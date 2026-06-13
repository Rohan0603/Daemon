import json
import pytest
from unittest.mock import patch, MagicMock
from PyQt6.QtCore import QThread
from src.event_worker import EventStreamWorker

def test_event_worker_parses_events():
    worker = EventStreamWorker("http://127.0.0.1:4096")
    
    mock_response = MagicMock()
    mock_response.iter_lines.return_value = [
        b'data: {"anyOf": [{"id": "1", "status": "error"}]}',  # Malformed but we handle JSON
        b'data: {"id": "1", "status": "error"}'  # Will refine mock data based on exact API
    ]
    
    # We will just test that the signals emit properly.
    # To avoid blocking the test, we call the parser method directly.
    lsp_errors = []
    worker.lsp_error_detected.connect(lambda e: lsp_errors.append(e))
    
    payload = {"diagnostics": [{"severity": "ERROR", "message": "Syntax"}]}
    worker._handle_event({"EventLspUpdated": payload})
    
    assert len(lsp_errors) == 1
    assert lsp_errors[0] == payload
