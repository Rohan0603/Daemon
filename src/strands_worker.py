import json
import re
from PyQt6.QtCore import QThread, pyqtSignal
import structlog
from strands import Agent
from strands.models.openai import OpenAIModel
from strands.tools.mcp import MCPClient
from strands.agent.conversation_manager import SlidingWindowConversationManager
from mcp.client.sse import sse_client

logger = structlog.get_logger()

def extract_dialogue_stream(accumulated_text: str) -> str:
    # First check if it doesn't look like JSON/markdown block
    stripped = accumulated_text.strip()
    if stripped and not (stripped.startswith('[') or stripped.startswith('{') or stripped.startswith('`')):
        return accumulated_text

    # Search for closed dialogue
    match = re.search(r'"dialogue"\s*:\s*"((?:[^"\\]|\\.)*)"', accumulated_text)
    if match:
        try:
            val = match.group(1)
            if val.endswith('\\') and not val.endswith('\\\\'):
                val = val[:-1]
            return val.encode('utf-8').decode('unicode_escape', errors='ignore')
        except Exception:
            return match.group(1)
            
    # Search for open dialogue
    match_open = re.search(r'"dialogue"\s*:\s*"((?:[^"\\]|\\.|\\)*)$', accumulated_text)
    if match_open:
        try:
            val = match_open.group(1)
            if val.endswith('\\') and not val.endswith('\\\\'):
                val = val[:-1]
            return val.encode('utf-8').decode('unicode_escape', errors='ignore')
        except Exception:
            return match_open.group(1)
            
    return ""


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
                    "get_memory", "get_diary", "query_memory"
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

            system_prompt = (
                "You are Kenny, the anxious, roasting desktop pet. Run autonomously in the background. "
                "Analyze the user's environment context. Use your tools to interact. "
                f"Your active profanity filter constraint is: {self.profanity_level}. "
                "Always output your final actions strictly as a JSON array matching the brain schema."
            )

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
        cleaned = re.sub(r'^```[a-z]*\n?(.*?)\n?```$', r'\1', cleaned, flags=re.DOTALL).strip()
        try:
            result = json.loads(cleaned)
            if isinstance(result, dict):
                result = [result]
            # Truncate every parsed dialogue field to the configured char limit
            for item in result:
                if isinstance(item, dict) and "dialogue" in item and len(item["dialogue"]) > BUBBLE_MAX_CHARS:
                    item["dialogue"] = item["dialogue"][:BUBBLE_MAX_CHARS - 3] + "..."
            return result
        except json.JSONDecodeError:
            # Model returned free-form text instead of structured JSON.
            # Use a sensible fallback: "observation" is a valid thought type
            # that the dispatch pipeline can work with, and the raw text
            # becomes the bubble dialogue.
            truncated = text if len(text) <= BUBBLE_MAX_CHARS else text[:BUBBLE_MAX_CHARS - 3] + "..."
            return [{"thought": "observation", "dialogue": truncated, "priority": 1}]
