# src/llm/strands_worker.py
import asyncio
import json
import re
import time
from collections import deque
from PyQt6.QtCore import QThread, pyqtSignal
import structlog
import warnings

# DeepSeek models emit reasoning_content tokens in every assistant turn.
# Strands SDK warns because it can't include them in multi-turn Chat Completions history.
# This is expected behaviour for this model — suppress the warning.
warnings.filterwarnings(
    "ignore",
    message="reasoningContent is not supported in multi-turn conversations",
    category=UserWarning,
)
from strands import Agent
from strands.models.openai import OpenAIModel
from strands.tools.mcp import MCPClient
from strands.agent.conversation_manager import SlidingWindowConversationManager
from mcp.client.sse import sse_client

logger = structlog.get_logger()

# ── Fallback dedup tracker ──────────────────────────────────────────────
# Prevents the same fallback message from flooding the bubble when LLM
# consistently fails to produce parseable JSON.
_FALLBACK_LOG: deque[tuple[str, float]] = deque(maxlen=6)
_FALLBACK_WINDOW_SEC = 60.0
_FALLBACK_MAX_REPEATS = 3
def _is_fallback_flood(text: str) -> bool:
    """Return True if *text* has been returned >= _FALLBACK_MAX_REPEATS
    within the sliding window of _FALLBACK_WINDOW_SEC seconds.
    
    When True the caller should log silently instead of emitting a visible
    bubble, breaking the infinite-repetition feedback loop."""
    now = time.time()
    # Purge stale entries
    while _FALLBACK_LOG and now - _FALLBACK_LOG[0][1] > _FALLBACK_WINDOW_SEC:
        _FALLBACK_LOG.popleft()
    # Count recent occurrences of this exact text
    count = sum(1 for t, _ in _FALLBACK_LOG if t == text)
    # Record this occurrence (always — even if we skip it, the next call needs to see it)
    _FALLBACK_LOG.append((text, now))
    return count >= _FALLBACK_MAX_REPEATS
def _salvage_text(raw_text: str, cleaned: str = "") -> str:
    """Try to extract human-readable text from failed JSON model output.

    The model often generates conversational dialogue text that just isn't
    wrapped in valid JSON. This function strips JSON syntax artifacts and
    returns whatever natural-language text can be recovered.

    Strategy:
    1. Try to find any quoted string value that looks like dialogue (long, multi-word)
    2. Strip JSON structural characters + key names from the text
    3. Return the raw text if all else fails (with JSON artifacts removed)
    """
    text = cleaned or raw_text

    # Strategy 1: Find any long quoted string value — model often puts
    # dialogue text as a JSON value even when the JSON is malformed
    quoted_values = re.findall(r'"((?:[^"\\]|\\.){10,})"', text)
    dialogue_candidates = [
        v for v in quoted_values
        if v and not v.startswith("thought") and not v.startswith("dialogue")
        and not v.startswith("type") and not v.startswith("priority")
        and not v.startswith("brain_update") and not v.startswith("context_hash")
        and not v.startswith("observation") and not v.startswith("intel_roast")
        and not v.startswith("typing_reaction") and not v.startswith("idle_thought")
        and "should probably implement" not in v
        and "If I stare at this cursor" not in v
        and "Wonder if the FSM" not in v
        and "Look man, I don't want to alarm" not in v
        and "You haven't twitched" not in v
        and "Oh man, the keyboard" not in v
        and len(v) > 15  # Filter out short keys like "idle", "ok"
    ]
    if dialogue_candidates:
        # Prefer the longest candidate (likely the dialogue field)
        best = max(dialogue_candidates, key=len)
        try:
            best = best.encode('utf-8').decode('unicode_escape', errors='ignore')
        except Exception:
            pass
        return best

    # Strategy 2: Strip JSON key names and structural chars
    # Remove common JSON key patterns: "key": value
    stripped = re.sub(
        r'"(thought|dialogue|type|priority|brain_update|observation|'
        r'intel_roast|typing_reaction|idle_thought|context_hash|action|'
        r'user_habits|user_preferences|pet_quirks|pet_habits|pet_fears|'
        r'pet_catchphrases|mission_goals|pet_affinity_score)"\s*:\s*',
        '', text
    )
    # Remove remaining JSON structural characters
    for ch in ('[', ']', '{', '}', '"', '\\'):
        stripped = stripped.replace(ch, '')
    stripped = stripped.strip().strip(',').strip()
    # Clean up double spaces and commas
    stripped = re.sub(r'\s{2,}', ' ', stripped)
    stripped = re.sub(r',\s*,', ',', stripped)
    if stripped and len(stripped) > 10:
        return stripped

    # Strategy 3: Return raw text as last resort
    raw_clean = raw_text.strip()
    # Strip leading/trailing JSON structure
    raw_clean = raw_clean.lstrip('[{( ')
    raw_clean = raw_clean.rstrip(']}) ,')
    if raw_clean and len(raw_clean) > 10:
        return raw_clean

    return ""
def extract_dialogue_stream(accumulated_text: str) -> str:
    stripped = accumulated_text.strip()
    if not stripped:
        return ""

    # Find the start of JSON array or object
    json_start = -1
    for i, char in enumerate(accumulated_text):
        if char in ('[', '{'):
            json_start = i
            break
            
    if json_start != -1:
        # Ignore preamble before JSON start
        json_content = accumulated_text[json_start:]
        
        # Search for closed dialogue inside the JSON content
        match = re.search(r'"dialogue"\s*:\s*"((?:[^"\\]|\\.)*)"', json_content)
        if match:
            try:
                val = match.group(1)
                if val.endswith('\\') and not val.endswith('\\\\'):
                    val = val[:-1]
                return val.encode('utf-8').decode('unicode_escape', errors='ignore')
            except Exception:
                return match.group(1)
                
        # Search for open dialogue inside the JSON content
        match_open = re.search(r'"dialogue"\s*:\s*"((?:[^"\\]|\\.|\\)*)$', json_content)
        if match_open:
            try:
                val = match_open.group(1)
                if val.endswith('\\') and not val.endswith('\\\\'):
                    val = val[:-1]
                return val.encode('utf-8').decode('unicode_escape', errors='ignore')
            except Exception:
                return match_open.group(1)
                
        return ""  # We have JSON start, but dialogue key is not here yet
    # No JSON delimiters found at all. Treat as free-form text.
    if stripped.startswith('`'):
        return ""
        
    return accumulated_text
# No module-level _interpolate_prompt — it's an instance method on StrandsAutonomousWorker
def _install_warning_filters() -> None:
    """Install warning filters for known SDK warnings."""
    import warnings
    warnings.filterwarnings(
        "ignore",
        message="reasoningContent is not supported in multi-turn conversations",
        category=UserWarning,
    )
class StrandsSession:
    _instance = None
    _tools_cache: list | None = None
    _tools_cache_ts: float = 0
    _TOOLS_CACHE_TTL: float = 60.0

    @classmethod
    def _get_cached_tools(cls, mcp_client) -> list:
        now = time.time()
        if cls._tools_cache is not None and now - cls._tools_cache_ts < cls._TOOLS_CACHE_TTL:
            return cls._tools_cache
        cls._tools_cache = mcp_client.list_tools_sync()
        cls._tools_cache_ts = now
        return cls._tools_cache

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    def __init__(self):
        self.mode = None
        self.mcp_client = None
        self.agent = None
        self.model = None

    def get_agent(self, mode: str, system_prompt: str, model, messages: list, tool_callback=None) -> tuple[Agent, list]:
        """Get or create the persistent agent and return (agent, tools)."""
        recreate = False
        if self.agent is None or self.mode != mode or self.mcp_client is None:
            recreate = True

        if recreate:
            self.close()
            import time
            time.sleep(0.5)  # Let old SSE connection drain before creating new MCP client
            self.mode = mode
            self.model = model
            
            tool_filters = None
            if mode == "autonomous":
                READ_ONLY_TOOL_NAMES = {
                    "list_directory", "read_file", "search_codebase",
                    "get_memory", "get_diary", "query_memory",
                    "change_visual_state"
                }
                tool_filters = {"allowed": list(READ_ONLY_TOOL_NAMES)}
            
            logger.info("Recreating StrandsSession", mode=mode, tool_filters=tool_filters)
            self.mcp_client = MCPClient(
                lambda: sse_client("http://127.0.0.1:4097/sse"),
                tool_filters=tool_filters
            )
            self.mcp_client.__enter__()
            tools = self._get_cached_tools(self.mcp_client)
            
            self.agent = Agent(
                system_prompt=system_prompt,
                tools=tools,
                model=self.model,
                messages=messages,
                conversation_manager=SlidingWindowConversationManager()
            )
        else:
            logger.info("Reusing persistent StrandsSession agent", mode=mode)
            from strands.types.content import split_system_prompt
            self.agent._system_prompt, self.agent._system_prompt_content = split_system_prompt(system_prompt)
            self.agent.messages = messages
            tools = self._get_cached_tools(self.mcp_client)

        # Update hooks
        from strands.hooks import AfterToolCallEvent
        self.agent.hooks._registered_callbacks[AfterToolCallEvent] = []
        
        def record_metrics(event: AfterToolCallEvent):
            try:
                from src.observability import record_mcp_tool_call
                record_mcp_tool_call(
                    tool_name=event.tool_use["name"],
                    duration_seconds=0.0,
                    allowed=event.exception is None
                )
            except Exception:
                pass
        self.agent.hooks.add_callback(AfterToolCallEvent, record_metrics)

        if tool_callback:
            self.agent.hooks.add_callback(AfterToolCallEvent, tool_callback)

        return self.agent, tools
    def close(self):
        self._tools_cache = None
        self._tools_cache_ts = 0
        if self.mcp_client is not None:
            logger.info("Closing StrandsSession MCP client")
            try:
                self.mcp_client.__exit__(None, None, None)
            except GeneratorExit:
                pass  # Expected during SSE connection teardown
            except asyncio.CancelledError:
                pass  # Expected during asyncio scope cancellation
            except Exception:
                logger.exception("Error closing MCP client")
            self.mcp_client = None
        self.agent = None
        self.mode = None
class StrandsAutonomousWorker(QThread):
    execution_complete = pyqtSignal(list)
    execution_failed = pyqtSignal(str)
    partial_text = pyqtSignal(str)

    def __init__(self, context: dict, chat_history: list, profanity_level: str = "moderate", config: dict | None = None, mode: str = "user"):
        super().__init__()
        self.context = context
        self.chat_history = chat_history  # [{"role": "user"/"assistant", "content": "..."}]
        self.profanity_level = profanity_level
        self.mode = mode
        self.agent = None
        self._is_aborted = False
        
        from src.config import load_config
        self.config = config if config is not None else load_config()
        llm_cfg = self.config.get("llm", {})
        provider = llm_cfg.get("provider", "opencode-zen")
        api_key = llm_cfg.get("api_key", "")
        model_id = llm_cfg.get("model_id", "deepseek-v4-flash-free")
        
        base_url = "https://opencode.ai/zen/v1"
        if provider == "openrouter":
            base_url = "https://openrouter.ai/api/v1"
        elif provider == "opencode-go":
            base_url = "https://opencode.ai/go/v1"
        elif provider == "opencode-zen" or provider == "opencode":
            base_url = "https://opencode.ai/zen/v1"
            
        self.model = OpenAIModel(
            client_args={
                "api_key": api_key,
                "base_url": base_url,
            },
            model_id=model_id,
            response_format={"type": "json_object"},
        )

    def _interpolate_prompt(self, prompt: str) -> str:
        """Replace {{placeholder}} tokens with config/context values."""
        replacements = {
            "pet_id":        str(self.config.get("pet", {}).get("id", "")),
            "persona_name":  str(self.config.get("pet", {}).get("persona_name", "")),
            "chattiness":    str(self.config.get("pet", {}).get("chattiness", "")),
            "apm":           str(self.context.get("apm", "")),
        }
        for key, val in replacements.items():
            prompt = prompt.replace("{{" + key + "}}", val)
        return prompt

    def abort(self):
        """Called by PetWindow to gracefully halt the ReAct loop."""
        logger.info("Aborting background Strands worker...")
        self._is_aborted = True
        if self.agent:
            self.agent.cancel()

    def run(self):
        logger.info("Initiating Strands background orchestration layer", mode=self.mode)
        try:
            import urllib.request
            import time

            # Wait for MCP server on port 4097 to be ready (fast polling)
            mcp_ready = False
            for i in range(5):
                if self._is_aborted:
                    logger.info("Strands worker aborted during startup waiting for MCP server")
                    return
                try:
                    with urllib.request.urlopen("http://127.0.0.1:4097/health", timeout=1.0) as response:
                        if response.status == 200:
                            mcp_ready = True
                            break
                except Exception:
                    pass
                time.sleep(0.3)
            if not mcp_ready:
                logger.warning("MCP server at port 4097 is not ready, proceeding anyway")

            # Format history to avoid "unsupported type" crashes
            formatted_history = []
            for turn in self.chat_history:
                # Strip assistant responses in autonomous mode to prevent
                # pool-refill outputs from inflating the LLM context window
                if self.mode == "autonomous" and turn["role"] == "assistant":
                    continue
                role = turn["role"]
                content = turn["content"]
                if isinstance(content, str):
                    formatted_contents = [{"text": content}]
                elif isinstance(content, list):
                    formatted_contents = []
                    for block in content:
                        if isinstance(block, dict) and "text" in block:
                            formatted_contents.append(block)
                        elif isinstance(block, str):
                            formatted_contents.append({"text": block})
                else:
                    formatted_contents = [{"text": str(content)}]
                    
                formatted_history.append({
                    "role": role,
                    "content": formatted_contents
                })

            from pathlib import Path
            project_root = Path(__file__).parent.parent.resolve()
            pet_id = self.config.get("pet", {}).get("id", "kenny")
            skill_path = project_root / ".opencode" / "skills" / pet_id / "SKILL.md"
            if not skill_path.exists():
                skill_path = project_root / ".opencode" / "skills" / "kenny" / "SKILL.md"

            skill_content = ""
            if skill_path.exists():
                try:
                    raw_skill = skill_path.read_text(encoding="utf-8")
                    if raw_skill.strip().startswith("---"):
                        parts = raw_skill.strip().split("---", 2)
                        if len(parts) >= 3:
                            skill_content = parts[2].strip()
                        else:
                            skill_content = raw_skill.strip()
                    else:
                        skill_content = raw_skill.strip()
                except Exception as e:
                    logger.error("Failed to read SKILL.md", path=str(skill_path), error=str(e))

            base_prompt = (
                "You are Kenny, the anxious, roasting desktop pet. Run autonomously in the background. "
                "Analyze the user's environment context. Use your tools to interact. "
                f"Your active profanity filter constraint is: {self.profanity_level}. "
                "CRITICAL: Your response must be valid JSON. No markdown fences. No prose. Only a JSON array. "
                "Always output your final actions strictly as a JSON array matching the brain schema. "
                "IMPORTANT: For change_visual_state, use ONLY actions from the valid list: "
                "bounce, celebrate, chase, dash, devastated, fall, flail, flip, float, glitch, grow, "
                "headshake, hyper, idle, inflate, jump, look_away, melt, nod, pulse, rainbow, shake, "
                "shrink, spin, strut, teleport, tremble, vanish, wander, wave, wobble. "
                "Do NOT invent new action names."
            )
            if skill_content:
                if self.mode == "autonomous":
                    # Condensed persona for autonomous refills: strip Phonetics &
                    # Delivery section (~3K chars of voice instructions irrelevant for
                    # background thought generation). Keep identity, rules, and schema.
                    condensed_parts = skill_content.split("\n## Phonetics & Delivery", maxsplit=1)
                    stripped = condensed_parts[0].strip()
                    # Shorten the lengthy action/examples section too
                    system_prompt = (f"{stripped}\n\n[System Instructions - condensed]\n{base_prompt}"
                                     "\n\nTOOL BUDGET: You have a budget of at most 3 tool calls for this response. Use them wisely.")
                else:
                    system_prompt = f"{skill_content}\n\n[System Instructions]\n{base_prompt}"
            else:
                system_prompt = base_prompt

            # Get the persistent agent and tools from StrandsSession
            session = StrandsSession.get_instance()
            self.agent, tools = session.get_agent(
                mode=self.mode,
                system_prompt=system_prompt,
                model=self.model,
                messages=formatted_history
            )

            def on_chunk(data: str = None, reasoningText: str = None, complete: bool = False, **kwargs):
                if data and not self._is_aborted:
                    self.partial_text.emit(data)

            # Execute the single-shot ReAct worker passing the callback
            raw_result = self.agent(
                f"Current system state: {json.dumps(self.context)}",
                callback_handler=on_chunk
            )
            
            # Check if execution was halted mid-flight
            if self._is_aborted or getattr(raw_result, 'stop_reason', '') == "cancelled":
                logger.info("Strands execution was successfully cancelled.")
                return

            parsed_actions = self._clean_and_parse_json(str(raw_result))
            self.execution_complete.emit(parsed_actions)
            
        except Exception as e:
            if not self._is_aborted:
                logger.error("Strands worker execution crashed", error=str(e))
                self.execution_failed.emit(str(e))

    def _clean_and_parse_json(self, text: str) -> list:
        from src.constants import BUBBLE_MAX_CHARS
        cleaned = text.strip()

        # Extract JSON content from markdown code fences or preambles/postambles
        # 1. Look for ```json ... ``` blocks
        md_json = re.search(r'```json\s*(.*?)\s*```', cleaned, re.DOTALL)
        if md_json:
            cleaned = md_json.group(1).strip()
        else:
            # 2. Look for generic ``` ... ``` blocks
            md_generic = re.search(r'```\s*(.*?)\s*```', cleaned, re.DOTALL)
            if md_generic:
                block = md_generic.group(1).strip()
                # Use it if it starts with JSON indicators
                if (block.startswith('[') and block.endswith(']')) or (block.startswith('{') and block.endswith('}')):
                    cleaned = block
            else:
                # 3. Fallback to bracket/brace matching to strip preamble/postamble
                first_bracket = cleaned.find('[')
                first_brace = cleaned.find('{')
                if first_bracket != -1 and (first_brace == -1 or first_bracket < first_brace):
                    last_bracket = cleaned.rfind(']')
                    if last_bracket != -1 and last_bracket > first_bracket:
                        cleaned = cleaned[first_bracket:last_bracket+1].strip()
                elif first_brace != -1:
                    last_brace = cleaned.rfind('}')
                    if last_brace != -1 and last_brace > first_brace:
                        cleaned = cleaned[first_brace:last_brace+1].strip()

        try:
            result = json.loads(cleaned)
            if isinstance(result, dict):
                result = [result]
            # Truncate every parsed dialogue field to the configured char limit
            for item in result:
                if isinstance(item, dict) and "dialogue" in item and len(item["dialogue"]) > BUBBLE_MAX_CHARS:
                    item["dialogue"] = item["dialogue"][:BUBBLE_MAX_CHARS - 3] + "..."
            return result
        except json.JSONDecodeError as e:
            logger.warning("JSON decode failed in Strands worker: %s", str(e))
            
            # If the response looks like JSON (starts with delimiter or contains markers)
            # but failed parsing, try to extract dialogue via regex to avoid showing raw JSON to user.
            is_json_like = (
                cleaned.startswith('[') or 
                cleaned.startswith('{') or 
                '"dialogue"' in cleaned or 
                '"thought"' in cleaned
            )
            if is_json_like:
                dialogue_text = None
                thought_text = None
                
                # 1. Try line-by-line greedy extraction first (for pretty-printed JSON)
                for line in cleaned.splitlines():
                    line = line.strip()
                    m_dialogue = re.search(r'"dialogue"\s*:\s*"(.*)"\s*,?\s*$', line)
                    if m_dialogue:
                        dialogue_text = m_dialogue.group(1)
                    m_thought = re.search(r'"thought"\s*:\s*"(.*)"\s*,?\s*$', line)
                    if m_thought:
                        thought_text = m_thought.group(1)
                
                # 2. Fallback to non-greedy extraction across whole text
                if not dialogue_text:
                    dialogue_matches = re.findall(r'"dialogue"\s*:\s*"((?:[^"\\]|\\.)*)"', cleaned)
                    if dialogue_matches:
                        dialogue_text = dialogue_matches[0]
                if not thought_text:
                    thought_matches = re.findall(r'"thought"\s*:\s*"((?:[^"\\]|\\.)*)"', cleaned)
                    if thought_matches:
                        thought_text = thought_matches[0]

                if dialogue_text:
                    try:
                        dialogue_text = dialogue_text.encode('utf-8').decode('unicode_escape', errors='ignore')
                    except Exception:
                        pass
                    
                    if thought_text:
                        try:
                            thought_text = thought_text.encode('utf-8').decode('unicode_escape', errors='ignore')
                        except Exception:
                            pass
                    else:
                        thought_text = "Observation (JSON Parse Error Recovery)"
                    
                    truncated = dialogue_text if len(dialogue_text) <= BUBBLE_MAX_CHARS else dialogue_text[:BUBBLE_MAX_CHARS - 3] + "..."
                    return [{"thought": thought_text, "dialogue": truncated, "priority": 1}]

                # If we couldn't even extract dialogue via regex, try to salvage
                # natural-language text from the raw output. The model often generates
                # conversational text that just isn't wrapped in valid JSON — show that
                # instead of repeating the canned "segfaulted" message.
                salvaged = _salvage_text(text, cleaned)
                if salvaged:
                    truncated = salvaged if len(salvaged) <= BUBBLE_MAX_CHARS else salvaged[:BUBBLE_MAX_CHARS - 3] + "..."
                    if _is_fallback_flood(truncated):
                        logger.warning("Suppressing repeated salvaged bubble (flood detected)")
                        return [{"thought": "...", "dialogue": ". . .", "priority": 5, "type": "observation"}]
                    return [{
                        "thought": "Recovered from JSON parse error",
                        "dialogue": truncated,
                        "type": "observation",
                        "priority": 5
                    }]

                # Last resort: user-friendly segfault message rather than raw JSON code.
                fallback_text = "Holy crap, my brain just segfaulted! (JSON Parse Error)"
                if _is_fallback_flood(fallback_text):
                    logger.warning("Suppressing repeated fallback bubble (flood detected)")
                    return [{"thought": "...", "dialogue": ". . .", "priority": 5, "type": "observation"}]
                return [{
                    "thought": "Strands worker JSON parse failure",
                    "dialogue": fallback_text,
                    "type": "observation",
                    "priority": 5
                }]

            # Truly free-form text: display directly in the bubble.
            truncated = text if len(text) <= BUBBLE_MAX_CHARS else text[:BUBBLE_MAX_CHARS - 3] + "..."
            if _is_fallback_flood(truncated):
                logger.warning("Suppressing repeated free-form bubble (flood detected)")
                return [{"thought": ". . .", "dialogue": ". . .", "priority": 5, "type": "observation"}]
            return [{"thought": "observation", "dialogue": truncated, "priority": 1}]