import json
import re
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
            tools = self.mcp_client.list_tools_sync()
            
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
            tools = self.mcp_client.list_tools_sync()

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
        if self.mcp_client is not None:
            logger.info("Closing StrandsSession MCP client")
            try:
                self.mcp_client.__exit__(None, None, None)
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
            model_id=model_id
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

            # Wait up to 5 seconds for MCP server on port 4097 to be ready
            mcp_ready = False
            for i in range(10):
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
                time.sleep(0.5)
            if not mcp_ready:
                logger.warning("MCP server at port 4097 is not ready, proceeding anyway")

            # Format history to avoid "unsupported type" crashes
            formatted_history = []
            for turn in self.chat_history:
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
                "Always output your final actions strictly as a JSON array matching the brain schema."
            )
            if skill_content:
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

                # If we couldn't even extract dialogue via regex, return a user-friendly segfault message
                # rather than raw JSON code.
                return [{
                    "thought": "Strands worker JSON parse failure",
                    "dialogue": "Holy crap, my brain just segfaulted! (JSON Parse Error)",
                    "type": "observation",
                    "priority": 5
                }]

            # Truly free-form text: display directly in the bubble.
            truncated = text if len(text) <= BUBBLE_MAX_CHARS else text[:BUBBLE_MAX_CHARS - 3] + "..."
            return [{"thought": "observation", "dialogue": truncated, "priority": 1}]

