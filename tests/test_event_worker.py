import json
import pytest
from unittest.mock import patch, MagicMock
from PyQt6.QtCore import QThread
from src.system.event_worker import EventStreamWorker

@patch('src.system.event_worker.time.sleep')
@patch('src.system.event_worker.logger')
@patch('src.system.event_worker.requests.get')
def test_event_worker_circuit_breaker_stops_after_max_failures(mock_get, mock_logger, mock_sleep):
    mock_get.side_effect = ConnectionRefusedError("No connection could be made because the target machine actively refused it")
    worker = EventStreamWorker("http://127.0.0.1:4096")

    worker.run()

    assert worker._running is False
    mock_logger.info.assert_any_call("EventStreamWorker disabled")


@patch('src.system.event_worker.time.sleep')
@patch('src.system.event_worker.requests.get')
def test_event_worker_circuit_breaker_resets_on_success(mock_get, mock_sleep):
    call_count = [0]
    worker = EventStreamWorker("http://127.0.0.1:4096")
    error = ConnectionRefusedError("refused")

    def side_effect(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] < 3:
            raise error
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.iter_lines.return_value = []
        worker._running = False
        return mock_resp

    mock_get.side_effect = side_effect

    worker.run()

    assert worker._consecutive_failures == 0


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
