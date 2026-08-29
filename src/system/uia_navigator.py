"""Semantic Windows UI Automation tree inspection and interaction."""
from __future__ import annotations

import ctypes
import logging
from collections.abc import Callable, Iterator
from typing import Any

from .screen_reader import _get_uia_automation

logger = logging.getLogger(__name__)

_TREE_SCOPE_SUBTREE = 4

_PATTERNS: dict[str, tuple[int, str]] = {
    "Invoke": (10000, "IUIAutomationInvokePattern"),
    "Value": (10002, "IUIAutomationValuePattern"),
    "Scroll": (10004, "IUIAutomationScrollPattern"),
    "ExpandCollapse": (10005, "IUIAutomationExpandCollapsePattern"),
    "SelectionItem": (10010, "IUIAutomationSelectionItemPattern"),
    "ScrollItem": (10017, "IUIAutomationScrollItemPattern"),
}

_CONTROL_TYPES = {
    50000: "Button",
    50001: "Calendar",
    50002: "CheckBox",
    50003: "ComboBox",
    50004: "Edit",
    50005: "Hyperlink",
    50006: "Image",
    50007: "ListItem",
    50008: "List",
    50009: "Menu",
    50010: "MenuBar",
    50011: "MenuItem",
    50012: "ProgressBar",
    50013: "RadioButton",
    50014: "ScrollBar",
    50015: "Slider",
    50016: "Spinner",
    50017: "StatusBar",
    50018: "Tab",
    50019: "TabItem",
    50020: "Text",
    50021: "ToolBar",
    50022: "ToolTip",
    50023: "Tree",
    50024: "TreeItem",
    50025: "Custom",
    50026: "Group",
    50027: "Thumb",
    50028: "DataGrid",
    50029: "DataItem",
    50030: "Document",
    50031: "SplitButton",
    50032: "Window",
    50033: "Pane",
    50034: "Header",
    50035: "HeaderItem",
    50036: "Table",
    50037: "TitleBar",
    50038: "Separator",
}

_UIA_ERRORS = (AttributeError, OSError, RuntimeError, TypeError, ValueError)


def _foreground_window() -> int:
    return int(ctypes.windll.user32.GetForegroundWindow())


def _window_title(window_handle: int) -> str:
    user32 = ctypes.windll.user32
    length = user32.GetWindowTextLengthW(window_handle)
    if length <= 0:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(window_handle, buffer, length + 1)
    return buffer.value


class UIANavigator:
    """Inspect and operate Windows controls through UI Automation patterns."""

    def __init__(
        self,
        max_depth: int = 3,
        *,
        automation_provider: Callable[[], Any] = _get_uia_automation,
        foreground_window_provider: Callable[[], int] = _foreground_window,
        window_title_provider: Callable[[int], str] = _window_title,
    ) -> None:
        if max_depth < 0:
            raise ValueError("max_depth must be non-negative")
        self.max_depth = max_depth
        self._automation_provider = automation_provider
        self._foreground_window_provider = foreground_window_provider
        self._window_title_provider = window_title_provider

    def dump_tree(
        self, window_handle: int | None = None, max_depth: int | None = None
    ) -> dict[str, Any]:
        """Return a depth-limited semantic tree for a window."""
        depth_limit = self.max_depth if max_depth is None else max_depth
        if not isinstance(depth_limit, int) or depth_limit < 0:
            return self._tree_result(window_handle or 0, [], False, "max_depth must be non-negative")

        automation, handle, root, error = self._resolve_root(window_handle)
        if error:
            return self._tree_result(handle, [], False, error)

        errors: list[str] = []
        truncated = [False]
        try:
            walker = automation.CreateTreeWalker(automation.CreateTrueCondition())
            tree = [self._serialize_element(walker, root, 0, depth_limit, truncated, errors)]
        except _UIA_ERRORS as exc:
            logger.warning("UIA tree traversal failed for HWND %s: %s", handle, exc)
            return self._tree_result(handle, [], truncated[0], f"UIA tree traversal failed: {exc}")

        return self._tree_result(handle, tree, truncated[0], "; ".join(errors) or None)

    def find_element(self, window_handle: int | None, query: dict[str, Any]) -> dict[str, Any] | None:
        """Find and serialize the first element matching semantic query fields."""
        automation, _, root, error = self._resolve_root(window_handle)
        if error:
            return None
        try:
            element = self._find_element_object(automation, root, query)
        except _UIA_ERRORS as exc:
            logger.warning("UIA element lookup failed: %s", exc)
            return None
        return self._element_info(element) if element is not None else None

    def invoke_element(
        self,
        window_handle: int | None,
        query: dict[str, Any],
        action: str,
        text: str | None = None,
    ) -> dict[str, Any]:
        """Invoke a supported UIA pattern action on the first matching element."""
        if not isinstance(action, str):
            return self._action_result(False, None, "UIA action must be a string")
        normalized_action = action.strip().casefold()
        supported = {"click", "type", "expand", "collapse", "scroll", "select"}
        if normalized_action not in supported:
            return self._action_result(False, None, f"Unsupported UIA action: {action}")
        if normalized_action == "type" and text is None:
            return self._action_result(False, None, "Text is required for the 'type' action")

        automation, _, root, error = self._resolve_root(window_handle)
        if error:
            return self._action_result(False, None, error)

        try:
            element = self._find_element_object(automation, root, query)
        except _UIA_ERRORS as exc:
            logger.warning("UIA element lookup failed: %s", exc)
            return self._action_result(False, None, f"UIA element lookup failed: {exc}")
        if element is None:
            return self._action_result(False, None, "No UIA element matched the query")

        pattern_name = {
            "click": "Invoke",
            "type": "Value",
            "expand": "ExpandCollapse",
            "collapse": "ExpandCollapse",
            "scroll": "Scroll",
            "select": "SelectionItem",
        }[normalized_action]
        try:
            pattern = self._get_pattern(element, pattern_name)
            if pattern is None:
                return self._action_result(
                    False, None, f"Element does not support the {pattern_name} pattern"
                )
            if normalized_action == "click":
                pattern.Invoke()
            elif normalized_action == "type":
                if bool(getattr(pattern, "CurrentIsReadOnly", False)):
                    return self._action_result(False, None, "Element value is read-only")
                pattern.SetValue(text)
            elif normalized_action == "expand":
                pattern.Expand()
            elif normalized_action == "collapse":
                pattern.Collapse()
            elif normalized_action == "scroll":
                pattern.Scroll(2, 4)
            else:
                pattern.Select()
        except _UIA_ERRORS as exc:
            logger.warning("UIA action '%s' failed: %s", normalized_action, exc)
            return self._action_result(False, None, f"UIA action failed: {exc}")

        return self._action_result(True, f"{normalized_action} completed", None)

    def get_element_patterns(
        self, window_handle: int | None, query: dict[str, Any]
    ) -> list[str]:
        """Return supported UIA pattern names for the first matching element."""
        automation, _, root, error = self._resolve_root(window_handle)
        if error:
            return []
        try:
            element = self._find_element_object(automation, root, query)
        except _UIA_ERRORS as exc:
            logger.warning("UIA element lookup failed: %s", exc)
            return []
        return self._supported_patterns(element) if element is not None else []

    def _resolve_root(
        self, window_handle: int | None
    ) -> tuple[Any | None, int, Any | None, str | None]:
        try:
            automation = self._automation_provider()
        except _UIA_ERRORS as exc:
            return None, int(window_handle or 0), None, f"UIA initialization failed: {exc}"
        if automation is None:
            return None, int(window_handle or 0), None, "Windows UI Automation is unavailable"

        try:
            handle = int(window_handle or self._foreground_window_provider())
        except _UIA_ERRORS as exc:
            return automation, 0, None, f"Unable to get foreground window: {exc}"
        if handle <= 0:
            return automation, handle, None, "No target window is available"

        try:
            root = automation.ElementFromHandle(handle)
        except _UIA_ERRORS as exc:
            return automation, handle, None, f"Unable to access target window: {exc}"
        if root is None:
            return automation, handle, None, "Target window has no UIA root element"
        return automation, handle, root, None

    def _tree_result(
        self,
        window_handle: int,
        tree: list[dict[str, Any]],
        truncated: bool,
        error: str | None,
    ) -> dict[str, Any]:
        try:
            title = self._window_title_provider(window_handle) if window_handle else ""
        except _UIA_ERRORS as exc:
            title = ""
            error = error or f"Unable to read window title: {exc}"
        return {
            "window_handle": window_handle,
            "window_title": title,
            "tree": tree,
            "truncated": truncated,
            "error": error,
        }

    def _serialize_element(
        self,
        walker: Any,
        element: Any,
        depth: int,
        max_depth: int,
        truncated: list[bool],
        errors: list[str],
    ) -> dict[str, Any]:
        info = self._element_info(element)
        info["children"] = []
        try:
            child = walker.GetFirstChildElement(element)
            if depth >= max_depth:
                truncated[0] = truncated[0] or child is not None
                return info
            while child is not None:
                info["children"].append(
                    self._serialize_element(
                        walker, child, depth + 1, max_depth, truncated, errors
                    )
                )
                child = walker.GetNextSiblingElement(child)
        except _UIA_ERRORS as exc:
            errors.append(f"Partial tree at {info['name'] or info['control_type']}: {exc}")
        return info

    def _element_info(self, element: Any) -> dict[str, Any]:
        control_type_id = self._current(element, "CurrentControlType", 0)
        return {
            "automation_id": str(self._current(element, "CurrentAutomationId", "") or ""),
            "name": str(self._current(element, "CurrentName", "") or ""),
            "control_type": _CONTROL_TYPES.get(control_type_id, str(control_type_id or "Unknown")),
            "control_type_id": control_type_id,
            "class_name": str(self._current(element, "CurrentClassName", "") or ""),
            "bounding_rect": self._bounding_rect(
                self._current(element, "CurrentBoundingRectangle", None)
            ),
            "is_offscreen": bool(self._current(element, "CurrentIsOffscreen", False)),
            "patterns": self._supported_patterns(element),
        }

    @staticmethod
    def _current(element: Any, attribute: str, default: Any) -> Any:
        try:
            return getattr(element, attribute)
        except _UIA_ERRORS:
            return default

    @staticmethod
    def _bounding_rect(rect: Any) -> dict[str, int] | None:
        if rect is None:
            return None
        try:
            return {
                "left": int(rect.left),
                "top": int(rect.top),
                "right": int(rect.right),
                "bottom": int(rect.bottom),
            }
        except _UIA_ERRORS:
            try:
                left, top, right, bottom = rect
                return {
                    "left": int(left),
                    "top": int(top),
                    "right": int(right),
                    "bottom": int(bottom),
                }
            except _UIA_ERRORS:
                return None

    def _supported_patterns(self, element: Any) -> list[str]:
        return [name for name in _PATTERNS if self._get_pattern(element, name) is not None]

    @staticmethod
    def _get_pattern(element: Any, pattern_name: str) -> Any | None:
        pattern_id, interface_name = _PATTERNS[pattern_name]
        try:
            pattern = element.GetCurrentPattern(pattern_id)
        except _UIA_ERRORS:
            return None
        if pattern is None or not bool(pattern):
            return None
        if not hasattr(pattern, "QueryInterface"):
            return pattern
        try:
            from comtypes.gen import UIAutomationClient

            interface = getattr(UIAutomationClient, interface_name)
            return pattern.QueryInterface(interface)
        except (AttributeError, ImportError, OSError, RuntimeError, TypeError, ValueError):
            return None

    def _find_element_object(self, automation: Any, root: Any, query: dict[str, Any]) -> Any | None:
        if not isinstance(query, dict) or not query:
            return None
        walker = automation.CreateTreeWalker(automation.CreateTrueCondition())
        xpath = str(query.get("xpath", "")).strip()
        xpath_segments = [part.casefold() for part in xpath.strip("/").split("/") if part]
        fields = {key: value for key, value in query.items() if key != "xpath" and value is not None}

        for element, path in self._walk_elements(walker, root):
            if fields and not self._matches_fields(element, fields):
                continue
            if xpath_segments and not self._matches_path(path, xpath_segments):
                continue
            if fields or xpath_segments:
                return element
        return None

    def _walk_elements(
        self, walker: Any, element: Any, path: list[set[str]] | None = None
    ) -> Iterator[tuple[Any, list[set[str]]]]:
        current_path = [*(path or []), self._element_labels(element)]
        yield element, current_path
        child = walker.GetFirstChildElement(element)
        while child is not None:
            yield from self._walk_elements(walker, child, current_path)
            child = walker.GetNextSiblingElement(child)

    def _matches_fields(self, element: Any, fields: dict[str, Any]) -> bool:
        field_map = {
            "automation_id": "CurrentAutomationId",
            "name": "CurrentName",
            "class_name": "CurrentClassName",
        }
        for key, expected in fields.items():
            if key == "control_type":
                actual_id = self._current(element, "CurrentControlType", 0)
                actual = _CONTROL_TYPES.get(actual_id, str(actual_id))
            elif key in field_map:
                actual = self._current(element, field_map[key], "")
            else:
                return False
            if str(actual).casefold() != str(expected).casefold():
                return False
        return True

    def _element_labels(self, element: Any) -> set[str]:
        control_type_id = self._current(element, "CurrentControlType", 0)
        return {
            str(value).casefold()
            for value in (
                self._current(element, "CurrentAutomationId", ""),
                self._current(element, "CurrentName", ""),
                _CONTROL_TYPES.get(control_type_id, control_type_id),
            )
            if value not in ("", None)
        }

    @staticmethod
    def _matches_path(path: list[set[str]], segments: list[str]) -> bool:
        return len(path) >= len(segments) and all(
            segment in labels for segment, labels in zip(segments, path[-len(segments):])
        )

    @staticmethod
    def _action_result(success: bool, result: str | None, error: str | None) -> dict[str, Any]:
        return {"success": success, "result": result, "error": error}
