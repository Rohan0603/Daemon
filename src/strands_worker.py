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

    def __init__(self, context: dict, chat_history: list, profanity_level: str = "moderate"):
        super().__init__()
        self.context = context
        self.chat_history = chat_history  # [{"role": "user"/"assistant", "content": "..."}]
        self.profanity_level = profanity_level
        self.agent = None
        self._is_aborted = False
        
        # Map Strands to the port 4096 OpenCode server
        self.model = OpenAIModel(
            api_key="opencode-local",
            base_url="http://127.0.0.1:4096/v1",
            model_id="opencode-default"
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
            mcp_client = MCPClient(lambda: sse_client("http://127.0.0.1:4097/sse"))
            
            with mcp_client:
                tools = mcp_client.list_tools_sync()
                
                memory = SlidingWindowConversationManager(max_tokens=4000)
                for turn in self.chat_history:
                    memory.add_message(role=turn["role"], content=turn["content"])
                
                self.agent = Agent(
                    system_prompt=(
                        "You are Kenny, the anxious, roasting desktop pet. Run autonomously in the background. "
                        "Analyze the user's environment context. Use your tools to interact. "
                        f"Your active profanity filter constraint is: {self.profanity_level}. "
                        "Always output your final actions strictly as a JSON array matching the brain schema."
                    ),
                    tools=tools,
                    model=self.model,
                    conversation_manager=memory
                )
                
                # Instrument the agent to record Prometheus metrics
                from strands.hooks import AfterToolCallEvent
                def record_metrics(event: AfterToolCallEvent):
                    from src.observability import record_mcp_tool_call
                    record_mcp_tool_call(
                        name=event.tool.name,
                        success=event.success,
                        duration=event.duration_seconds
                    )
                self.agent.hooks.add_listener(AfterToolCallEvent, record_metrics)
                
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
        cleaned = text.strip()
        cleaned = re.sub(r'^```[a-z]*\n?(.*?)\n?```$', r'\1', cleaned, flags=re.DOTALL).strip()
        try:
            result = json.loads(cleaned)
            if isinstance(result, dict):
                result = [result]
            return result
        except json.JSONDecodeError:
            return [{"thought": "Strands payload parsing failure", "dialogue": text, "priority": 1}]
