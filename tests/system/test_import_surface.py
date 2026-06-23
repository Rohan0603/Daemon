from src.system import (
    APMWorker,
    ClickThroughManager,
    EventStreamWorker,
    ScreenReader,
    TTSWorker,
    TypingBuffer,
    get_active_window_title,
    normalize_window_title,
)
from src.apm_worker import APMWorker as LegacyAPMWorker
from src.click_through import ClickThroughManager as LegacyClickThroughManager
from src.event_worker import EventStreamWorker as LegacyEventStreamWorker
from src.screen_reader import ScreenReader as LegacyScreenReader
from src.tts_worker import TTSWorker as LegacyTTSWorker
from src.typing_buffer import TypingBuffer as LegacyTypingBuffer
from src.active_window import (
    get_active_window_title as legacy_get_active_window_title,
    normalize_window_title as legacy_normalize_window_title,
)

def test_system_package_exports_current_services():
    assert APMWorker is LegacyAPMWorker
    assert ClickThroughManager is LegacyClickThroughManager
    assert EventStreamWorker is LegacyEventStreamWorker
    assert ScreenReader is LegacyScreenReader
    assert TTSWorker is LegacyTTSWorker
    assert TypingBuffer is LegacyTypingBuffer
    assert get_active_window_title is legacy_get_active_window_title
    assert normalize_window_title is legacy_normalize_window_title