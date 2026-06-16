import logging
from src.log_context import (
    get_correlation_id,
    set_correlation_id,
    reset_correlation_id,
    CorrelationIdDefault,
)


def test_set_and_get():
    cid = set_correlation_id()
    assert get_correlation_id() == cid
    assert len(cid) == 12


def test_set_provided_id():
    cid = set_correlation_id("my-test-id")
    assert get_correlation_id() == "my-test-id"


def test_reset():
    set_correlation_id("abc123")
    reset_correlation_id()
    assert get_correlation_id() == ""


def test_formatter_injects_cid():
    cid = set_correlation_id("test-cid")
    fmt = CorrelationIdDefault("[cid=%(correlation_id)s] %(message)s")
    record = logging.LogRecord("test", logging.INFO, "", 0, "msg", (), None)
    result = fmt.format(record)
    assert "test-cid" in result
    assert "msg" in result


def test_formatter_defaults_to_dash():
    reset_correlation_id()
    fmt = CorrelationIdDefault("[cid=%(correlation_id)s] %(message)s")
    record = logging.LogRecord("test", logging.INFO, "", 0, "msg", (), None)
    result = fmt.format(record)
    assert "[cid=-]" in result
