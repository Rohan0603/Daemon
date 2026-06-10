import sys
import os
import faulthandler
import argparse
import logging
import traceback
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from src.constants import LOCK_PATH

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


def _acquire_lock() -> bool:
    """Check for existing daemon instance. Return True if lock acquired."""
    if LOCK_PATH.exists():
        try:
            pid = int(LOCK_PATH.read_text().strip())
            import ctypes
            PROCESS_QUERY_LIMITED_INFO = 0x1000
            handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFO, False, pid)
            if handle:
                ctypes.windll.kernel32.CloseHandle(handle)
                return False
        except Exception:
            pass
    LOCK_PATH.write_text(str(os.getpid()))
    return True


def _release_lock() -> None:
    try:
        LOCK_PATH.unlink(missing_ok=True)
    except Exception:
        pass


def main() -> None:
    _ensure_ffmpeg_on_path()
    from src.config import load_config
    import src.constants as constants

    cfg = load_config()
    for key, val in cfg.items():
        if hasattr(constants, key):
            setattr(constants, key, val)

    parser = argparse.ArgumentParser(description="Daemon Desktop Pet")
    parser.add_argument("--debug", action="store_true", help="Run headless FSM simulation")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose debug logging")
    parser.add_argument("--no-opencode", action="store_true", help="Disable opencode integration")
    parser.add_argument("--no-auth", action="store_true", help="Disable Firebase auth login")
    args = parser.parse_args()

    if not _acquire_lock():
        print("Daemon is already running. Exiting.", file=sys.stderr)
        sys.exit(1)

    from src.logging_setup import setup_logging
    setup_logging(debug=args.verbose, config_overrides=cfg.get("logging"))

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

    from src.constants import OPENCODE_SERVER_URL
    from src.opencode_serve_manager import ensure_opencode_serve_running, stop_opencode_serve
    if not args.no_opencode:
        if ensure_opencode_serve_running(url=OPENCODE_SERVER_URL):
            logger.debug("opencode serve ready at %s", OPENCODE_SERVER_URL)
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
    )

    try:
        exit_code = app.exec()
    finally:
        _release_lock()

    elapsed = int(time.monotonic() - start_time)

    window._log_data_state("Pre-Sync")
    if window._firebase_mem:
        window._firebase_mem.sync_from_local(window._memory)
        window._diary_synced = window._firebase_mem.push_pending_diaries(
            window._diary_store, window._diary_entries, window._diary_synced,
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
