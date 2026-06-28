import uuid
from collections import deque
from PyQt6.QtCore import QThread, pyqtSignal
from strands import Agent
from strands.models.openai import OpenAIModel
from strands.tools.mcp import MCPClient
from strands.agent.conversation_manager import SlidingWindowConversationManager
from mcp.client.sse import sse_client
import structlog
import json
import logging
import time
import warnings

warnings.filterwarnings(
    "ignore",
    message="reasoningContent is not supported in multi-turn conversations",
    category=UserWarning,
)

logger = structlog.get_logger()

# ── Fallback dedup tracker ──────────────────────────────────────────────
_FALLBACK_LOG: deque[tuple[str, float]] = deque(maxlen=6)
_FALLBACK_WINDOW_SEC = 60.0
_FALLBACK_MAX_REPEATS = 3
def _is_fallback_flood(text: str) -> bool:
    """Return True if *text* has been returned >= _FALLBACK_MAX_REPEATS
    within sliding window of _FALLBACK_WINDOW_SEC seconds.
    
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
    """
    # 1. Extract from JSON-like block
    import re
    json_match = re.search(r'\{[\s\S]*?\}', raw_text)
    if json_match:
        try:
            parsed = json.loads(json_match.group(0))
            return str(parsed.get("thought", parsed.get("dialogue", raw_text)))
        except json.JSONDecodeError:
            pass
    
    # 2. Extract quoted string content
    quoted_match = re.search(r'"([^"]+)"', raw_text)
    if quoted_match:
        return quoted_match.group(1)
    
    # 3. Clean markdown backticks
    cleaned = raw_text.strip()
    if cleaned.startswith("```") and cleaned.endswith("```"):
        cleaned = cleaned[3:-3].strip()
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()
    
    # 4. Remove obvious non-text artifacts
    artifacts = ["```json", "```", "//", "/*", "*/", "#", "*", "-", "_", "=", "~", ">", "<"]
    for artifact in artifacts:
        cleaned = cleaned.replace(artifact, " ")
    
    return cleaned.strip() if cleaned else raw_text

# ── after-tool-call event for telemetry ────────────────────────────────────
try:
    from strands.events import AfterToolCallEvent
except Exception:
    class AfterToolCallEvent:
        pass

def extract_dialogue_stream(accumulated_text: str) -> str:
    """Extract dialogue text from accumulated LLM output stream."""
    stripped = accumulated_text.strip()
    if not stripped:
        return ""

    # Find the start of JSON array or object
    json_start = -1
    for i, char in enumerate(accumulated_text):
        if char in ("[", "{"):
            json_start = i
            break
            
    if json_start != -1:
        # Ignore preamble before JSON start
        json_content = accumulated_text[json_start:]
        
        # Search for closed dialogue inside the JSON content
        match = re.search(r"\"dialogue\"s*:s*\"((?:[^\"\]|\.)*)\"", json_content)
        if match:
            try:
                val = match.group(1)
                if val.endswith("\\") and not val.endswith("\\\\"):
                    val = val[:-1]
                return val.encode("utf-8").decode("unicode_escape", errors="ignore")
            except Exception:
                return match.group(1)
                
        # Search for open dialogue inside the JSON content
        match_open = re.search(r"\"dialogue\"s*:s*\"((?:[^\"\]|\.|\)*)$", json_content)
        if match_open:
            try:
                val = match_open.group(1)
                if val.endswith("\\") and not val.endswith("\\\\"):
                    val = val[:-1]
                return val.encode("utf-8").decode("unicode_escape", errors="ignore")
            except Exception:
                return match_open.group(1)
                
        return ""  # We have JSON start, but dialogue key is not here yet
    # No JSON delimiters found at all. Treat as free-form text.
    if stripped.startswith("`"):
        return ""
        
    return accumulated_text

# ── Strands Autonomous Worker with Dual-Profile Support ─────────────────────
class StrandsAutonomousWorker(QThread):
    execution_complete = pyqtSignal(list)
    execution_failed = pyqtSignal(str)
    partial_text = pyqtSignal(str)

    def __init__(
        self,
        context: dict,
        chat_history: list,
        zen_api_key: str,
        uid: str,
        pet_id: str,
        is_autonomous: bool = True,
    ):
        """
        Stateless, single-shot background worker isolating context window 
        operations by user ID and pet ID.
        
        Args:
            context: Full context snapshot (autonomous) or {"user_query": str} (chat)
            chat_history: Recent message turns [{"role": "user"/"assistant", "content": "..."}]
            zen_api_key: OpenCode Zen API key
            uid: User ID for multi-user isolation
            pet_id: Pet ID for multi-pet isolation
            is_autonomous: Profile toggle - True=Deep Context (4000 tokens, tools), False=Ultra-Fast (1200 tokens, no tools)
        """
        super().__init__()
        self.context = context
        self.chat_history = chat_history
        self.zen_api_key = zen_api_key
        self.uid = uid
        self.pet_id = pet_id
        self.is_autonomous = is_autonomous
        self.agent = None
        self._is_aborted = False
        self._correlation_id = context.get("correlation_id", f"auto-{uuid.uuid4().hex[:6]}")
        
        # Connect natively to OpenCode Zen Cloud's Free Tier
        self.model = OpenAIModel(
            api_key=zen_api_key,
            base_url="https://opencode.ai/zen/v1",
            model_id="opencode/deepseek-v4-flash-free"
        )
        
        # Profile-specific conversation manager
        if self.is_autonomous:
            # Profile A: Background Autonomy — Deep context snapshot processing
            self._conversation_manager = SlidingWindowConversationManager()
            self._system_prompt = (
                f"You are Kenny, the anxious desktop pet with ID '{self.pet_id}' owned by user '{self.uid}'. "
                "You are operating autonomously in the background. Analyze the full environment context snapshots. "
                "Call tools if you need to alter state, scan files, or query information. "
                "Always return your final action response array matching the structural brain schema contract."
            )
            self._payload = f"Full Environment Context Snapshot: {json.dumps(self.context)}"
            self._tool_filters = None  # All tools allowed
        else:
            # Profile B: Direct Chat — Ultra-compressed prompts for sub-second text generation
            self._conversation_manager = SlidingWindowConversationManager()
            self._system_prompt = (
                f"You are Kenny (Pet ID: {self.pet_id}). The user ({self.uid}) is chatting directly with you. "
                "Respond immediately, concisely, and with intense wit. Avoid calling tools unless strictly requested. "
                "Always return your final response array matching the structural brain schema contract."
            )
            user_query = self.context.get("user_query", "")
            self._payload = f"Direct message from user: {user_query}"
            self._tool_filters = {"allowed": []}  # No tools by default

    def abort(self):
        """Thread-safe graceful cancellation framework."""
        logger.info("Signaling cancellation loop to active Strands Agent", uid=self.uid, pet_id=self.pet_id)
        self._is_aborted = True
        if self.agent:
            self.agent.cancel()

    def run(self):
        # Establish unique tracing correlation IDs linked to this multi-pet execution turn
        set_correlation_id(self._correlation_id)
        
        logger.info("Strands core worker invoked", uid=self.uid, pet_id=self.pet_id, is_autonomous=self.is_autonomous)
        try:
            # Connect to Daemon's internal in-process MCP server on port 4097
            mcp_client = MCPClient(
                lambda: sse_client("http://127.0.0.1:4097/sse"),
                tool_filters=self._tool_filters
            )
            
            with mcp_client:
                # Dynamic discovery strips out the need for hardcoded JSON schema files
                tools = mcp_client.list_tools_sync()
                
                # Inject conversation history into our isolated, single-shot memory manager
                for turn in self.chat_history:
                    self._conversation_manager.add_message(role=turn["role"], content=turn["content"])
                
                self.agent = Agent(
                    system_prompt=self._system_prompt,
                    tools=tools,
                    model=self.model,
                    conversation_manager=self._conversation_manager
                )
                
                # Register thread-safe Prometheus metric hooks
                self._attach_telemetry(self._correlation_id)
                
                # Fire the model execution turn
                raw_result = self.agent(self._payload)
                
                # Intercept execution cleanly if abort lifecycle fired mid-flight
                if self._is_aborted or getattr(raw_result, 'stop_reason', '') == "cancelled":
                    logger.info("Strands thread loop successfully broken before dispatch", correlation_id=self._correlation_id)
                    return

                parsed_actions = self._clean_and_parse_json(str(raw_result))
                self.execution_complete.emit(parsed_actions)
                
        except Exception as e:
            if not self._is_aborted:
                logger.error("Strands runner encountered an unhandled exception", error=str(e), correlation_id=self._correlation_id)
                self.execution_failed.emit(str(e))

    def _attach_telemetry(self, cid: str):
        def record_metrics(event: AfterToolCallEvent):
            # Pass unique user/pet dimensions down to your tracking logs
            logger.info("Strands executed background tool call", tool=event.tool_use["name"], uid=self.uid, pet_id=self.pet_id, correlation_id=cid)
            record_mcp_tool_call(name=event.tool_use["name"], success=event.exception is None, duration=event.duration_seconds)
        self.agent.hooks.add_listener(AfterToolCallEvent, record_metrics)

    def _clean_and_parse_json(self, text: str) -> list:
        # 1. Try direct JSON parsing first
        cleaned_text = text.strip()
        try:
            return json.loads(cleaned_text)
        except json.JSONDecodeError:
            pass

        # 2. Salavage from Markdown code blocks or formatted text
        salvaged = _salvage_text(text, cleaned_text)
        if salvaged != text:
            try:
                return json.loads(salvaged)
            except json.JSONDecodeError:
                pass

        # 3. Fallback for tool call processing: extract conversational content
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        thoughts = []

        # Try to find action/observation pattern
        for line in lines:
            if 'thought' in line.lower() or 'observation' in line.lower():
                thoughts.append({
                    "thought": line,
                    "dialogue": line,
                    "priority": 1
                })

        if thoughts:
            return thoughts

        # 4. Ultimate fallback: Provide meaningful output structure
        fallback_text = f"Analysis of context: {str(self.context)[:100]}..."
        if self.is_fallback_flood(fallback_text):
            return []
        
        return [{
            "thought": f"Processed context from {self.uid}'s pet '{self.pet_id}' via {'autonomous' if self.is_autonomous else 'user'} profile",
            "dialogue": text[:200] + "..." if len(text) > 200 else text,
            "priority": 2
        }]

    def is_fallback_flood(self, text: str) -> bool:
        """Check if text is being repeated too frequently."""
        return _is_fallback_flood(text)

    def record_mcp_tool_call(self, name: str, success: bool, duration: float):
        """Record MCP tool call metrics."""
        from prometheus_client import Counter, Histogram
        
        tool_call_count = Counter('daemon_mcp_tool_calls_total', 'Total MCP tool calls', 
                               ['uid', 'pet_id', 'tool_name', 'success'])
        tool_call_duration = Histogram('daemon_mcp_tool_call_duration_seconds', 
                                    'MCP tool call duration',
                                    ['uid', 'pet_id', 'tool_name'])
        
        tool_call_count.labels(uid=self.uid, pet_id=self.pet_id, tool_name=name, success=str(success)).inc()
        tool_call_duration.labels(uid=self.uid, pet_id=self.pet_id, tool_name=name).observe(duration)