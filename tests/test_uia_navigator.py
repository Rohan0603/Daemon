from types import SimpleNamespace

import pytest

from src.system.uia_navigator import UIANavigator


class FakePattern:
    def __init__(self, read_only=False):
        self.CurrentIsReadOnly = read_only
        self.calls = []

    def Invoke(self):
        self.calls.append(("invoke",))

    def SetValue(self, text):
        self.calls.append(("set_value", text))

    def Expand(self):
        self.calls.append(("expand",))

    def Collapse(self):
        self.calls.append(("collapse",))

    def Scroll(self, horizontal, vertical):
        self.calls.append(("scroll", horizontal, vertical))

    def Select(self):
        self.calls.append(("select",))


class FakeElement:
    def __init__(
        self,
        name,
        control_type,
        *,
        automation_id="",
        class_name="",
        children=None,
        patterns=None,
    ):
        self.CurrentName = name
        self.CurrentControlType = control_type
        self.CurrentAutomationId = automation_id
        self.CurrentClassName = class_name
        self.CurrentBoundingRectangle = SimpleNamespace(
            left=10, top=20, right=110, bottom=60
        )
        self.CurrentIsOffscreen = False
        self.children = children or []
        self.patterns = patterns or {}
        self.parent = None
        for child in self.children:
            child.parent = self

    def GetCurrentPattern(self, pattern_id):
        if pattern_id not in self.patterns:
            raise OSError("pattern unavailable")
        return self.patterns[pattern_id]


class FakeWalker:
    @staticmethod
    def GetFirstChildElement(element):
        return element.children[0] if element.children else None

    @staticmethod
    def GetNextSiblingElement(element):
        if element.parent is None:
            return None
        siblings = element.parent.children
        index = siblings.index(element) + 1
        return siblings[index] if index < len(siblings) else None


class FakeAutomation:
    def __init__(self, root):
        self.root = root

    def ElementFromHandle(self, handle):
        return self.root

    @staticmethod
    def CreateTrueCondition():
        return object()

    @staticmethod
    def CreateTreeWalker(condition):
        return FakeWalker()


@pytest.fixture
def ui():
    invoke = FakePattern()
    value = FakePattern()
    expand = FakePattern()
    scroll = FakePattern()
    select = FakePattern()
    save = FakeElement(
        "Save",
        50000,
        automation_id="saveButton",
        class_name="Button",
        patterns={10000: invoke},
    )
    editor = FakeElement(
        "Editor",
        50004,
        automation_id="document",
        patterns={10002: value},
    )
    menu = FakeElement(
        "File",
        50011,
        automation_id="fileMenu",
        children=[save],
        patterns={10005: expand, 10004: scroll, 10010: select},
    )
    root = FakeElement("Notepad", 50032, children=[menu, editor])
    navigator = UIANavigator(
        automation_provider=lambda: FakeAutomation(root),
        foreground_window_provider=lambda: 42,
        window_title_provider=lambda handle: "Untitled - Notepad",
    )
    return navigator, {
        "invoke": invoke,
        "value": value,
        "expand": expand,
        "scroll": scroll,
        "select": select,
    }


def test_dump_tree_serializes_semantics_and_patterns(ui):
    navigator, _ = ui

    result = navigator.dump_tree()

    assert result["window_handle"] == 42
    assert result["window_title"] == "Untitled - Notepad"
    assert result["error"] is None
    assert result["truncated"] is False
    root = result["tree"][0]
    save = root["children"][0]["children"][0]
    assert save["automation_id"] == "saveButton"
    assert save["control_type"] == "Button"
    assert save["bounding_rect"] == {
        "left": 10,
        "top": 20,
        "right": 110,
        "bottom": 60,
    }
    assert save["patterns"] == ["Invoke"]


def test_dump_tree_marks_depth_truncation(ui):
    navigator, _ = ui

    result = navigator.dump_tree(max_depth=1)

    assert result["truncated"] is True
    assert result["tree"][0]["children"][0]["children"] == []


def test_find_element_supports_fields_and_semantic_path(ui):
    navigator, _ = ui

    by_fields = navigator.find_element(
        42, {"automation_id": "saveButton", "control_type": "button"}
    )
    by_path = navigator.find_element(42, {"xpath": "/Notepad/File/Save"})

    assert by_fields["name"] == "Save"
    assert by_path["automation_id"] == "saveButton"
    assert navigator.find_element(42, {"name": "Missing"}) is None


@pytest.mark.parametrize(
    ("query", "action", "text", "pattern_name", "expected_call"),
    [
        ({"name": "Save"}, "click", None, "invoke", ("invoke",)),
        ({"automation_id": "document"}, "type", "hello", "value", ("set_value", "hello")),
        ({"name": "File"}, "expand", None, "expand", ("expand",)),
        ({"name": "File"}, "collapse", None, "expand", ("collapse",)),
        ({"name": "File"}, "scroll", None, "scroll", ("scroll", 2, 4)),
        ({"name": "File"}, "select", None, "select", ("select",)),
    ],
)
def test_invoke_element_uses_expected_pattern(
    ui, query, action, text, pattern_name, expected_call
):
    navigator, patterns = ui

    result = navigator.invoke_element(42, query, action, text)

    assert result == {"success": True, "result": f"{action} completed", "error": None}
    assert patterns[pattern_name].calls[-1] == expected_call


def test_invoke_element_reports_invalid_requests(ui):
    navigator, _ = ui

    assert navigator.invoke_element(42, {"name": "Editor"}, "type")["error"] == (
        "Text is required for the 'type' action"
    )
    assert navigator.invoke_element(42, {"name": "Missing"}, "click")["error"] == (
        "No UIA element matched the query"
    )
    assert navigator.invoke_element(42, {"name": "Save"}, "delete")["error"] == (
        "Unsupported UIA action: delete"
    )


def test_unavailable_uia_returns_explicit_error():
    navigator = UIANavigator(
        automation_provider=lambda: None,
        foreground_window_provider=lambda: 42,
        window_title_provider=lambda handle: "",
    )

    result = navigator.dump_tree()

    assert result["tree"] == []
    assert result["error"] == "Windows UI Automation is unavailable"
