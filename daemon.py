import sys
import os
import faulthandler
import argparse
import logging
import traceback
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from src.constants import STORAGE_DIR
from src.config import DEFAULT_SERVER_URL

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
    flat_cfg = flatten_config(cfg)
    for key, val in flat_cfg.items():
        if hasattr(constants, key):
            setattr(constants, key, val)

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
    setup_logging(debug=args.verbose, log_dir=log_config.get("dir", "logs"), config_overrides=log_config)

    logger.info("=== DAEMON STARTUP (PID %d) ===", os.getpid())
    logger.info("Crash instrumentation active: crash_dump.log = %s", _CRASH_LOG)

    # Generate codebase map for Kenny's self-awareness (runs at startup)
    try:
        from scripts.generate_ast_map import generate_codebase_map
        project_root = os.path.abspath(os.path.dirname(__file__))
        src_dir = os.path.join(project_root, "src")
        map_path = os.path.join(project_root, "data", "codebase_map.json")
        generate_codebase_map(src_dir, map_path)
    except Exception as e:
        logger.warning("Failed to generate codebase map: %s", e)

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
    )

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
