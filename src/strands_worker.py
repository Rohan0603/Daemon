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

class StrandsAutonomousWorker(QThread):
    execution_complete = pyqtSignal(list)
    execution_failed = pyqtSignal(str)

    def __init__(self, context: dict, chat_history: list, profanity_level: str = "moderate", config: dict | None = None):
        super().__init__()
        self.context = context
        self.chat_history = chat_history  # [{"role": "user"/"assistant", "content": "..."}]
        self.profanity_level = profanity_level
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
        logger.info("Initiating Strands background orchestration layer")
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

            mcp_client = MCPClient(lambda: sse_client("http://127.0.0.1:4097/sse"))
            
            with mcp_client:
                tools = mcp_client.list_tools_sync()
                
                # Format history to avoid "unsupported type" crashes
                formatted_history = []
                for turn in self.chat_history:
                    role = turn["role"]
                    content = turn["content"]
                    # If content is a string, wrap it in a ContentBlock list
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

                self.agent = Agent(
                    system_prompt=(
                        "You are Kenny, the anxious, roasting desktop pet. Run autonomously in the background. "
                        "Analyze the user's environment context. Use your tools to interact. "
                        f"Your active profanity filter constraint is: {self.profanity_level}. "
                        "Always output your final actions strictly as a JSON array matching the brain schema."
                    ),
                    tools=tools,
                    model=self.model,
                    messages=formatted_history,
                    conversation_manager=SlidingWindowConversationManager()
                )
                
                # Instrument the agent to record Prometheus metrics.
                # This is a read-only observer — must never block tool execution.
                from strands.hooks import AfterToolCallEvent
                def record_metrics(event: AfterToolCallEvent):
                    try:
                        from src.observability import record_mcp_tool_call
                        record_mcp_tool_call(
                            tool_name=event.tool_use["name"],
                            duration_seconds=0.0,
                            allowed=event.exception is None
                        )
                    except Exception:
                        pass  # instrumentation must never crash the pipeline
                self.agent.hooks.add_callback(AfterToolCallEvent, record_metrics)
                
                # Execute the single-shot ReAct worker
                raw_result = self.agent(f"Current system state: {json.dumps(self.context)}")
                
                # Check if execution was halted mid-flight
                if self._is_aborted or getattr(raw_result, 'stop_reason', '') == "cancelled":
                    logger.info("Strands execution was successfully cancelled.")
                    return  # Exit cleanly without emitting completion signals

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
