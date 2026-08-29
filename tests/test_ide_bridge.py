from src.system.ide_bridge import IDEBridge, default_ide_handlers


def test_bridge_requires_localhost_and_dispatches_context():
    bridge = IDEBridge(token="secret")
    assert bridge.dispatch({"token": "bad", "type": "GET_ACTIVE_CONTEXT"})["error"] == "unauthorized"
    bridge.dispatch({"token": "secret", "type": "EDITOR_CONTEXT",
                     "context": {"file": "main.py"}})
    assert bridge.dispatch({"token": "secret", "type": "GET_ACTIVE_CONTEXT"})["context"]["file"] == "main.py"


def test_bridge_editor_handlers():
    inserted = []
    bridge = IDEBridge(
        token="secret",
        handlers=default_ide_handlers(insert_code=inserted.append),
    )
    assert bridge.dispatch({"token": "secret", "type": "INSERT_CODE", "text": "x = 1"}) == {"ok": True}
    assert inserted == ["x = 1"]
    assert bridge.dispatch({"token": "secret", "type": "REPLACE_SELECTION"})["error"].startswith("unsupported")


def test_bridge_validates_binding():
    try:
        IDEBridge(host="0.0.0.0")
    except ValueError:
        pass
    else:
        raise AssertionError("non-localhost binding must be rejected")
