import json
import pytest
from unittest.mock import patch, MagicMock
from PyQt6.QtCore import QThread
from src.system.event_worker import EventStreamWorker

@patch('src.system.event_worker.requests.get')
def test_event_worker_parses_events(mock_get):
    worker = EventStreamWorker("http://127.0.0.1:4096")
    
    mock_response = MagicMock()
    
    def mock_iter_lines():
        yield b'data: {"anyOf": [{"id": "1", "status": "error"}]}'
        yield b'data: {"EventLspUpdated": {"diagnostics": [{"severity": "ERROR", "message": "Syntax"}]}}'
        worker._running = False
        
    mock_response.iter_lines.side_effect = lambda: mock_iter_lines()
    mock_response.__enter__.return_value = mock_response
    mock_get.return_value = mock_response
    
    lsp_errors = []
    worker.lsp_error_detected.connect(lambda e: lsp_errors.append(e))
    
    worker.run()
    
    assert len(lsp_errors) == 1
    assert lsp_errors[0] == {"diagnostics": [{"severity": "ERROR", "message": "Syntax"}]}
