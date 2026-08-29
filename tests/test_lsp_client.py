import io
import json

import pytest

from src.system.lsp_client import LSPClient, LSPError


def frame(message):
    payload = json.dumps(message, separators=(",", ":")).encode()
    return b"Content-Length: " + str(len(payload)).encode() + b"\r\n\r\n" + payload


class FakeStream(io.BytesIO):
    def flush(self):
        pass


class FakeProcess:
    def __init__(self, responses):
        self.stdin = FakeStream()
        self.stdout = FakeStream(b"".join(frame(item) for item in responses))
        self.returncode = None
        self.terminated = False

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = 0

    def kill(self):
        self.returncode = -9

    def wait(self, timeout=None):
        self.returncode = 0


def test_lsp_handshake_document_sync_and_notifications(tmp_path):
    process = FakeProcess([
        {"jsonrpc": "2.0", "id": 1, "result": {"capabilities": {}}},
    ])
    client = LSPClient(["pyright-langserver", "--stdio"], tmp_path, process_factory=lambda *a, **k: process)

    assert client.start() == {"capabilities": {}}
    client.did_open(tmp_path / "main.py", "x = 1", "python")
    client.did_change(tmp_path / "main.py", "x = 2", 2)

    sent = process.stdin.getvalue()
    assert b'"method":"initialize"' in sent
    assert b'"method":"initialized"' in sent
    assert b'"textDocument/didOpen"' in sent
    assert b'"textDocument/didChange"' in sent
    client.stop()
    assert process.terminated is True


def test_lsp_collects_diagnostics_and_queries_locations(tmp_path):
    uri = (tmp_path / "main.py").resolve().as_uri()
    process = FakeProcess([
        {"jsonrpc": "2.0", "method": "textDocument/publishDiagnostics",
         "params": {"uri": uri, "diagnostics": [{"message": "bad"}]}},
        {"jsonrpc": "2.0", "id": 1, "result": {}},
        {"jsonrpc": "2.0", "id": 2, "result": [{"uri": uri}]},
        {"jsonrpc": "2.0", "id": 3, "result": {"uri": uri}},
        {"jsonrpc": "2.0", "id": 4, "result": [{"uri": uri}]},
        {"jsonrpc": "2.0", "id": 5, "result": {"uri": uri}},
    ])
    client = LSPClient(["server"], tmp_path, process_factory=lambda *a, **k: process)

    client.start()
    assert client.get_diagnostics(tmp_path / "main.py") == [{"message": "bad"}]
    assert client.goto_definition(tmp_path / "main.py", 2, 3) == [{"uri": uri}]
    assert client.find_references(tmp_path / "main.py", 2, 3) == [{"uri": uri}]
    assert client.symbol_info(tmp_path / "main.py", 2, 3)["definitions"] == [{"uri": uri}]


def test_lsp_validates_workspace_positions_and_frames(tmp_path):
    client = LSPClient(["server"], tmp_path, process_factory=lambda *a, **k: None)

    with pytest.raises(ValueError, match="outside workspace"):
        client._document_uri(tmp_path.parent / "other.py")
    with pytest.raises(ValueError, match="positive"):
        client._location_request("x", "main.py", 0, 1)

    with pytest.raises(ValueError, match="command"):
        LSPClient([], tmp_path)
    with pytest.raises(LSPError):
        client._read()
