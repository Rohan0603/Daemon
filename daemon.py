import sys
import os
import atexit
import faulthandler
import argparse
import logging
import traceback
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from src.constants import STORAGE_DIR, DEBUG, MAX_RESPONSE_CHARS
from src.config import DEFAULT_SERVER_URL

def _resolve_skill_path(pet_id: str) -> Path:
    """Resolve the SKILL.md path for a given pet_id, falling back to kenny if not found."""
    project_root = Path(__file__).parent
    skill_dir = project_root / ".opencode" / "skills" / pet_id
    if not skill_dir.exists():
        skill_dir = project_root / ".opencode" / "skills" / "kenny"
    return skill_dir / "SKILL.md"

logger = logging.getLogger("daemon")

_CRASH_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "crash_dump.log")
_crash_fh = open(_CRASH_LOG, "wb", buffering=0)
faulthandler.enable(file=_crash_fh, all_threads=True)

_original_excepthook = sys.excepthook
def _crash_hook(exc_type, exc_value, exc_tb):
    with open(_CRASH_LOG, "a") as f:
        f.write(f"\n=== UNHANDLED EXCEPTION: {exc_type.__name__} ===\n")
        f.write(f"Message: {exc_value}\n")
        traceback.print_tb(exc_tb, file=f)
        f.write("\n")
    _original_excepthook(exc_type, exc_value, exc_tb)
sys.excepthook = _crash_hook

# Track the active PetWindow reference for atexit emergency flush
_active_pet_window_ref = None


def _emergency_flush(window: "PetWindow | None" = None) -> None:
    """Emergency data flush for atexit — last-resort save on abnormal exit.

    Tries to flush WriteCoalescer and save Memory/History. Silent on any
    failure since the interpreter may be partially torn down.
    """
    if window is None:
        return
    try:
        if hasattr(window, '_write_coalescer'):
            window._write_coalescer.flush()
    except Exception:
        pass
    try:
        if hasattr(window, '_memory'):
            window._memory.save()
    except Exception:
        pass
    try:
        if hasattr(window, '_history'):
            window._history.save()
    except Exception:
        pass


def _ensure_ffmpeg_on_path():
    """Add the winget ffmpeg install directory to PATH if present."""
    ffmpeg_dir = os.path.join(
        os.environ.get("LOCALAPPDATA", ""),
        "Microsoft", "WinGet", "Packages",
    )
    if os.path.isdir(ffmpeg_dir):
        for entry in os.listdir(ffmpeg_dir):
            if entry.lower().startswith("gyan.ffmpeg"):
                bin_dir = os.path.join(ffmpeg_dir, entry, "ffmpeg-8.1.1-essentials_build", "bin")
                if os.path.isdir(bin_dir) and bin_dir not in os.environ.get("PATH", ""):
                    os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")


def _lock_path(pet_id: str) -> Path:
    return STORAGE_DIR / f".daemon_{pet_id}.lock"

def _acquire_lock(pet_id: str) -> bool:
    lock = _lock_path(pet_id)
    if lock.exists():
        try:
            pid = int(lock.read_text().strip())
            import ctypes
            PROCESS_QUERY_LIMITED_INFO = 0x1000
            handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFO, False, pid)
            if handle:
                is_stale = False
                try:
                    from ctypes import wintypes
                    buf = ctypes.create_unicode_buffer(1024)
                    size = wintypes.DWORD(1024)
                    if ctypes.windll.kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                        exe_name = os.path.basename(buf.value).lower()
                        if not any(x in exe_name for x in ("python", "py", "daemon")):
                            is_stale = True
                except Exception:
                    pass
                ctypes.windll.kernel32.CloseHandle(handle)
                if not is_stale:
                    return False
        except Exception:
            pass
    lock.write_text(str(os.getpid()))
    return True


def _release_lock(pet_id: str) -> None:
    lock = _lock_path(pet_id)
    try:
        lock.unlink(missing_ok=True)
    except Exception:
        pass


def main() -> None:
    _ensure_ffmpeg_on_path()
    from src.config import load_config, flatten_config
    import src.constants as constants

    cfg = load_config()
    from src.config import validate_config, MissingConfigurationError
    try:
        validate_config(cfg)
    except MissingConfigurationError as e:
        logger.error(f"Configuration Validation Failed: {e}")
        # Need to spawn Settings UI here
        app = QApplication.instance() or QApplication(sys.argv)
        from src.settings_dialog import SettingsDialog
        dialog = SettingsDialog(
            llm_model_id=cfg.get("llm", {}).get("model_id") or "gemini-2.5-flash",
            llm_api_key=cfg.get("llm", {}).get("api_key", ""),
            llm_server_url=cfg.get("llm", {}).get("server_url") or "http://127.0.0.1:4096",
            firebase_api_key=cfg.get("firebase", {}).get("api_key", ""),
            firebase_project_id=cfg.get("firebase", {}).get("project_id", "")
        )
        result = dialog.exec()
        if result == dialog.DialogCode.Accepted:
            from src.config import save_config
            vals = dialog.get_values()
            save_config({
                "llm": {
                    "model_id": vals["OPENCODE_API_MODEL_ID"],
                    "api_key": vals["OPENCODE_API_KEY"],
                    "server_url": vals["OPENCODE_SERVER_URL"],
                },
                "firebase": {
                    "api_key": vals["FIREBASE_API_KEY"],
                    "project_id": vals["FIREBASE_PROJECT_ID"],
                }
            })
            # User saved, reload config and re-validate
            cfg = load_config()
            try:
                validate_config(cfg)
            except MissingConfigurationError as e2:
                logger.fatal(f"Configuration still invalid after setup: {e2}")
                sys.exit(1)
        else:
            logger.fatal("Setup cancelled by user. Exiting.")
            sys.exit(1)
    flat_cfg = flatten_config(cfg)
    storage_keys = {"MEMORY_PATH", "HISTORY_PATH", "DIARY_PATH", "STATE_PATH",
                    "AUTH_TOKEN_PATH", "RESPONSE_CACHE_PATH", "THOUGHTS_LOG_PATH",
                    "CONFIG_PATH", "FIREBASE_CREDENTIALS_PATH"}
    project_root = os.path.abspath(os.path.dirname(__file__))
    for key, val in flat_cfg.items():
        if hasattr(constants, key):
            # Resolve relative storage paths against project root
            if key in storage_keys and isinstance(val, str) and not os.path.isabs(val):
                val = os.path.normpath(os.path.join(project_root, val))
            setattr(constants, key, val)

    from src.observability import init_observability
    init_observability()

    parser = argparse.ArgumentParser(description="Daemon Desktop Pet")
    parser.add_argument("--debug", action="store_true", help="Run headless FSM simulation")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose debug logging")
    parser.add_argument("--no-opencode", action="store_true", help="Disable opencode integration")
    parser.add_argument("--no-auth", action="store_true", help="Disable Firebase auth login")
    parser.add_argument("--pet-id", type=str, default=None, help="Pet persona ID (default: kenny)")
    args = parser.parse_args()

    pet_id = args.pet_id or cfg["pet"]["id"]
    constants.CURRENT_PET_ID = pet_id

    if not _acquire_lock(pet_id):
        print("Daemon is already running. Exiting.", file=sys.stderr)
        sys.exit(1)

    from src.logging_setup import setup_logging
    log_config = cfg.get("logging", {})
    setup_logging(
        debug=args.verbose,
        log_dir=log_config.get("dir", "logs"),
        json_output=log_config.get("json", False),
        max_bytes=log_config.get("max_bytes", 10 * 1024 * 1024),
        backup_count=log_config.get("backup_count", 5),
        config_overrides=log_config.get("levels"),
    )



    logger.info("=== DAEMON STARTUP (PID %d) ===", os.getpid())
    model_id = cfg.get("llm", {}).get("model_id", "Unknown")
    logger.info("Using LLM Model ID: %s", model_id)
    logger.info("Crash instrumentation active: crash_dump.log = %s", _CRASH_LOG)
    import time
    _boot_marks = {}  # Track boot stage timings
    _boot_marks["config"] = time.monotonic()

    # Generate codebase map for Kenny's self-awareness (runs at startup)
    try:
        from scripts.generate_ast_map import generate_codebase_map
        project_root = os.path.abspath(os.path.dirname(__file__))
        src_dir = os.path.join(project_root, "src")
        map_path = os.path.join(project_root, "data", "codebase_map.json")
        generate_codebase_map(src_dir, map_path)
    except Exception as e:
        logger.warning("Failed to generate codebase map: %s", e)

    # ── Plugin loading ───────────────────────────────────────────────────
    from src.plugin_registry import PluginRegistry
    from src.plugin_manager import PluginManager
    from src.animator import apply_plugin_profiles

    plugin_registry = PluginRegistry()
    plugin_manager = PluginManager(plugin_registry)
    plugin_manager.discover()
    plugin_manager.load_all()
    apply_plugin_profiles(plugin_registry)
    logger.info("Loaded %d plugin(s)", len(plugin_manager.loaded_plugins))

    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            PHANDLER_ROUTINE = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.DWORD)

            @PHANDLER_ROUTINE
            def console_ctrl_handler(ctrl_type):
                logger.warning("Console control signal received: %d (0=CTRL_C, 1=CTRL_BREAK, 2=CTRL_CLOSE, 5=CTRL_LOGOFF, 6=CTRL_SHUTDOWN)", ctrl_type)
                return True

            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleCtrlHandler(console_ctrl_handler, True)
            logger.info("Windows console control handler installed")
        except Exception as e:
            logger.warning("Failed to install console control handler: %s", e)

    if args.debug:
        _run_debug_simulation()
        return

    from src.opencode_serve_manager import ensure_opencode_serve_running, stop_opencode_serve
    if not args.no_opencode:
        opencode_server_url = cfg.get("llm", {}).get("server_url", DEFAULT_SERVER_URL)
        opencode_api_key = cfg.get("llm", {}).get("api_key", "")
        if ensure_opencode_serve_running(url=opencode_server_url, api_key=opencode_api_key):
            logger.debug("opencode serve ready at %s", opencode_server_url)
        else:
            logger.info("opencode serve not available; CLI fallback will be used")

    from src.persistence import load_state, save_state
    from src.pet_window import PetWindow
    import time

    state = load_state()
    start_time = time.monotonic()

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    # ── Firebase Auth gate ────────────────────────────────────────────────
    if not args.no_auth:
        from src.firebase_auth import FirebaseAuth

        auth = FirebaseAuth()
        fresh_login = not auth.load()

        if not fresh_login and not auth.get_valid_token():
            logger.warning("Token refresh failed — showing login dialog")
            fresh_login = True  # Will show login dialog on boot
    else:
        auth = None
        fresh_login = False

    window = PetWindow(
        opencode_enabled=not args.no_opencode,
        skill_ready=True,
        initial_state=state,
        auth=auth,
        fresh_login=fresh_login,
        pet_id=pet_id,
        plugin_registry=plugin_registry,
    )
    _boot_marks["petwindow"] = time.monotonic()

    # Log boot timing summary
    boot_start = _boot_marks["config"]
    logger.info(
        "Boot timing: config=%.2fs opencode=%ds petwin=%.2fs total=%.1fs",
        _boot_marks.get("opencode", boot_start) - boot_start,
        int(_boot_marks.get("opencode", 0) > 0),
        _boot_marks["petwindow"] - _boot_marks.get("opencode", boot_start),
        _boot_marks["petwindow"] - boot_start,
    )

    # Register atexit handler for emergency data flush on abnormal exit
    global _active_pet_window_ref
    _active_pet_window_ref = window
    atexit.register(_emergency_flush, window)

    try:
        exit_code = app.exec()
    finally:
        _release_lock(pet_id)

    elapsed = int(time.monotonic() - start_time)

    window._log_data_state("Pre-Sync")
    if window._firebase_mem:
        window._firebase_mem.sync_from_local(window._memory)
        diary_entries = window._diary_store.get_entries()
        diary_texts = [e.get("content", "") for e in diary_entries]
        existing = window._diary_store.read()
        diary_synced = existing.get("synced", 0) if existing else 0
        window._firebase_mem.push_pending_diaries(
            window._diary_store, diary_texts, diary_synced,
        )
    window._history.save()
    window._memory.save()

    stop_opencode_serve()

    save_state({
        "mood": window.mood_score,
        "interactions": window.interaction_count,
        "runtime_seconds": state.get("runtime_seconds", 0) + elapsed,
        "skill_greeted": True,
        "first_run_done": True,
    })

    sys.exit(exit_code)



def _run_debug_simulation() -> None:
    from dataclasses import replace
    from src.pet_fsm import PetFSM, FSMContext, PetState

    fsm = PetFSM()
    prev_state = fsm.current_state

    for tick in range(100):
        ctx = FSMContext(
            cursor_pos=(9999, 9999),
            pet_rect=(100, 900, 40, 50),
            apm=0,
            is_dragged=False,
            is_falling=False,
            query_pending=False,
            autonomous_query_pending=False,
            build_event=None,
            idle_seconds=float(tick),
            wander_due=(tick == 5),
            hyper_sustained_seconds=0.0,
            hyper_cooldown_seconds=0.0,
            state_elapsed_ms=tick * 33,
        )

        if 70 <= tick < 80:
            ctx = replace(ctx, is_dragged=True)
        if 80 <= tick < 90:
            ctx = replace(ctx, is_dragged=False, is_falling=True)
        if tick >= 90:
            ctx = replace(ctx, is_falling=False)

        new_state = fsm.update(33, ctx)
        if new_state != prev_state:
            logger.info("[tick %03d] %s -> %s", tick, prev_state.name, new_state.name)
            prev_state = new_state

    logger.info("simulation complete")


if __name__ == "__main__":
    main()
