import logging
from src.log_context import (
    get_correlation_id,
    set_correlation_id,
    reset_correlation_id,
    CorrelationIdDefault,
    RepeatedEventFilter,
    correlation_scope,
    redact_sensitive,
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


def test_correlation_scope_restores_previous_value():
    set_correlation_id("outer")
    with correlation_scope("inner") as cid:
        assert cid == "inner"
        assert get_correlation_id() == "inner"
    assert get_correlation_id() == "outer"


def test_redaction_masks_sensitive_fields_and_truncates():
    result = redact_sensitive(
        {"password": "secret", "message": "x" * 20, "nested": {"api_key": "key"}}
        , max_length=10
    )
    assert result["password"] == "[REDACTED]"
    assert result["nested"]["api_key"] == "[REDACTED]"
    assert result["message"].endswith("…")


def test_repeated_event_filter_is_bounded_and_suppresses():
    event_filter = RepeatedEventFilter(max_repeats=2, max_keys=2)
    records = [
        logging.LogRecord("test", logging.WARNING, "", 0, "repeat", (), None)
        for _ in range(3)
    ]
    assert [event_filter.filter(record) for record in records] == [True, True, False]
    for index in range(5):
        event_filter.filter(logging.LogRecord("test", logging.INFO, "", index, str(index), (), None))
    assert len(event_filter._events) == 2
