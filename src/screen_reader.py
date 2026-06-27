from src.system.screen_reader import (
    ScreenReader,
    get_foreground_text_delta,
    clear_screen_cache,
    get_text_via_uia,
    get_text_via_wm_gettext,
    get_browser_url_via_uia,
)

__all__ = [
    "ScreenReader",
    "get_foreground_text_delta",
    "clear_screen_cache",
    "get_text_via_uia",
    "get_text_via_wm_gettext",
    "get_browser_url_via_uia",
]