import pytest
from unittest.mock import ANY, MagicMock, patch


def _mock_firebase_diary(m: MagicMock) -> MagicMock:
    """Set sensible defaults for diary methods on a mock MemoryManager."""
    m.read_local_diary.return_value = None       # no local file → fetch from Firebase
    m.fetch_all_diary_entries.return_value = []   # Firebase has no entries
    m.write_local_diary = MagicMock()
    m.push_pending_diaries.return_value = 0
    return m

@pytest.fixture
def app():
    from PyQt6.QtWidgets import QApplication
    _app = QApplication.instance()
    if _app is None:
        _app = QApplication([])
    return _app

def test_force_quit_initial_value(app):
    from src.pet_window import PetWindow
    
    with patch("src.pet_window.ClickThroughManager") as mock_ctm, \
         patch("PyQt6.QtWidgets.QSystemTrayIcon") as mock_tray, \
         patch("src.pet_window.APMWorker") as mock_apm:
        
        window = PetWindow(opencode_enabled=False)
        assert hasattr(window, "_force_quit")
        assert window._force_quit is False

def test_close_event_ignores_and_hides_when_not_force_quit(app):
    from src.pet_window import PetWindow
    from PyQt6.QtGui import QCloseEvent
    
    with patch("src.pet_window.ClickThroughManager") as mock_ctm, \
         patch("PyQt6.QtWidgets.QSystemTrayIcon") as mock_tray, \
         patch("src.pet_window.APMWorker") as mock_apm:
        
        window = PetWindow(opencode_enabled=False)
        window.hide = MagicMock()
        
        event = QCloseEvent()
        window.closeEvent(event)
        
        assert event.isAccepted() is False
        window.hide.assert_called_once()

def test_close_event_accepts_when_force_quit(app):
    from src.pet_window import PetWindow
    from PyQt6.QtGui import QCloseEvent
    
    with patch("src.pet_window.ClickThroughManager") as mock_ctm, \
         patch("PyQt6.QtWidgets.QSystemTrayIcon") as mock_tray, \
         patch("src.pet_window.APMWorker") as mock_apm:
        
        window = PetWindow(opencode_enabled=False)
        window._force_quit = True
        window.hide = MagicMock()
        
        event = QCloseEvent()
        window.closeEvent(event)
        
        assert event.isAccepted() is True
        window.hide.assert_not_called()

def test_force_quit_app_stops_apm_and_quits(app):
    from src.pet_window import PetWindow
    
    with patch("src.pet_window.ClickThroughManager") as mock_ctm, \
         patch("PyQt6.QtWidgets.QSystemTrayIcon") as mock_tray, \
         patch("src.pet_window.APMWorker") as mock_apm, \
         patch("PyQt6.QtWidgets.QApplication.quit") as mock_quit:
        
        window = PetWindow(opencode_enabled=False)
        window._force_quit_app()
        
        assert window._force_quit is True
        window._apm_worker.stop.assert_called_once()
        mock_quit.assert_called_once()


def test_pet_window_initializes_state_parameters(app):
    from src.pet_window import PetWindow
    with patch("src.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.pet_window.APMWorker"):
        window = PetWindow(opencode_enabled=True, skill_ready=True, initial_state={"mood": 5, "interactions": 10})
        assert window.mood_score == 5
        assert window.interaction_count == 10
        assert window._skill_ready is True


def test_pet_window_greets_when_skill_ready_and_not_greeted(app):
    from src.pet_window import PetWindow
    with patch("src.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.pet_window.APMWorker"):
        window = PetWindow(opencode_enabled=True, skill_ready=True, initial_state={"skill_greeted": False})
        assert window._bubble_text == "dae: memory active."


def test_pet_window_does_not_greet_if_already_greeted(app):
    from src.pet_window import PetWindow
    with patch("src.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.pet_window.APMWorker"):
        window = PetWindow(opencode_enabled=True, skill_ready=True, initial_state={"skill_greeted": True})
        assert window._bubble_text == ""


def test_pet_window_increments_interactions_on_opencode_result(app, tmp_path):
    from src.pet_window import PetWindow
    mem_path = str(tmp_path / "mem.json")
    hist_path = str(tmp_path / "hist.json")
    with patch("src.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.pet_window.APMWorker"):
        window = PetWindow(opencode_enabled=True, skill_ready=True,
                           initial_state={"interactions": 2},
                           memory_path=mem_path, history_path=hist_path)
        window._on_opencode_result("mock response")
        assert window.interaction_count == 3


def test_joke_interval_constant():
    from src.constants import JOKE_INTERVAL_SEC
    assert JOKE_INTERVAL_SEC > 0


def test_joke_timer_initialized(app):
    from src.pet_window import PetWindow
    from src.constants import BEHAVIOR_TICK_MS
    with patch("src.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.pet_window.APMWorker"):
        window = PetWindow(opencode_enabled=False)
        assert hasattr(window, "_behavior_timer")
        assert window._behavior_timer.interval() == BEHAVIOR_TICK_MS


def test_on_joke_tick_skips_when_pending(app, tmp_path):
    from src.pet_window import PetWindow
    mem_path = str(tmp_path / "mem.json")
    hist_path = str(tmp_path / "hist.json")
    with patch("src.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.pet_window.APMWorker"), \
         patch("src.pet_window.OpencodeWorker") as mock_worker_cls:
        window = PetWindow(opencode_enabled=True, memory_path=mem_path, history_path=hist_path)
        window._autonomous_query_pending = True
        window._trigger_joke()
        mock_worker_cls.assert_not_called()


def test_input_submission_starts_opencode_worker(app, tmp_path):
    from src.pet_window import PetWindow
    from src.pet_fsm import PetState
    mem_path = str(tmp_path / "mem.json")
    hist_path = str(tmp_path / "hist.json")
    mock_firebase = _mock_firebase_diary(MagicMock())
    mock_firebase.load_current_brain.return_value = {}

    with patch("src.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.pet_window.APMWorker"), \
         patch("src.pet_window.OpencodeWorker") as mock_worker_class, \
         patch("src.pet_window.get_active_window_title", return_value="Test Window"), \
         patch("src.pet_window.MemoryManager", return_value=mock_firebase), \
         patch("src.pet_window.DiaryStore"):

        mock_worker = MagicMock()
        mock_worker_class.return_value = mock_worker

        window = PetWindow(opencode_enabled=True, memory_path=mem_path, history_path=hist_path)
        window._input_field.setText("hello opencode")
        window._on_input_submitted()

        mock_worker_class.assert_called_once()
        call_kwargs = mock_worker_class.call_args.kwargs
        assert call_kwargs["user_input"] == "hello opencode"
        assert call_kwargs["context_hint"] == "Test Window"
        assert call_kwargs["is_autonomous"] is False
        assert "hello opencode" in call_kwargs["prompt"]
        mock_worker.start.assert_called_once()
        assert window._fsm.current_state == PetState.THINKING


def test_firebase_failure_sets_unavailable_flag(app, tmp_path):
    from src.pet_window import PetWindow
    mem_path = str(tmp_path / "mem.json")
    hist_path = str(tmp_path / "hist.json")
    mock_firebase = _mock_firebase_diary(MagicMock())
    mock_firebase.sync_to_local.side_effect = Exception("creds invalid")
    with patch("src.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.pet_window.APMWorker"), \
         patch("src.pet_window.MemoryManager", return_value=mock_firebase), \
         patch("src.pet_window.DiaryStore") as mock_ds_cls:
        mock_ds = MagicMock()
        mock_ds.read.return_value = None
        # Simulate seeding: store entries in a real list behind the mock
        _seeded_entries = []
        mock_ds.add_diary_entry.side_effect = lambda text, ts=0, **kw: (
            _seeded_entries.append({"content": text, "timestamp": ts, "hash": "h"}) or True
        )
        mock_ds.get_entries.side_effect = lambda: list(_seeded_entries)
        mock_ds_cls.return_value = mock_ds
        window = PetWindow(opencode_enabled=False, memory_path=mem_path, history_path=hist_path)
        assert window._firebase_available is False
        # Diary gets seeded with mispronunciation history on first run
        assert len(window._diary_store.get_entries()) == 3


def test_force_quit_stops_timers_and_waits_for_worker(app):
    from src.pet_window import PetWindow
    with patch("src.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.pet_window.APMWorker"), \
         patch("PyQt6.QtWidgets.QApplication.quit"), \
         patch.object(PetWindow, "_on_boot_check_auth"):
        window = PetWindow(opencode_enabled=False)
        window._fsm_timer.stop = MagicMock()
        window._behavior_timer.stop = MagicMock()
        window._response_manager.stop = MagicMock()
        mock_worker = MagicMock()
        mock_worker.isRunning.return_value = True
        window._opencode_worker = mock_worker
        window._force_quit_app()
        window._fsm_timer.stop.assert_called_once()
        window._behavior_timer.stop.assert_called_once()
        window._response_manager.stop.assert_called_once()
        mock_worker.quit.assert_called_once()
        mock_worker.wait.assert_called_once_with(15000)


def test_firebase_crud_sets_available_flag(app, tmp_path, qtbot):
    from src.pet_window import PetWindow
    from unittest.mock import patch, MagicMock
    mem_path = str(tmp_path / "mem.json")
    hist_path = str(tmp_path / "hist.json")

    mock_crud = MagicMock()
    mock_crud.available = True

    with patch("src.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.pet_window.APMWorker"), \
         patch("src.firebase_crud.FirebaseCRUD", return_value=mock_crud), \
         patch("src.pet_window.MemoryManager"), \
         patch("src.pet_window.QDialog"):
        window = PetWindow(opencode_enabled=False, memory_path=mem_path, history_path=hist_path)

    qtbot.wait(600)  # Let boot timer fire
    assert window._firebase_available is True


def test_on_opencode_error_shows_in_character_bubble(app, tmp_path):
    from src.pet_window import PetWindow
    mem_path = str(tmp_path / "mem.json")
    hist_path = str(tmp_path / "hist.json")
    mock_firebase = _mock_firebase_diary(MagicMock())
    mock_firebase.load_current_brain.return_value = {}
    with patch("src.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.pet_window.APMWorker"), \
         patch("src.pet_window.MemoryManager", return_value=mock_firebase):
        window = PetWindow(opencode_enabled=True, memory_path=mem_path, history_path=hist_path)
        window._on_opencode_error("some technical error message")
        # Check that the bubble is shown, and it is NOT the technical message
        assert window._bubble_text != "some technical error message"
        assert len(window._bubble_text) > 0


def test_curiosity_command_remember_still_works(app, tmp_path):
    from src.pet_window import PetWindow
    mem_path = str(tmp_path / "mem.json")
    hist_path = str(tmp_path / "hist.json")
    mock_firebase = _mock_firebase_diary(MagicMock())
    mock_firebase.load_current_brain.return_value = {}
    with patch("src.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.pet_window.APMWorker"), \
         patch("src.pet_window.MemoryManager", return_value=mock_firebase):
        window = PetWindow(opencode_enabled=False, memory_path=mem_path, history_path=hist_path)
        window._input_field.setText("!remember test_key: test_val")
        window._on_input_submitted()
        assert window._memory.recall("test_key") == "test_val"

def test_on_input_submitted_shows_thinking_state(app, tmp_path):
    from src.pet_window import PetWindow
    from src.pet_fsm import PetState
    mem_path = str(tmp_path / "mem.json")
    hist_path = str(tmp_path / "hist.json")
    mock_firebase = _mock_firebase_diary(MagicMock())
    mock_firebase.load_current_brain.return_value = {}
    with patch("src.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.pet_window.APMWorker"), \
         patch("src.pet_window.MemoryManager", return_value=mock_firebase), \
         patch("src.pet_window.OpencodeWorker") as mock_worker_cls:
        mock_worker_cls.return_value = MagicMock()
        window = PetWindow(opencode_enabled=True, memory_path=mem_path, history_path=hist_path)
        window._input_field.setText("my query text")
        window._on_input_submitted()
        # No filler bubble — only THINKING animation
        assert window._fsm.current_state == PetState.THINKING


def test_pet_window_constructs_write_coalescer_response_manager_and_builder(app, tmp_path):
    from src.pet_window import PetWindow
    mem_path = str(tmp_path / "mem.json")
    hist_path = str(tmp_path / "hist.json")
    with patch("src.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.pet_window.APMWorker"), \
         patch("src.pet_window.MemoryManager"):
        window = PetWindow(opencode_enabled=True, memory_path=mem_path, history_path=hist_path)
    assert hasattr(window, "_write_coalescer")
    assert hasattr(window, "_response_manager")
    assert hasattr(window, "_context_manager")
    from src.write_coalescer import WriteCoalescer
    from src.response_manager import AutonomousResponseManager
    from src.context_manager import ContextManager
    assert isinstance(window._write_coalescer, WriteCoalescer)
    assert isinstance(window._response_manager, AutonomousResponseManager)
    assert isinstance(window._context_manager, ContextManager)


def test_memory_history_use_stored_coalescer(app, tmp_path):
    from src.pet_window import PetWindow
    mem_path = str(tmp_path / "mem.json")
    hist_path = str(tmp_path / "hist.json")
    with patch("src.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.pet_window.APMWorker"), \
         patch("src.pet_window.MemoryManager"):
        window = PetWindow(opencode_enabled=True, memory_path=mem_path, history_path=hist_path)
    # Mutating memory/history with no per-call coalescer should mark the
    # write_coalescer dirty (no immediate disk write).
    save = MagicMock()
    window._memory.save = save
    window._memory.remember("k", "v")
    save.assert_not_called()
    window._write_coalescer._dirty["memory"] is True or window._write_coalescer._dirty["memory"]
    assert window._write_coalescer._dirty["memory"] is True


def test_force_quit_stops_response_manager_and_flushes_writes(app, tmp_path):
    from src.pet_window import PetWindow
    mem_path = str(tmp_path / "mem.json")
    hist_path = str(tmp_path / "hist.json")
    with patch("src.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.pet_window.APMWorker"), \
         patch("src.pet_window.MemoryManager"), \
         patch("PyQt6.QtWidgets.QApplication.quit"), \
         patch.object(PetWindow, "_on_boot_check_auth"):
        window = PetWindow(opencode_enabled=False, memory_path=mem_path, history_path=hist_path)
        window._response_manager.stop = MagicMock()
        window._write_coalescer.stop = MagicMock()
        window._write_coalescer.flush = MagicMock()
        window._force_quit_app()
        window._response_manager.stop.assert_called_once()
        window._write_coalescer.stop.assert_called_once()
        window._write_coalescer.flush.assert_called_once()


def test_should_fire_autonomous_skips_when_disabled_or_thinking(app, tmp_path):
    from src.pet_window import PetWindow
    from src.pet_fsm import PetState
    mem_path = str(tmp_path / "mem.json")
    hist_path = str(tmp_path / "hist.json")
    with patch("src.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.pet_window.APMWorker"), \
         patch("src.pet_window.MemoryManager"):
        window = PetWindow(opencode_enabled=False, memory_path=mem_path, history_path=hist_path)
        # opencode disabled
        assert window._should_fire_autonomous("test") is False
        # query pending
        window._opencode_enabled = True
        window._autonomous_query_pending = True
        assert window._should_fire_autonomous("test") is False
        # thinking state
        window._autonomous_query_pending = False
        window._fsm.current_state = PetState.THINKING
        assert window._should_fire_autonomous("test") is False
        # clear conditions → fires
        window._fsm.current_state = PetState.IDLE
        assert window._should_fire_autonomous("test") is True


def test_add_diary_entry_uses_write_coalescer(app, tmp_path):
    from src.pet_window import PetWindow
    mem_path = str(tmp_path / "mem.json")
    hist_path = str(tmp_path / "hist.json")
    mock_auth = MagicMock()
    mock_auth.uid = "test-uid"
    mock_firebase = MagicMock()
    mock_firebase.sync_to_local = MagicMock()
    mock_firebase.fetch_all_diary_entries = MagicMock(return_value=[])
    mock_firebase.write_local_diary = MagicMock()
    with patch("src.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.pet_window.APMWorker"), \
         patch("src.pet_window.MemoryManager", return_value=mock_firebase):
        window = PetWindow(opencode_enabled=False, memory_path=mem_path, history_path=hist_path,
                           auth=mock_auth)
        window._firebase_mem = mock_firebase
        window._firebase_mem.write_local_diary = MagicMock()
        window._write_coalescer.mark_dirty = MagicMock()
        window._add_diary_entry("test entry")
        window._write_coalescer.mark_dirty.assert_called_once_with("diary")
        window._firebase_mem.write_local_diary.assert_not_called()


def test_session_created_saves_session_id(app, tmp_path):
    from src.pet_window import PetWindow
    mem_path = str(tmp_path / "mem.json")
    hist_path = str(tmp_path / "hist.json")
    with patch("src.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.pet_window.APMWorker"), \
         patch("src.pet_window.MemoryManager"), \
         patch("src.pet_window.OpencodeWorker"):
        window = PetWindow(opencode_enabled=False, memory_path=mem_path, history_path=hist_path)
        window._on_session_created("sess-123")
        assert window._opencode_session_id == "sess-123"


def test_crash_recovery_hook_flushes_on_exception(app, tmp_path):
    import sys
    from src.pet_window import PetWindow
    mem_path = str(tmp_path / "mem.json")
    hist_path = str(tmp_path / "hist.json")
    with patch("src.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.pet_window.APMWorker"), \
         patch("src.pet_window.MemoryManager"), \
         patch.object(PetWindow, "_on_boot_check_auth"):
        # Replace excepthook so PetWindow captures no-op as 'existing'
        orig_hook = sys.excepthook
        sys.excepthook = lambda *args: None
        try:
            window = PetWindow(opencode_enabled=False, memory_path=mem_path, history_path=hist_path)
            pet_hook = sys.excepthook
        finally:
            sys.excepthook = orig_hook
        assert pet_hook is not None
        assert pet_hook is not orig_hook
        window._write_coalescer.flush = MagicMock()
        try:
            raise RuntimeError("test crash")
        except RuntimeError as e:
            pet_hook(RuntimeError, e, e.__traceback__)
        window._write_coalescer.flush.assert_called_once()


def test_silence_backoff_increases_interval():
    """After SILENCE_THRESHOLD non-engaged outputs, interval should backoff."""
    from src.constants import SILENCE_THRESHOLD, BASE_INTERVAL_SEC, MAX_BACKOFF_SEC, BACKOFF_MULTIPLIER
    from src.pet_window import PetWindow
    pw = PetWindow.__new__(PetWindow)
    pw._consecutive_silent = 0
    pw._consecutive_engaged = 0
    pw._current_interval = BASE_INTERVAL_SEC

    for i in range(SILENCE_THRESHOLD):
        pw._on_output_displayed(engaged=False)

    expected = min(BASE_INTERVAL_SEC * (BACKOFF_MULTIPLIER ** SILENCE_THRESHOLD), MAX_BACKOFF_SEC)
    assert pw._current_interval == expected


def test_engagement_resets_to_base_interval():
    """After ENGAGED_THRESHOLD engaged outputs, interval should reset to BASE."""
    from src.constants import ENGAGED_THRESHOLD, BASE_INTERVAL_SEC
    from src.pet_window import PetWindow
    pw = PetWindow.__new__(PetWindow)
    pw._consecutive_silent = 5
    pw._consecutive_engaged = 0
    pw._current_interval = BASE_INTERVAL_SEC * 2

    for i in range(ENGAGED_THRESHOLD):
        pw._on_output_displayed(engaged=True)

    assert pw._current_interval == BASE_INTERVAL_SEC


def test_brain_update_wired_to_signal(app, tmp_path):
    from src.pet_window import PetWindow
    mem_path = str(tmp_path / "mem.json")
    hist_path = str(tmp_path / "hist.json")
    with patch("src.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.pet_window.APMWorker"), \
         patch("src.pet_window.MemoryManager"):
        window = PetWindow(opencode_enabled=False, memory_path=mem_path, history_path=hist_path)
        assert hasattr(window, "_on_brain_update")
        assert callable(window._on_brain_update)


def test_on_brain_update_calls_memory_and_firebase(app, tmp_path):
    from src.pet_window import PetWindow
    from unittest.mock import MagicMock
    mem_path = str(tmp_path / "mem.json")
    hist_path = str(tmp_path / "hist.json")
    mock_auth = MagicMock()
    mock_auth.uid = "test-uid"
    mock_firebase = MagicMock()
    mock_firebase.db = MagicMock()
    mock_firebase.sync_to_local = MagicMock()
    mock_firebase.fetch_all_diary_entries = MagicMock(return_value=[])
    with patch("src.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.pet_window.APMWorker"), \
         patch("src.pet_window.MemoryManager", return_value=mock_firebase):
        window = PetWindow(opencode_enabled=False, memory_path=mem_path, history_path=hist_path,
                           auth=mock_auth)
        window._firebase_mem = mock_firebase
        window._firebase_available = True
        window._memory.remember = MagicMock()
        window._on_brain_update({"intel_archive": ["new intel item"]})
        window._memory.remember.assert_called_once_with("intel_archive", "new intel item")


def test_on_brain_update_strips_locked(app, tmp_path):
    from src.pet_window import PetWindow
    from unittest.mock import MagicMock
    mem_path = str(tmp_path / "mem.json")
    hist_path = str(tmp_path / "hist.json")
    with patch("src.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.pet_window.APMWorker"), \
         patch("src.pet_window.MemoryManager") as mm_cls:
        mock_firebase = MagicMock()
        mock_firebase.db = MagicMock()
        mm_cls.return_value = mock_firebase
        window = PetWindow(opencode_enabled=False, memory_path=mem_path, history_path=hist_path)
        window._firebase_available = True
        window._memory.remember = MagicMock()
        window._on_brain_update({"mission_directive": "hacked"})
        window._memory.remember.assert_not_called()


def test_constructs_response_manager_with_single_thought_pool(app, tmp_path):
    from src.pet_window import PetWindow
    mem_path = str(tmp_path / "mem.json")
    hist_path = str(tmp_path / "hist.json")
    with patch("src.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.pet_window.APMWorker"), \
         patch("src.pet_window.MemoryManager"):
        pw = PetWindow(opencode_enabled=False, memory_path=mem_path, history_path=hist_path)
    assert hasattr(pw, "_response_manager")
    assert hasattr(pw._response_manager, "thought_pool")


def test_active_chat_tick_dispatches_trigger(app, tmp_path):
    from src.pet_window import PetWindow
    mem_path = str(tmp_path / "mem.json")
    hist_path = str(tmp_path / "hist.json")
    with patch("src.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.pet_window.APMWorker"), \
         patch("src.pet_window.MemoryManager"), \
         patch("src.pet_window.OpencodeWorker") as mock_worker_cls, \
         patch("src.pet_window.get_active_window_title", return_value="Test Window"):
        mock_worker = MagicMock()
        mock_worker.isRunning.return_value = False
        mock_worker_cls.return_value = mock_worker
        pw = PetWindow(opencode_enabled=True, memory_path=mem_path, history_path=hist_path)
        pw._opencode_worker = mock_worker
        pw._trigger_chat()
        assert mock_worker_cls.call_count >= 2
        mock_worker.start.assert_called()

def test_joke_tick_dispatches_trigger(app, tmp_path):
    from src.pet_window import PetWindow
    mem_path = str(tmp_path / "mem.json")
    hist_path = str(tmp_path / "hist.json")
    with patch("src.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.pet_window.APMWorker"), \
         patch("src.pet_window.MemoryManager"), \
         patch("src.pet_window.OpencodeWorker") as mock_worker_cls, \
         patch("src.pet_window.get_active_window_title", return_value="Test Window"):
        mock_worker = MagicMock()
        mock_worker.isRunning.return_value = False
        mock_worker_cls.return_value = mock_worker
        pw = PetWindow(opencode_enabled=True, memory_path=mem_path, history_path=hist_path)
        pw._opencode_worker = mock_worker
        pw._trigger_joke()
        mock_worker_cls.assert_called_once()
        mock_worker.start.assert_called_once()


def test_force_quit_stops_response_manager(app, tmp_path):
    from src.pet_window import PetWindow
    mem_path = str(tmp_path / "mem.json")
    hist_path = str(tmp_path / "hist.json")
    with patch("src.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.pet_window.APMWorker"), \
         patch("src.pet_window.MemoryManager"), \
         patch("PyQt6.QtWidgets.QApplication.quit"):
        pw = PetWindow(opencode_enabled=False, memory_path=mem_path, history_path=hist_path)
        pw._force_quit_app()
        assert pw._response_manager._decay_timer.isActive() is False
        assert pw._response_manager._auto_refill_timer.isActive() is False


def test_should_fire_autonomous_checks_correct_pool(app, tmp_path):
    from src.pet_window import PetWindow
    from src.pet_fsm import PetState
    mem_path = str(tmp_path / "mem.json")
    hist_path = str(tmp_path / "hist.json")
    with patch("src.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.pet_window.APMWorker"), \
         patch("src.pet_window.MemoryManager"):
        pw = PetWindow(opencode_enabled=False, memory_path=mem_path, history_path=hist_path)
        pw._opencode_worker = object()
        pw._response_manager.thought_pool._items = []
        # boredom checks thought pool
        assert pw._should_fire_autonomous("boredom") is False
        pw._response_manager.thought_pool._items = [
            {"dialogue": "a", "action": "idle", "priority": 3, "type": "idle_thought"}
        ]
        assert pw._should_fire_autonomous("boredom") is True
        # active_chat/joke require opencode
        assert pw._should_fire_autonomous("active_chat") is False
        pw._opencode_enabled = True
        assert pw._should_fire_autonomous("active_chat") is True


def test_window_accepts_fresh_login_flag(app):
    from src.pet_window import PetWindow
    with patch("src.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.pet_window.APMWorker"), \
         patch("src.pet_window.MemoryManager"), \
         patch("src.pet_window.DiaryStore"):
        window = PetWindow(fresh_login=True)
    assert window._fresh_login is True


def test_window_without_explicit_auth(app):
    from src.pet_window import PetWindow
    with patch("src.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.pet_window.APMWorker"), \
         patch("src.pet_window.MemoryManager"), \
         patch("src.pet_window.DiaryStore"):
        window = PetWindow()
    assert window._crud is None
    assert window._firebase_mem is None


def test_risky_keyword_interrupts_bubble(qtbot):
    from src.pet_window import PetWindow
    with patch("src.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.pet_window.APMWorker"), \
         patch("src.pet_window.MemoryManager"), \
         patch("src.pet_window.DiaryStore"):
        window = PetWindow()
    qtbot.add_widget(window)
    window._typing_buffer.get_context = lambda: "git push --force origin main"
    window._clear_bubble_queue = MagicMock()
    window._show_bubble = MagicMock()
    window._fsm.transition_to = MagicMock()
    window._on_typing_debounce()
    assert window._show_bubble.called


def test_dispatch_multiplexed_creates_worker(qtbot):
    from src.pet_window import PetWindow
    with patch("src.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.pet_window.APMWorker"), \
         patch("src.pet_window.MemoryManager"), \
         patch("src.pet_window.DiaryStore"), \
         patch("src.pet_window.OpencodeWorker") as mock_worker_cls:
        mock_worker = MagicMock()
        mock_worker_cls.return_value = mock_worker
        window = PetWindow()
        qtbot.add_widget(window)
        window._dispatch_multiplexed(["kenny_roast", "morty_panic"])
        assert mock_worker_cls.called
        assert mock_worker.start.called
        assert mock_worker.response_ready.connect.called


def test_structured_multiplexed_bickering_pair(qtbot):
    from src.pet_window import PetWindow
    with patch("src.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.pet_window.APMWorker"), \
         patch("src.pet_window.MemoryManager"), \
         patch("src.pet_window.DiaryStore"):
        window = PetWindow()
        qtbot.add_widget(window)
        window._dispatch_structured = MagicMock()
        items = [
            {"dialogue": "Kenny roast!", "action": "shake", "target_x": 0, "mode": "kenny_roast"},
            {"dialogue": "Morty panic!", "action": "spin", "target_x": 0, "mode": "morty_panic"},
        ]
        window._on_structured_multiplexed(items)
        assert window._dispatch_structured.call_count == 1
        call_args = window._dispatch_structured.call_args
        assert call_args[0][0]["dialogue"] == "Kenny roast!"
        assert call_args[0][0]["action"] == "shake"


def test_structured_multiplexed_standard_path(qtbot):
    from src.pet_window import PetWindow
    with patch("src.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.pet_window.APMWorker"), \
         patch("src.pet_window.MemoryManager"), \
         patch("src.pet_window.DiaryStore"):
        window = PetWindow()
        qtbot.add_widget(window)
        window._dispatch_structured = MagicMock()
        window._response_manager.add_items = MagicMock()
        items = [
            {"dialogue": "First", "action": "idle", "target_x": 0, "pool_type": "jokes_blackmail"},
            {"dialogue": "Second", "action": "idle", "target_x": 0, "pool_type": "jokes_blackmail"},
        ]
        window._on_structured_multiplexed(items)
        assert window._dispatch_structured.call_count == 1
        call_args = window._dispatch_structured.call_args
        assert call_args[0][0]["dialogue"] == "First"
        assert window._response_manager.add_items.called


def test_health_timer_initialized(app, tmp_path):
    from src.pet_window import PetWindow
    mem_path = str(tmp_path / "mem.json")
    hist_path = str(tmp_path / "hist.json")
    with patch("src.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.pet_window.APMWorker"), \
         patch("src.pet_window.MemoryManager"):
        window = PetWindow(opencode_enabled=False, memory_path=mem_path, history_path=hist_path)
    assert hasattr(window, "_health_timer")
    assert window._health_timer.isActive()
    assert window._health_timer.interval() == 10000


def test_health_check_disconnect_shows_devastated(app, tmp_path):
    from src.pet_window import PetWindow
    from src.pet_fsm import PetState
    mem_path = str(tmp_path / "mem.json")
    hist_path = str(tmp_path / "hist.json")
    with patch("src.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.pet_window.APMWorker"), \
         patch("src.pet_window.MemoryManager"), \
         patch("src.opencode_serve_manager.check_health", return_value=False):
        window = PetWindow(opencode_enabled=True, memory_path=mem_path, history_path=hist_path)
        window._brain_disconnected = False
        window._on_health_check()
    assert window._brain_disconnected is True
    assert window._fsm.current_state == PetState.DEVASTATED


def test_health_check_reconnect_returns_to_idle(app, tmp_path):
    from src.pet_window import PetWindow
    from src.pet_fsm import PetState
    mem_path = str(tmp_path / "mem.json")
    hist_path = str(tmp_path / "hist.json")
    with patch("src.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.pet_window.APMWorker"), \
         patch("src.pet_window.MemoryManager"), \
         patch("src.opencode_serve_manager.check_health", return_value=True):
        window = PetWindow(opencode_enabled=True, memory_path=mem_path, history_path=hist_path)
        window._brain_disconnected = True
        window._fsm.transition_to(PetState.DEVASTATED)
        window._on_health_check()
    assert window._brain_disconnected is False
    assert window._fsm.current_state == PetState.IDLE


def test_window_change_clears_screen_cache(app, tmp_path):
    from src.pet_window import PetWindow
    mem_path = str(tmp_path / "mem.json")
    hist_path = str(tmp_path / "hist.json")
    with patch("src.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.pet_window.APMWorker"), \
         patch("src.pet_window.MemoryManager"), \
         patch("src.screen_reader.clear_screen_cache") as mock_clear:
        window = PetWindow(opencode_enabled=False, memory_path=mem_path, history_path=hist_path)
        window._last_active_window = "Old Window"
        with patch("src.pet_window.get_active_window_title", return_value="New Window"):
            window._has_significant_delta()
        mock_clear.assert_called_once()


def test_restart_brain_calls_ensure_running_and_check(app, tmp_path):
    from src.pet_window import PetWindow
    mem_path = str(tmp_path / "mem.json")
    hist_path = str(tmp_path / "hist.json")
    with patch("src.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.pet_window.APMWorker"), \
         patch("src.pet_window.MemoryManager"), \
         patch("src.opencode_serve_manager.ensure_opencode_serve_running") as mock_ensure, \
         patch("src.opencode_serve_manager.check_health") as mock_check:
        window = PetWindow(opencode_enabled=True, memory_path=mem_path, history_path=hist_path)
        window._on_restart_brain()
    mock_ensure.assert_called_once()
    mock_check.assert_called_once()
