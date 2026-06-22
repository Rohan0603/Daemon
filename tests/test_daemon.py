"""Tests for daemon.py — crash_dump rotation, boot helpers."""
import pathlib


def test_crash_dump_rotated_when_over_1mb(tmp_path):
    """crash_dump.log > 1MB on boot should be renamed to crash_dump.log.bak."""
    crash_log = tmp_path / "crash_dump.log"
    bak_log   = tmp_path / "crash_dump.log.bak"

    crash_log.write_bytes(b"x" * (1024 * 1024 + 1))  # 1MB + 1 byte

    from daemon import _rotate_crash_dump
    _rotate_crash_dump(crash_log)

    assert bak_log.exists()
    assert not crash_log.exists() or crash_log.stat().st_size == 0


def test_crash_dump_not_rotated_when_under_1mb(tmp_path):
    """crash_dump.log under 1MB should not be rotated."""
    crash_log = tmp_path / "crash_dump.log"
    crash_log.write_text("small log")

    from daemon import _rotate_crash_dump
    _rotate_crash_dump(crash_log)

    assert crash_log.exists()
    assert not (tmp_path / "crash_dump.log.bak").exists()


def test_crash_dump_not_rotated_when_missing(tmp_path):
    """No crash_dump.log should not raise."""
    crash_log = tmp_path / "crash_dump.log"

    from daemon import _rotate_crash_dump
    _rotate_crash_dump(crash_log)  # must not raise

    assert not crash_log.exists()
