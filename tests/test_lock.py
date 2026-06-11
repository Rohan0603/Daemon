import os
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from daemon import _acquire_lock, _release_lock, _lock_path

def test_lock_lifecycle(tmp_path):
    with patch("daemon.STORAGE_DIR", tmp_path):
        pet_id = "testpet"
        lock = _lock_path(pet_id)
        assert not lock.exists()

        # 1. Acquire lock first time
        assert _acquire_lock(pet_id) is True
        assert lock.exists()
        assert int(lock.read_text().strip()) == os.getpid()

        # 2. Re-acquiring from same active process (should block)
        assert _acquire_lock(pet_id) is False

        # 3. Release lock
        _release_lock(pet_id)
        assert not lock.exists()

def test_acquire_lock_stale_pid(tmp_path):
    with patch("daemon.STORAGE_DIR", tmp_path):
        pet_id = "testpet"
        lock = _lock_path(pet_id)
        
        # Write an inactive PID
        lock.write_text("999999")
        
        # OpenProcess should fail on 999999, so treated as stale, and lock acquired
        assert _acquire_lock(pet_id) is True
        assert int(lock.read_text().strip()) == os.getpid()

def test_acquire_lock_recycled_pid_non_python(tmp_path):
    with patch("daemon.STORAGE_DIR", tmp_path):
        pet_id = "testpet"
        lock = _lock_path(pet_id)
        
        lock.write_text("12345")
        
        with patch("ctypes.windll.kernel32.OpenProcess", return_value=999) as mock_open, \
             patch("ctypes.windll.kernel32.QueryFullProcessImageNameW") as mock_query, \
             patch("ctypes.windll.kernel32.CloseHandle") as mock_close, \
             patch("ctypes.create_unicode_buffer") as mock_buf:
            
            mock_buf_obj = MagicMock()
            mock_buf_obj.value = r"C:\Windows\explorer.exe"
            mock_buf.return_value = mock_buf_obj
            mock_query.return_value = 1
            
            assert _acquire_lock(pet_id) is True
            mock_open.assert_called_once()
            mock_query.assert_called_once()
            mock_close.assert_called_once_with(999)
            
            assert int(lock.read_text().strip()) == os.getpid()

def test_acquire_lock_recycled_pid_python(tmp_path):
    with patch("daemon.STORAGE_DIR", tmp_path):
        pet_id = "testpet"
        lock = _lock_path(pet_id)
        
        lock.write_text("12345")
        
        with patch("ctypes.windll.kernel32.OpenProcess", return_value=999) as mock_open, \
             patch("ctypes.windll.kernel32.QueryFullProcessImageNameW") as mock_query, \
             patch("ctypes.windll.kernel32.CloseHandle") as mock_close, \
             patch("ctypes.create_unicode_buffer") as mock_buf:
            
            mock_buf_obj = MagicMock()
            mock_buf_obj.value = r"C:\Python39\python.exe"
            mock_buf.return_value = mock_buf_obj
            mock_query.return_value = 1
            
            assert _acquire_lock(pet_id) is False
            mock_open.assert_called_once()
            mock_query.assert_called_once()
            mock_close.assert_called_once_with(999)
            
            assert lock.read_text().strip() == "12345"
