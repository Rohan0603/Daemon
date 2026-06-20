# Strands Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the manual ReAct execution framework and custom `while` loops with the Strands Agents SDK.

**Architecture:** This update enables dynamic tool discovery via the local port 4097 MCP server, bridges natively with the OpenCode port 4096 LLM API, simplifies context tracking, and isolates orchestration overhead inside a clean PyQt6 `QThread` pipeline. The worker is entirely stateless, thread-safe, single-shot, dynamically injecting conversation history and profanity rules on each run, fully supports graceful UI cancellation, and leverages the EventBus for decoupled state transitions.

**Tech Stack:** Python, PyQt6, strands-agents, strands-agents-mcp-server, mcp

---

## Task 1: Environment Setup & Prerequisites

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Install Strands packages**
```bash
py -m pip install strands-agents strands-agents-mcp-server mcp
```

- [ ] **Step 2: Update `requirements.txt`**  
Append the new dependencies to `requirements.txt` to keep the PyInstaller setup clean.
```text
strands-agents
strands-agents-mcp-server
mcp
```

- [ ] **Step 3: Run targeted test baseline**
> **Note:** Do not run the full test suite (`py -m pytest tests/ -v`) as it generates too much output and consumes excessive tokens. Only run tests related to the files we are modifying:
```bash
py -m pytest tests/test_fsm.py tests/test_response_manager.py tests/test_response_pool.py -v
```

---

## Task 2: Build the `StrandsAutonomousWorker` Class

**Files:**
- Create: `src/strands_worker.py`

- [ ] **Step 1: Scaffold imports and signals**  
Import Strands components and hook them into custom PyQt signals:
```python
import json
from PyQt6.QtCore import QThread, pyqtSignal
import structlog
from strands import Agent
from strands.models.openai import OpenAIModel
from strands.tools.mcp import MCPClient
from strands.memory import SlidingWindowConversationManager
from mcp.client.sse import sse_client

logger = structlog.get_logger()
```

- [ ] **Step 2: Implement the initialization and abort routines**
Build the constructor to receive context data, chat history, and the profanity configuration. Define the `abort()` method using native Strands cancellation:
```python
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
```

- [ ] **Step 3: Implement the `run()` execution block**  
Build out the asynchronous runner. Use the native `MCPClient` context manager to ingest all 13 Daemon tool definitions directly from port 4097, prime the conversation history, dynamically inject the profanity level into the prompt, and handle abort checks:
```python
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
```

- [ ] **Step 4: Add clean string parsing guards**
Implement the standard json markdown fence trimming mechanism. Ensure triple backticks are fully stripped to prevent `JSONDecodeError`:
```python
    def _clean_and_parse_json(self, text: str) -> list:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return [{"thought": "Strands payload parsing failure", "dialogue": text, "priority": 1}]
```

---

## Task 3: Wire into the Behavior Engine (`src/pet_window.py`)

**Files:**
- Modify: `src/pet_window.py`

- [ ] **Step 1: Import the worker and EventTypes**  
At the top of `src/pet_window.py`, import the `StrandsAutonomousWorker` and `EventType` if not already imported.

- [ ] **Step 2: Swap out legacy invocation with safe Thread re-assignment**  
Locate the execution block where background autonomous triggers are evaluated. Ensure you safely block and abort the active thread before re-assignment:
```python
    def _on_autonomous_trigger_fired(self):
        # 1. Safely halt any existing in-flight ReAct loop to prevent memory leaks/crashes
        if hasattr(self, 'strands_worker') and self.strands_worker and self.strands_worker.isRunning():
            self.strands_worker.abort()
            self.strands_worker.wait() # Safely block for the cancellation point
            
        current_context = self._behavior.build_context_snapshot() 
        profanity_level = self._config.get("pet", {}).get("profanity_level", "moderate")
        
        # 2. Pull last 10 turns for context injection
        recent_chat_raw = self._history.get_recent(10)
        recent_chat = []
        for item in recent_chat_raw:
            if item.get("user_input"):
                recent_chat.append({"role": "user", "content": item["user_input"]})
            if item.get("daemon_response"):
                recent_chat.append({"role": "assistant", "content": item["daemon_response"]})
        
        self.strands_worker = StrandsAutonomousWorker(current_context, recent_chat, profanity_level)
        self.strands_worker.execution_complete.connect(self._on_strands_response_ready)
        
        # 3. Handle failures gracefully to un-stick the FSM
        def handle_failure(err):
            logger.error("Strands error", error=err)
            self._fsm.transition_to(PetState.IDLE)
            self._autonomous_query_pending = False

        self.strands_worker.execution_failed.connect(handle_failure)
        
        # Force FSM into tracking state
        self._fsm.transition_to(PetState.AUTONOMOUS_THINKING)
        self.strands_worker.start()
```

- [ ] **Step 3: Connect responses to the EventBus and pools**
Instead of hard-wiring the worker's response to UI slots, publish to the EventBus and cache surplus outputs:
```python
    def _on_strands_response_ready(self, items: list):
        self._autonomous_query_pending = False

        if items:
            # Publish to the decoupled Behavior logic layer via EventBus
            # (Requires registering a listener for LLM_RESPONSE_READY in BehaviorController)
            self._events.publish(Event(
                type=EventType.LLM_RESPONSE_READY,
                source="strands_worker",
                data={"items": items}
            ))
            # Fallback for immediate UI dispatch if EventBus refactor is deferred:
            # self._dispatch_structured(items[0])
            
        # If surplus items are generated, prime your thought pools
        if len(items) > 1:
            for surplus in items[1:]:
                self._response_manager.thought_pool.add_item(surplus)
```

---

## Task 4: Prune Obsolete Code Base Structures

**Files:**
- Modify: `src/context_manager.py`
- Modify: `src/opencode_worker.py` (Delete/deprecate)

- [ ] **Step 1: Drop legacy prompt blocks from `src/context_manager.py`**  
Locate and delete massive raw string instructions that were previously used to explicitly tell the model *how* to call tools or construct JSON schemas.

- [ ] **Step 2: Clean up array tracking rules inside historical caches**  
Prune any custom list-popping mechanisms that were manually truncating the conversation turn records.

- [ ] **Step 3: Remove custom JSON regex parsing fallbacks**  
Simplify the parsing layer since Strands structurally enforces correct tool-handling signatures with the OpenCode API.

---

## Task 5: Metrics and Observability Hook Up

**Files:**
- Modify: `src/strands_worker.py`

- [ ] **Step 1: Tie Strands tool events to Prometheus metrics**  
Open `src/strands_worker.py` and import the event listeners from Strands along with your global metrics collectors:
```python
from strands.hooks import AfterToolCallEvent

def instrument_strands_agent(agentInstance):
    def record_metrics(event: AfterToolCallEvent):
        # Intercept every background tool execution seamlessly
        from src.observability import record_mcp_tool_call
        record_mcp_tool_call(
            name=event.tool.name, 
            success=event.success, 
            duration=event.duration_seconds
        )
    agentInstance.hooks.add_listener(AfterToolCallEvent, record_metrics)
```

- [ ] **Step 2: Call the instrumenter right after Agent creation**
Ensure `instrument_strands_agent(agent)` executes immediately before `agent(...)` runs inside the worker's thread path.

---

## Task 6: Smoke Testing & Verification

- [ ] **Step 1: Validate component tests**
Verify that the FSM transitions handle the autonomous thinking states perfectly, and run the dedicated response cache tests to make sure pool insertion is unaffected:
```bash
py -m pytest tests/test_fsm.py tests/test_animator.py tests/test_response_manager.py tests/test_response_pool.py -v
```

- [ ] **Step 2: Run application live**  
Launch Daemon with logging enabled to observe the tool-trajectories tracking live:
```bash
py daemon.py --verbose
```

- [ ] **Step 3: Check Prometheus endpoint metrics exposition**
Hit `http://127.0.0.1:4097/metrics` and verify that background tool call latencies match up perfectly.
