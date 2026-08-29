import asyncio
import json
import logging
import os
import re
import time
import ctypes
from PyQt6.QtCore import QThread, pyqtSignal
from mcp.server.fastmcp import FastMCP
from functools import lru_cache, wraps

from src.utils.security import get_safe_data_path
logger = logging.getLogger(__name__)


def _log_tool_call(func):
    """Debug-log every MCP tool invocation with its tool name.

    Applied to all ``_handle_*`` tool implementations via the auto-instrumentation
    loop below so tool calls are identifiable in the logs without per-tool boilerplate.
    """
    tool_name = func.__name__
    if tool_name.startswith("_handle_"):
        tool_name = tool_name[len("_handle_"):]

    @wraps(func)
    def wrapper(*args, **kwargs):
        logger.debug("[MCP] Tool called: %s", tool_name)
        return func(*args, **kwargs)
    return wrapper


_PROJECT_ROOT = None
def _get_project_root():
    global _PROJECT_ROOT
    if _PROJECT_ROOT is None:
        from pathlib import Path
        _PROJECT_ROOT = Path(__file__).parent.parent.resolve()
    return _PROJECT_ROOT

PROJECT_ROOT = _get_project_root()

ALLOWED_READ_EXTENSIONS = {".py", ".md", ".json", ".ps1", ".txt", ".log", ".yaml", ".yml"}
MAX_READ_LINES = 500
_FILE_CACHE = {}
_FILE_CACHE_TTL = 10  # seconds
_FILE_CACHE_MAX_ENTRIES = 50
_CACHE_TIMESTAMPS = {}


def _evict_stale_file_cache() -> None:
    now = time.time()
    stale = [k for k, ts in _CACHE_TIMESTAMPS.items() if now - ts > _FILE_CACHE_TTL]
    for k in stale:
        _FILE_CACHE.pop(k, None)
        _CACHE_TIMESTAMPS.pop(k, None)
    if len(_FILE_CACHE) > _FILE_CACHE_MAX_ENTRIES:
        oldest = sorted(_CACHE_TIMESTAMPS, key=_CACHE_TIMESTAMPS.get)
        for k in oldest[:len(_FILE_CACHE) - _FILE_CACHE_MAX_ENTRIES]:
            _FILE_CACHE.pop(k, None)
            _CACHE_TIMESTAMPS.pop(k, None)
def _validate_mcp_path(relative_path: str, root: str = PROJECT_ROOT) -> str:
    abs_root = os.path.normpath(os.path.abspath(root))
    normed = os.path.normpath(os.path.join(abs_root, relative_path))
    if not normed.startswith(abs_root):
        raise ValueError(f"Path traversal blocked: {relative_path}")
    return normed
def _validate_read_extension(file_path: str) -> bool:
    _, ext = os.path.splitext(file_path)
    return ext.lower() in ALLOWED_READ_EXTENSIONS

# FSM actions (state machine for pet animations)
FSM_ACTIONS = frozenset({
    "idle", "wander", "hyper", "celebrate", "devastated", "fall", "chase"
})

EXPRESSION_ACTIONS = frozenset({
    "float", "jump", "grow", "shrink", "pulse", "glitch", "rainbow",
    "flip", "teleport", "wave", "wobble", "dash", "melt", "inflate",
    "nod", "headshake", "tremble", "strut", "flail", "vanish",
    "shake", "bounce", "spin", "look_away",
})

VALID_ACTIONS = FSM_ACTIONS | EXPRESSION_ACTIONS
# Consent mapping for intrusive tools
CONSENT_TOOL_MAP = {
    "change_visual_state": "allow_intrusive_animations",
    "read_clipboard": "allow_clipboard_hijacking",
    "capture_blackmail_evidence": "allow_window_management",
    "send_system_toast": "allow_audio_disruptions",
    "simulate_keystroke": "allow_keyboard_injection",
    "move_mouse": "allow_mouse_interference",
    "browser_navigation": "allow_browser_redirection",
    "get_screen_context": "allow_window_management",
    "get_browser_context": "allow_browser_redirection",
    "execute_os_action": "allow_window_management",
    "trigger_pet_animation": "allow_intrusive_animations",
    "uia_interact_element": "allow_window_management",
    "vision_capture_screen": "allow_window_management",
    "vision_click_coordinate": "allow_mouse_interference",
}
FEATURE_TOOL_MAP = {
    "change_visual_state": "pet_interaction",
    "trigger_pet_animation": "pet_interaction",
    "read_clipboard": "desktop_interaction",
    "capture_blackmail_evidence": "desktop_interaction",
    "get_screen_context": "desktop_interaction",
    "get_browser_context": "desktop_interaction",
    "uia_get_window_tree": "desktop_interaction",
    "uia_interact_element": "desktop_interaction",
    "vision_capture_screen": "desktop_interaction",
    "vision_click_coordinate": "desktop_interaction",
    "lsp_get_diagnostics": "code_intelligence",
    "lsp_get_symbol_info": "code_intelligence",
    "query_semantic_memory": "memory_sync",
}
# Submit function for Pyodide compatibility
def mcp_submit(event: str, data: dict = None) -> None:
    """Send an event to the event system (Pyodide compatibility)."""
    from src.events import submit_event
    from src.constants import EVENT_KEY

    if data is None:
        data = {}
    data[EVENT_KEY] = event
    submit_event(data)
class MCPServerThread(QThread):
    """QThread wrapper for FastMCP SSE server."""
    def __init__(self, memory=None, diary_store=None, history=None, config=None,
                 fsm_bridge=None, action_layer=None, features=None):
        super().__init__()
        self._memory = memory
        self._diary_store = diary_store
        self._history = history
        self._config = config
        self._fsm_bridge = fsm_bridge
        self._action_layer = action_layer
        self._features = features or {}
        self._server = None
        self._uvicorn_server = None
        self._stop_event = False
        logger.info("MCPServerThread initialized")

    def run(self):
        """Start the FastMCP SSE server."""
        logger.info("Starting FastMCP SSE server thread")
        try:
            import pythoncom
            pythoncom.CoInitialize()
        except ImportError:
            logger.debug("pythoncom not available, continuing without CoInitialize")

        app = _create_fastmcp_app(self)
        self._server = app
        import uvicorn
        config = uvicorn.Config(
            app.sse_app(), host="127.0.0.1", port=4097, log_level="error"
        )
        self._uvicorn_server = uvicorn.Server(config)
        try:
            logger.info("Starting FastMCP SSE server on port 4097")
            self._uvicorn_server.run()
        except Exception as e:
            logger.error("FastMCP SSE server error: %s", e)
            raise
        finally:
            try:
                import pythoncom
                pythoncom.CoUninitialize()
            except (AttributeError, ImportError):
                pass

    def stop(self):
        """Stop the FastMCP SSE server."""
        logger.info("Stopping FastMCP SSE server")
        server = getattr(self, "_uvicorn_server", None)
        if server is not None:
            server.should_exit = True
        self._server = None
        self._stop_event = True


def _create_fastmcp_app(server_thread):
    """Create the FastMCP app with all tools registered."""
    app = FastMCP("DaemonMCP", host="127.0.0.1", port=4097)

    @app.tool()
    def change_visual_state(action: str, layer: str, duration_ms: int = None, target_x: int = None, target_y: int = None) -> dict:
        """Change Daemon's visual animation state."""
        return _handle_change_visual_state(server_thread, action, layer, duration_ms, target_x, target_y)

    @app.tool()
    def read_clipboard() -> dict:
        """Read whatever the user has copied to their clipboard."""
        return _handle_read_clipboard(server_thread)

    @app.tool()
    def capture_blackmail_evidence() -> dict:
        """Take a full-screen screenshot and save as evidence."""
        return _handle_capture_blackmail_evidence(server_thread)

    @app.tool()
    def send_system_toast(title: str, message: str) -> dict:
        """Send a native Windows OS desktop notification."""
        return _handle_send_system_toast(server_thread, title, message)

    @app.tool()
    def list_directory(relative_path: str) -> dict:
        """List files and directories within the Daemon project root."""
        return _handle_list_directory(server_thread, relative_path)

    @app.tool()
    def read_file(file_path: str, start_line: int = None, end_line: int = None) -> dict:
        """Read a source file from the Daemon project."""
        return _handle_read_file(server_thread, file_path, start_line, end_line)

    @app.tool()
    def search_codebase(search_term: str) -> dict:
        """Search for a symbol across Python files in src/ and tests/."""
        return _handle_search_codebase(server_thread, search_term)

    @app.tool()
    def get_memory() -> dict:
        """Read all memory facts Daemon knows about the user."""
        return _handle_get_memory(server_thread)

    @app.tool()
    def get_diary(limit: int = 10) -> dict:
        """Read recent diary entries."""
        return _handle_get_diary(server_thread, limit)

    @app.tool()
    def simulate_keystroke(keys: str) -> dict:
        """Type a string of characters as if the user typed them."""
        return _handle_simulate_keystroke(server_thread, keys)

    @app.tool()
    def move_mouse(x: int, y: int, click: bool = False) -> dict:
        """Move the cursor to a screen position."""
        return _handle_move_mouse(server_thread, x, y, click)

    @app.tool()
    def browser_navigation(url: str) -> dict:
        """Open a URL in the default web browser."""
        return _handle_browser_navigation(server_thread, url)

    @app.tool()
    def set_log_level(level: str) -> dict:
        """Change the root logger level at runtime."""
        return _handle_set_log_level(server_thread, level)

    @app.tool()
    def get_screen_time() -> dict:
        """Get today's screen time usage per application."""
        return _handle_get_screen_time(server_thread)

    @app.tool()
    def get_recent_git_diff() -> dict:
        """Get the git diff of the currently staged files."""
        return _handle_get_recent_git_diff(server_thread)

    @app.tool()
    def set_reminder(message: str, time_minutes: int) -> dict:
        """Set a reminder that will emit a system toast and pet bubble after a given time."""
        return _handle_set_reminder(server_thread, message, time_minutes)

    @app.tool()
    def get_reminders() -> dict:
        """List all currently active reminders."""
        return _handle_get_reminders(server_thread)

    @app.tool()
    def dismiss_reminder(id: str) -> dict:
        """Dismiss/cancel an active reminder by ID."""
        return _handle_dismiss_reminder(server_thread, id)

    @app.tool()
    def query_memory(type: str, keyword: str = None, limit: int = 20) -> dict:
        """Query any of Daemon's persistent stores."""
        return _handle_query_memory(server_thread, type, keyword, limit)

    @app.tool()
    def query_semantic_memory(query: str, limit: int = 5) -> dict:
        """Search indexed memory and diary records by semantic similarity."""
        retriever = getattr(server_thread, "_rag_retriever", None)
        if retriever is None:
            return {"error": "Semantic memory is not configured"}
        return retriever.retrieve(query, limit)

    @app.tool()
    def get_screen_context() -> dict:
        """Returns pruned UIA XML (depth 7) from the active window."""
        return _handle_get_screen_context(server_thread)

    @app.tool()
    def get_browser_context() -> dict:
        """Detect browser window and extract URL."""
        return _handle_get_browser_context(server_thread)

    @app.tool()
    def execute_os_action(action: str, x: int, y: int, text: str, use_clipboard: bool) -> dict:
        """Consent-gated OS control."""
        return _handle_execute_os_action(server_thread, action, x, y, text, use_clipboard)

    @app.tool()
    def trigger_pet_animation(state: str) -> dict:
        """Map to pet FSM action or expression animation."""
        return _handle_trigger_pet_animation(server_thread, state)

    @app.tool()
    def uia_get_window_tree(window_handle: int = None, max_depth: int = 3) -> dict:
        """Return a semantic UI Automation tree for a Windows application."""
        return _handle_uia_get_window_tree(server_thread, window_handle, max_depth)

    @app.tool()
    def uia_interact_element(
        query: dict,
        action: str,
        text: str = None,
        window_handle: int = None,
    ) -> dict:
        """Operate a Windows control through a semantic UI Automation pattern."""
        return _handle_uia_interact_element(
            server_thread, query, action, text, window_handle
        )

    @app.tool()
    def vision_capture_screen(
        region: list[int] = None, add_grid: bool = True, add_som: bool = False
    ) -> dict:
        """Capture the screen with optional coordinate grid metadata."""
        return _handle_vision_capture_screen(server_thread, region, add_grid, add_som)

    @app.tool()
    def vision_click_coordinate(
        x: int,
        y: int,
        click_type: str = "left",
        smooth: bool = True,
        duration: float = 0.3,
    ) -> dict:
        """Move and click at a consent-approved screen coordinate."""
        return _handle_vision_click_coordinate(
            server_thread, x, y, click_type, smooth, duration
        )

    @app.tool()
    def lsp_get_diagnostics(path: str = None) -> dict:
        """Return diagnostics collected from the configured language server."""
        return _handle_lsp_get_diagnostics(server_thread, path)

    @app.tool()
    def lsp_get_symbol_info(path: str, line: int, column: int) -> dict:
        """Return definitions and references for a source position."""
        return _handle_lsp_get_symbol_info(server_thread, path, line, column)

    return app
def _is_tool_allowed(server_thread, tool_name: str) -> tuple[bool, str]:
    """Check consent for *tool_name*. Returns (allowed, error_message)."""
    if server_thread is None:
        return True, ""
    config = getattr(server_thread, "_config", None)
    if config is None:
        return True, ""

    feature_key = FEATURE_TOOL_MAP.get(tool_name)
    if feature_key is not None and not getattr(server_thread, "_features", {}).get(feature_key, True):
        msg = f"ERROR: User has disabled feature 'features.{feature_key}'. Tool '{tool_name}' blocked."
        logger.info("MCP feature disabled: %s (%s)", tool_name, feature_key)
        return False, msg

    consent_key = CONSENT_TOOL_MAP.get(tool_name)
    if consent_key is None:
        return True, ""

    allowed = config.get(consent_key, False)
    if not allowed:
        msg = f"ERROR: User has denied permission '{consent_key}'. Tool '{tool_name}' blocked."
        logger.warning("MCP Blocked: LLM attempted '%s' but '%s' is False", tool_name, consent_key)
        return False, msg
    return True, ""

def extract_consent_config(nested_config: dict | None) -> dict:
    """Return the 'consent' sub-dict from a nested daemon config (never None)."""
    if not nested_config:
        return {}
    return nested_config.get("consent", {}) or {}

def _handle_change_visual_state(server_thread, action: str, layer: str, duration_ms: int, target_x: int, target_y: int) -> dict:
    """Handle change_visual_state tool call."""
    allowed, err = _is_tool_allowed(server_thread, "change_visual_state")
    if not allowed:
        return {"content": [{"type": "text", "text": err}]}

    if action not in VALID_ACTIONS:
        return {"content": [{"type": "text", "text": f"Invalid action: {action}. Valid actions: {sorted(VALID_ACTIONS)}"}]}
    if layer not in ("fsm", "expression"):
        return {"content": [{"type": "text", "text": f"Invalid layer: {layer}"}]}

    # Auto-correct layer if action belongs exclusively to the other layer
    if layer == "fsm" and action not in FSM_ACTIONS and action in EXPRESSION_ACTIONS:
        logger.warning("Auto-corrected action '%s' from fsm->expression layer", action)
        layer = "expression"
    elif layer == "expression" and action not in EXPRESSION_ACTIONS and action in FSM_ACTIONS:
        logger.warning("Auto-corrected action '%s' from expression->fsm layer", action)
        layer = "fsm"

    # Dispatch to the correct handler
    if layer == "fsm":
        if action not in FSM_ACTIONS:
            return {"content": [{"type": "text", "text": f"Action '{action}' is not valid for fsm layer. Valid FSM actions: {sorted(FSM_ACTIONS)}"}]}
        if server_thread._fsm_bridge:
            server_thread._fsm_bridge.fsm_action_requested.emit(action)
    else:
        if action not in EXPRESSION_ACTIONS:
            return {"content": [{"type": "text", "text": f"Action '{action}' is not valid for expression layer. Valid expression actions: {sorted(EXPRESSION_ACTIONS)}"}]}
        if server_thread._action_layer:
            server_thread._action_layer.trigger(action, duration_ms, {})

    return {"content": [{"type": "text", "text": "ok"}]}
def _handle_read_clipboard(server_thread) -> dict:
    """Handle read_clipboard tool call."""
    allowed, err = _is_tool_allowed(server_thread, "read_clipboard")
    if not allowed:
        return {"content": [{"type": "text", "text": err}]}

    return _read_clipboard()
def _handle_capture_blackmail_evidence(server_thread) -> dict:
    """Handle capture_blackmail_evidence tool call."""
    allowed, err = _is_tool_allowed(server_thread, "capture_blackmail_evidence")
    if not allowed:
        return {"content": [{"type": "text", "text": err}]}

    return _capture_blackmail_evidence()
def _handle_send_system_toast(server_thread, title: str, message: str) -> dict:
    """Handle send_system_toast tool call."""
    allowed, err = _is_tool_allowed(server_thread, "send_system_toast")
    if not allowed:
        return {"content": [{"type": "text", "text": err}]}

    if server_thread._fsm_bridge:
        server_thread._fsm_bridge.emit_toast(title, message)
    return {"content": [{"type": "text", "text": "toast sent"}]}
def _handle_list_directory(server_thread, relative_path: str) -> dict:
    """Handle list_directory tool call."""
    return _list_directory(relative_path)
def _handle_read_file(server_thread, file_path: str, start_line: int, end_line: int) -> dict:
    """Handle read_file tool call."""
    return _read_file(file_path, start_line, end_line)
def _handle_search_codebase(server_thread, search_term: str) -> dict:
    """Handle search_codebase tool call."""
    return _search_codebase(server_thread, search_term)
def _handle_get_memory(server_thread) -> dict:
    """Handle get_memory tool call."""
    if server_thread._memory is None:
        text = "Memory not available (no memory store configured)"
    else:
        facts = server_thread._memory.get_all()
        if not facts:
            text = "No memory facts stored."
        else:
            lines = [f"{k}: {v}" for k, v in facts.items()]
            text = "Memory facts:\n" + "\n".join(lines)
    logger.debug("MCP get_memory -> %d chars", len(text))
    return {"content": [{"type": "text", "text": text}]}
def _handle_get_diary(server_thread, limit: int) -> dict:
    """Handle get_diary tool call."""
    if server_thread._diary_store is None:
        text = "Diary not available (no diary store configured)"
    else:
        entries = server_thread._diary_store.get_entries()
        if not entries:
            text = "No diary entries."
        else:
            recent = entries[-limit:]
            lines = []
            for e in recent:
                ts = e.get("timestamp", "")
                content = e.get("content", "")
                lines.append(f"[{ts}] {content}")
            text = "Recent diary entries:\n" + "\n".join(lines)
    logger.debug("MCP get_diary -> %d chars", len(text))
    return {"content": [{"type": "text", "text": text}]}
def _handle_simulate_keystroke(server_thread, keys: str) -> dict:
    """Handle simulate_keystroke tool call."""
    allowed, err = _is_tool_allowed(server_thread, "simulate_keystroke")
    if not allowed:
        return {"content": [{"type": "text", "text": err}]}

    return _simulate_keystroke(keys)
def _handle_move_mouse(server_thread, x: int, y: int, click: bool) -> dict:
    """Handle move_mouse tool call."""
    allowed, err = _is_tool_allowed(server_thread, "move_mouse")
    if not allowed:
        return {"content": [{"type": "text", "text": err}]}

    return _move_mouse(x, y, click)
def _handle_browser_navigation(server_thread, url: str) -> dict:
    """Handle browser_navigation tool call."""
    allowed, err = _is_tool_allowed(server_thread, "browser_navigation")
    if not allowed:
        return {"content": [{"type": "text", "text": err}]}

    return _browser_navigation(url)
def _handle_set_log_level(server_thread, level: str) -> dict:
    """Handle set_log_level tool call."""
    level_str = level.upper()
    import logging as _logging
    level_map = {"DEBUG": _logging.DEBUG, "INFO": _logging.INFO, "WARNING": _logging.WARNING,
                 "ERROR": _logging.ERROR, "CRITICAL": _logging.CRITICAL}
    level_val = level_map.get(level_str)
    if level_val is None:
        return {"content": [{"type": "text", "text": f"Invalid level: {level_str}"}]}

    _logging.getLogger("src").setLevel(level_val)
    logger.info("Daemon 'src' namespace logger level set to %s by MCP tool", level_str)
    return {"content": [{"type": "text", "text": f"Log level set to {level_str}"}]}
def _handle_get_screen_time(server_thread) -> dict:
    """Handle get_screen_time tool call."""
    from src.persistence import load_state
    state = load_state()
    screen_time = state.get("screen_time", {})
    return {"content": [{"type": "text", "text": json.dumps(screen_time, indent=2)}]}
def _handle_get_recent_git_diff(server_thread) -> dict:
    """Handle get_recent_git_diff tool call."""
    import subprocess
    try:
        # First try to get staged diff
        diff = subprocess.check_output(["git", "diff", "--cached"], stderr=subprocess.STDOUT, text=True).strip()
        if not diff:
            # If empty, try un-staged diff
            diff = subprocess.check_output(["git", "diff"], stderr=subprocess.STDOUT, text=True).strip()
        if not diff:
            # If still empty, get last commit diff
            diff = subprocess.check_output(["git", "show", "--stat", "-p", "HEAD"], stderr=subprocess.STDOUT, text=True).strip()
        # Truncate if too long
        if len(diff) > 4000:
            diff = diff[:4000] + "\n...[truncated]"
        return {"content": [{"type": "text", "text": diff}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error: {str(e)}"}]}
def _handle_set_reminder(server_thread, message: str, time_minutes: int) -> dict:
    """Handle set_reminder tool call."""
    import concurrent.futures
    future = concurrent.futures.Future()
    data = {"message": message, "time_minutes": time_minutes, "future": future}
    server_thread._fsm_bridge.reminder_request.emit("set", data)
    rem_id = future.result(timeout=2.0)
    return {"content": [{"type": "text", "text": f"Reminder set with ID: {rem_id}"}]}
def _handle_get_reminders(server_thread) -> dict:
    """Handle get_reminders tool call."""
    import concurrent.futures
    future = concurrent.futures.Future()
    server_thread._fsm_bridge.reminder_request.emit("get", {"future": future})
    active = future.result(timeout=2.0)
    return {"content": [{"type": "text", "text": json.dumps(active, indent=2)}]}
def _handle_dismiss_reminder(server_thread, id: str) -> dict:
    """Handle dismiss_reminder tool call."""
    import concurrent.futures
    future = concurrent.futures.Future()
    data = {"id": id, "future": future}
    server_thread._fsm_bridge.reminder_request.emit("dismiss", data)
    success = future.result(timeout=2.0)
    if success:
        return {"content": [{"type": "text", "text": f"Reminder {id} dismissed"}]}
    else:
        return {"content": [{"type": "text", "text": f"Error: Reminder ID not found"}]}
def _handle_query_memory(server_thread, type: str, keyword: str, limit: int) -> dict:
    """Handle query_memory tool call."""
    store_type = type
    keyword = keyword.lower() if keyword else ""
    limit = min(int(limit), 50)

    backend_map = {
        "memory": server_thread._memory,
        "diary": server_thread._diary_store,
        "history": server_thread._history,
    }
    if store_type not in backend_map:
        return {"content": [{"type": "text", "text": f"Unknown type: {store_type!r}"}]}

    backend = backend_map[store_type]
    if backend is None:
        return {"content": [{"type": "text", "text": f"Store type '{store_type}' is not configured/available."}]}

    # Query logic for each store
    if store_type == "memory":
        all_items = list(backend.get_all().items())
        if keyword:
            filtered = [(k, v) for k, v in all_items if keyword in v.lower()]
        else:
            filtered = all_items
        entries = [{"content": f"{k}: {v}", "timestamp": "", "type": "memory"} for k, v in filtered[:limit]]
    elif store_type == "diary":
        all_items = backend.get_entries()
        if keyword:
            filtered = [item for item in all_items if keyword in item.get("content", "").lower()]
        else:
            filtered = all_items
        entries = filtered[:limit]
    elif store_type == "history":
        all_items = backend.get_entries()
        if keyword:
            filtered = [item for item in all_items if keyword in item.get("content", "").lower()]
        else:
            filtered = all_items
        entries = filtered[:limit]

    return {"content": [{"type": "text", "text": json.dumps(entries, indent=2)}]}
def _handle_get_screen_context(server_thread) -> dict:
    """Handle get_screen_context tool call."""
    allowed, err = _is_tool_allowed(server_thread, "get_screen_context")
    if not allowed:
        return {"content": [{"type": "text", "text": err}]}

    # Import here to avoid circular imports
    from src.screen_reader import ScreenReader

    reader = ScreenReader()
    text = reader.get_foreground_text()
    # Extract basic context from UI Automation
    result = f"Screen context: {text[:1000]}"
    return {"content": [{"type": "text", "text": result}]}
def _handle_get_browser_context(server_thread) -> dict:
    """Handle get_browser_context tool call."""
    allowed, err = _is_tool_allowed(server_thread, "get_browser_context")
    if not allowed:
        return {"content": [{"type": "text", "text": err}]}

    # Import here to avoid circular imports
    from src.screen_reader import get_browser_url_via_uia

    url = get_browser_url_via_uia()
    if url:
        return {"content": [{"type": "text", "text": json.dumps({"url": url})}]}
    else:
        return {"content": [{"type": "text", "text": json.dumps({"url": None})}]}
def _handle_execute_os_action(server_thread, action: str, x: int, y: int, text: str, use_clipboard: bool) -> dict:
    """Handle execute_os_action tool call."""
    # Check consent for window management if action requires it
    allowed, err = _is_tool_allowed(server_thread, "execute_os_action")
    if not allowed:
        return {"content": [{"type": "text", "text": err}]}

    # Try to execute the action
    try:
        import pywintypes
        from pywinauto import Application

        # Get the active window
        app = Application().connect(active_only=True)
        window = app.active_window()

        if action == "click":
            window.click_input(coords=(x, y))
            result = f"Clicked at ({x}, {y})"
        elif action == "type":
            window.type_keys(text)
            result = f"Typed '{text}'"
        elif action == "right_click":
            window.right_click_input(coords=(x, y))
            result = f"Right-clicked at ({x}, {y})"
        elif action == "drag":
            window.drag_mouse(coords_start=(x, y), coords_end=(x + 50, y + 50))
            result = f"Dragged from ({x}, {y})"
        else:
            return {"content": [{"type": "text", "text": f"Error: Unknown action '{action}'"}]}

        return {"content": [{"type": "text", "text": result}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error executing action '{action}': {str(e)}"}]}
def _handle_trigger_pet_animation(server_thread, state: str) -> dict:
    """Handle trigger_pet_animation tool call."""
    allowed, err = _is_tool_allowed(server_thread, "trigger_pet_animation")
    if not allowed:
        return {"content": [{"type": "text", "text": err}]}

    # Map UI states to FSM actions
    FSM_TO_ACTION = {
        "IDLE": "idle",
        "THINKING": "wander",
        "FRUSTRATED": "hyper",
        "SMUG": "celebrate",
        "SHOCKED": "devastated",
        "LAUGHING": "fall",
    }

    # Check if it's a valid FSM state
    if state.upper() in FSM_TO_ACTION:
        action = FSM_TO_ACTION[state.upper()]
        if server_thread._fsm_bridge:
            server_thread._fsm_bridge.fsm_action_requested.emit(action)
            return {"content": [{"type": "text", "text": f"Triggered FSM action: {action}"}]}
    elif state in EXPRESSION_ACTIONS:
        if server_thread._action_layer:
            server_thread._action_layer.trigger(state, duration_ms=None, params={})
            return {"content": [{"type": "text", "text": f"Triggered expression animation: {state}"}]}
    else:
        return {"content": [{"type": "text", "text": f"Error: Invalid state '{state}'. Valid FSM states: {list(FSM_TO_ACTION.keys())}. Valid expression actions: {sorted(EXPRESSION_ACTIONS)}"}]}
    return {"content": [{"type": "text", "text": f"State '{state}' handled"}]}


def _handle_uia_get_window_tree(
    server_thread, window_handle: int | None, max_depth: int
) -> dict:
    """Handle the read-only UIA tree inspection tool."""
    from src.system.uia_navigator import UIANavigator

    result = UIANavigator().dump_tree(window_handle, max_depth)
    return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}


def _handle_uia_interact_element(
    server_thread,
    query: dict,
    action: str,
    text: str | None,
    window_handle: int | None,
) -> dict:
    """Handle consent-gated semantic UIA interaction."""
    allowed, err = _is_tool_allowed(server_thread, "uia_interact_element")
    if not allowed:
        return {"content": [{"type": "text", "text": err}]}

    from src.system.uia_navigator import UIANavigator

    result = UIANavigator().invoke_element(window_handle, query, action, text)
    return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}


def _handle_vision_capture_screen(
    server_thread, region: list[int] | None, add_grid: bool, add_som: bool
) -> dict:
    """Handle consent-gated screen capture."""
    allowed, err = _is_tool_allowed(server_thread, "vision_capture_screen")
    if not allowed:
        return {"content": [{"type": "text", "text": err}]}
    from src.system.vision_controller import VisionController

    normalized = tuple(region) if region is not None else None
    result = VisionController().capture_screen(normalized, add_grid, add_som)
    return {"content": [{"type": "text", "text": json.dumps(result)}]}


def _handle_vision_click_coordinate(
    server_thread,
    x: int,
    y: int,
    click_type: str,
    smooth: bool,
    duration: float,
) -> dict:
    """Handle consent-gated coordinate interaction."""
    allowed, err = _is_tool_allowed(server_thread, "vision_click_coordinate")
    if not allowed:
        return {"content": [{"type": "text", "text": err}]}
    from src.system.vision_controller import VisionController

    result = VisionController().click_coordinate(x, y, click_type, smooth, duration)
    return {"content": [{"type": "text", "text": json.dumps(result)}]}


def _get_lsp_client(server_thread):
    client = getattr(server_thread, "_lsp_client", None)
    if client is None:
        return None
    if not client.running:
        client.start()
    return client


def _handle_lsp_get_diagnostics(server_thread, path: str | None) -> dict:
    client = _get_lsp_client(server_thread)
    if client is None:
        return {"content": [{"type": "text", "text": json.dumps({"error": "LSP is not configured"})}]}
    result = client.get_diagnostics(path)
    return {"content": [{"type": "text", "text": json.dumps(result)}]}


def _handle_lsp_get_symbol_info(server_thread, path: str, line: int, column: int) -> dict:
    client = _get_lsp_client(server_thread)
    if client is None:
        return {"content": [{"type": "text", "text": json.dumps({"error": "LSP is not configured"})}]}
    result = client.symbol_info(path, line, column)
    return {"content": [{"type": "text", "text": json.dumps(result)}]}


# ── Tool call instrumentation ──────────────────────────────────────────────
# Auto-wrap every MCP tool handler with entry debug logging so tool calls are
# identifiable in the logs. Runs once at import, after all _handle_* definitions.
for _name, _func in list(globals().items()):
    if _name.startswith("_handle_") and callable(_func):
        globals()[_name] = _log_tool_call(_func)


# Legacy tool implementations (copied from old mcp_server.py)
def _read_clipboard() -> dict:
    """Read UTF-16 text from the Windows clipboard.

    Returns "Clipboard: <text>" on success, or a descriptive string on failure.
    CloseClipboard() is guaranteed to execute via finally block.
    """
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.GetClipboardData.argtypes = [wintypes.UINT]
    user32.GetClipboardData.restype = wintypes.HANDLE
    user32.CloseClipboard.argtypes = []
    user32.CloseClipboard.restype = wintypes.BOOL

    CF_UNICODETEXT = 13
    if not user32.OpenClipboard(None):
        return {"content": [{"type": "text", "text": "Clipboard: (locked by another application)"}]}

    try:
        handle = user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return {"content": [{"type": "text", "text": "Clipboard: (empty or non-text data)"}]}
        kernel32 = ctypes.windll.kernel32
        kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
        kernel32.GlobalLock.restype = wintypes.LPVOID
        kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
        kernel32.GlobalUnlock.restype = wintypes.BOOL

        ptr = kernel32.GlobalLock(handle)
        if not ptr:
            return {"content": [{"type": "text", "text": "Clipboard: (failed to lock)"}]}
        try:
            length = kernel32.lstrlenW(ctypes.c_wchar_p(ptr))
            text = ctypes.wstring_at(ptr, length)
            return {"content": [{"type": "text", "text": f"Clipboard: {text}"}]}
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()
def _capture_blackmail_evidence() -> dict:
    """Capture a full-screen screenshot, save to data/blackmail/, return message."""
    from PIL import ImageGrab
    from datetime import datetime
    from src.utils.security import get_safe_data_path

    screenshot = ImageGrab.grab()
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"evidence_{ts}.png"
    path = get_safe_data_path(os.path.join("blackmail", filename))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    screenshot.save(path)
    return {"content": [{"type": "text", "text": f"Evidence saved to {path}"}]}
_MAX_KEYSTROKE_LEN = 50
_BLOCKED_KEYS = {"win", "cmd", "super", "win_l", "win_r", "cmd_l", "cmd_r", "super_l", "super_r"}
def _simulate_keystroke(keys: str) -> dict:
    """Type *keys* using pynput keyboard controller. Max 50 chars.
    Blocks Windows/super modifier keys. Returns status string."""
    from pynput.keyboard import Controller

    lower = keys.lower()
    for bk in _BLOCKED_KEYS:
        if bk in lower:
            return {"content": [{"type": "text", "text": "Error: Windows key is blocked for safety"}]}
    if len(keys) > _MAX_KEYSTROKE_LEN:
        return {"content": [{"type": "text", "text": f"Error: Payload too large ({len(keys)} chars, max {_MAX_KEYSTROKE_LEN})"}]}
    kb = Controller()
    kb.type(keys)
    return {"content": [{"type": "text", "text": f"Typed {len(keys)} characters"}]}

def _move_mouse(x: int, y: int, click: bool = False) -> dict:
    """Move cursor to (x, y) using pynput mouse controller.
    Clamps coordinates to display bounds. Optionally left-clicks.
    Returns status string."""
    from pynput.mouse import Controller, Button

    import ctypes
    w = ctypes.windll.user32.GetSystemMetrics(0)
    h = ctypes.windll.user32.GetSystemMetrics(1)
    cx = max(0, min(x, w - 1))
    cy = max(0, min(y, h - 1))
    mouse = Controller()
    mouse.position = (cx, cy)
    if click:
        mouse.click(Button.left)
    return {"content": [{"type": "text", "text": f"Moved cursor to ({cx}, {cy})" + (" and clicked" if click else "")}]}

def _browser_navigation(url: str) -> dict:
    """Open *url* in default browser. Only http:// and https:// allowed.
    Returns status string."""
    import webbrowser

    lower = url.strip().lower()
    if not (lower.startswith("http://") or lower.startswith("https://")):
        return {"content": [{"type": "text", "text": "Error: Only http:// and https:// URLs are allowed"}]}
    webbrowser.open(url.strip())
    return {"content": [{"type": "text", "text": f"Opened {url.strip()}"}]}
def _list_directory(relative_path: str) -> dict:
    """List files and directories within the Daemon project root. Returns a structured JSON list with type (file/directory) and size for files."""
    try:
        abs_path = _validate_mcp_path(relative_path)
    except ValueError as e:
        return {"content": [{"type": "text", "text": json.dumps({"error": str(e)})}]}
    if not os.path.exists(abs_path):
        return {"content": [{"type": "text", "text": json.dumps({"error": f"Path not found: {relative_path}"})}]}
    if not os.path.isdir(abs_path):
        return {"content": [{"type": "text", "text": json.dumps({"error": f"Not a directory: {relative_path}"})}]}
    entries = []
    for entry in sorted(os.listdir(abs_path)):
        full = os.path.join(abs_path, entry)
        if os.path.isdir(full):
            entries.append({"name": entry, "type": "directory"})
        else:
            try:
                size = os.path.getsize(full)
            except OSError:
                size = 0
            entries.append({"name": entry, "type": "file", "size": size})
    return {"content": [{"type": "text", "text": json.dumps(entries, indent=2)}]}
def _read_file(file_path: str, start_line: int, end_line: int) -> dict:
    """Read a source file from the Daemon project. Limited to allowed extensions (.py, .md, .json, .ps1, .txt, .log, .yaml) and max 500 lines."""
    if not _validate_read_extension(file_path):
        return {"content": [{"type": "text", "text": json.dumps({"error": f"File type not allowed: {file_path}"})}]}
    try:
        abs_path = _validate_mcp_path(file_path)
    except ValueError as e:
        return {"content": [{"type": "text", "text": json.dumps({"error": str(e)})}]}
    if not os.path.exists(abs_path):
        return {"content": [{"type": "text", "text": json.dumps({"error": f"File not found: {file_path}. Use list_directory to find available files."})}]}
    if not os.path.isfile(abs_path):
        return {"content": [{"type": "text", "text": json.dumps({"error": f"Not a file: {file_path}"})}]}

    _evict_stale_file_cache()

    # Check cache
    import time
    cache_key = f"{file_path}:{start_line or 1}:{end_line or 'end'}"
    now = time.time()
    if cache_key in _FILE_CACHE and (now - _CACHE_TIMESTAMPS.get(cache_key, 0)) < _FILE_CACHE_TTL:
        logger.debug("MCP read_file cache hit: %s", file_path)
        return _FILE_CACHE[cache_key]

    try:
        with open(abs_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except UnicodeDecodeError:
        return {"content": [{"type": "text", "text": json.dumps({"error": f"Cannot read binary file: {file_path}"})}]}
    total_lines = len(lines)
    start_idx = max(0, (start_line or 1) - 1)
    end_idx = min(total_lines, end_line) if end_line else min(total_lines, start_idx + MAX_READ_LINES)
    selected = lines[start_idx:end_idx]
    content = "".join(selected)
    header = f"# {file_path} (lines {start_idx + 1}-{end_idx} of {total_lines})\n"
    if end_idx - start_idx >= MAX_READ_LINES:
        content += "\n... (truncated at 500 lines max, use start_line/end_line to paginate)"
    result = {"content": [{"type": "text", "text": header + content}]}

    # Cache the result
    _FILE_CACHE[cache_key] = result
    _CACHE_TIMESTAMPS[cache_key] = now

    return result
def _search_codebase(server_thread, search_term: str) -> dict:
    """Search for a symbol across Python files in src/ and tests/. Returns file paths and line numbers with line snippets."""
    if not search_term:
        return {"content": [{"type": "text", "text": json.dumps({"error": "search_term required"})}]}
    import re

    results = []
    search_dirs = [os.path.join(PROJECT_ROOT, "src"), os.path.join(PROJECT_ROOT, "tests")]
    pattern = re.compile(search_term)
    for search_dir in search_dirs:
        if not os.path.exists(search_dir):
            continue
        for root, dirs, files in os.walk(search_dir):
            dirs[:] = [d for d in dirs if not d.startswith("__") and not d.startswith(".")]
            for file in files:
                if not file.endswith(".py"):
                    continue
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, PROJECT_ROOT)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        for i, line in enumerate(f, 1):
                            if pattern.search(line):
                                results.append({"file": rel_path, "line": i, "snippet": line.strip()[:200]})
                except UnicodeDecodeError:
                    continue
    return {"content": [{"type": "text", "text": json.dumps(results, indent=2)}]}

# Backward-compatible alias for old import
MCPServer = MCPServerThread