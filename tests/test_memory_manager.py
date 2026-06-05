from __future__ import annotations
import pytest
from collections import deque
from unittest.mock import MagicMock, patch, call


# ---------------------------------------------------------------------------
# Fixtures — bypass __init__ to inject a mock db directly
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_crud():
    return MagicMock()


@pytest.fixture
def mgr_db(mock_crud):
    """MemoryManager instance with a live mock CRUD client."""
    from src.memory_manager import MemoryManager
    mgr = MemoryManager.__new__(MemoryManager)
    mgr.crud = mock_crud
    mgr._uid = "test-uid"
    mgr._pending_writes = deque()
    return mgr


@pytest.fixture
def mgr_no_db():
    """MemoryManager with unavailable CRUD (creds missing)."""
    from src.memory_manager import MemoryManager
    mgr = MemoryManager.__new__(MemoryManager)
    unavailable_crud = MagicMock()
    unavailable_crud.available = False
    unavailable_crud.get.return_value = None
    unavailable_crud.set.return_value = False
    unavailable_crud.add.return_value = None
    unavailable_crud.read_all_text.return_value = []
    mgr.crud = unavailable_crud
    mgr._uid = "test-uid"
    mgr._pending_writes = deque()
    return mgr


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

def test_constructor_accepts_crud_and_uid():
    """Constructor stores crud and uid."""
    from src.firebase_crud import FirebaseCRUD
    from src.memory_manager import MemoryManager
    crud = MagicMock(spec=FirebaseCRUD)
    mgr = MemoryManager(crud=crud, uid="test-uid")
    assert mgr._uid == "test-uid"
    assert mgr.crud is crud


# ---------------------------------------------------------------------------
# load_current_brain
# ---------------------------------------------------------------------------

def test_load_brain_returns_firestore_doc(mgr_db, mock_crud):
    """When doc exists, return its dict."""
    mock_crud.get.return_value = {
        "daemon_origin": "test_origin",
        "user_habits": ["codes at night"],
        "long_term_goals": ["ship daemon"],
    }

    brain = mgr_db.load_current_brain()

    assert brain["daemon_origin"] == "test_origin"
    assert brain["user_habits"] == ["codes at night"]
    mock_crud.get.assert_called_with("daemon_data/test-uid", "core_brain")


def test_load_brain_returns_defaults_when_doc_missing(mgr_db, mock_crud):
    """When Firestore doc doesn't exist, return default dict."""
    mock_crud.get.return_value = None

    brain = mgr_db.load_current_brain()

    assert "daemon_origin" in brain
    assert "user_habits" in brain
    assert "long_term_goals" in brain


def test_load_brain_returns_defaults_when_db_none(mgr_no_db):
    """When db is None, return default dict without error."""
    brain = mgr_no_db.load_current_brain()
    assert "daemon_origin" in brain
    assert "user_habits" in brain
    assert "long_term_goals" in brain


def test_load_brain_returns_defaults_on_exception(mgr_db, mock_crud):
    """CRUD error -> logged at warning level, returns defaults."""
    mock_crud.get.side_effect = Exception("network error")
    with patch("src.memory_manager.logger") as mock_log:
        brain = mgr_db.load_current_brain()
        assert "daemon_origin" in brain
        mock_log.warning.assert_called_once()


# ---------------------------------------------------------------------------
# update_brain
# ---------------------------------------------------------------------------

def test_update_brain_calls_set_with_merge(mgr_db, mock_crud):
    """update_brain uses set(..., merge=True)."""
    new_data = {"daemon_origin": "updated", "user_habits": [], "long_term_goals": []}
    mock_crud.set.return_value = True

    mgr_db.update_brain(new_data)

    mock_crud.set.assert_called_with("daemon_data/test-uid", "core_brain", new_data, merge=True)


def test_update_brain_no_op_when_db_none(mgr_no_db):
    """db=None -> update_brain does nothing, no exception."""
    mgr_no_db.update_brain({"daemon_origin": "x"})  # must not raise


def test_update_brain_silent_on_exception(mgr_db, mock_crud):
    """CRUD.set returns False -> logged at warning level, no crash."""
    mock_crud.set.return_value = False
    with patch("src.memory_manager.logger") as mock_log:
        mgr_db.update_brain({"daemon_origin": "x"})
        mock_log.warning.assert_called_once()


# ---------------------------------------------------------------------------
# add_diary_entry
# ---------------------------------------------------------------------------

def test_add_diary_entry_adds_to_collection(mgr_db, mock_crud):
    """add_diary_entry writes text + timestamp to daemon_diary."""
    mock_crud.add.return_value = "abc123"
    mgr_db.add_diary_entry("Daemon danced today")

    mock_crud.add.assert_called_once()
    args, _ = mock_crud.add.call_args
    assert args[0] == "daemon_diary/test-uid/entries"
    assert args[1]["text"] == "Daemon danced today"
    assert isinstance(args[1]["timestamp"], int)


def test_add_diary_entry_no_op_when_db_none(mgr_no_db):
    """db=None -> add_diary_entry does nothing, no exception."""
    mgr_no_db.add_diary_entry("should be ignored")  # must not raise


def test_add_diary_entry_silent_on_exception(mgr_db, mock_crud):
    """CRUD.add returns None -> logged at warning level, no crash."""
    mock_crud.add.return_value = None
    with patch("src.memory_manager.logger") as mock_log:
        mgr_db.add_diary_entry("fail silently")
        mock_log.warning.assert_called_once()


# ---------------------------------------------------------------------------
# fetch_all_diary_entries  (replaces get_recent_diary — full fetch once at startup)
# ---------------------------------------------------------------------------

def test_fetch_all_returns_all_entries_ascending(mgr_db, mock_crud):
    """Returns all entries in ASCENDING order (oldest first)."""
    mock_crud.read_all_text.return_value = ["old", "middle", "recent"]

    result = mgr_db.fetch_all_diary_entries()

    assert result == ["old", "middle", "recent"]
    mock_crud.read_all_text.assert_called_with(
        "daemon_diary/test-uid/entries", text_field="text", order_by="timestamp", limit=200, ascending=True
    )


def test_fetch_all_returns_empty_when_db_none(mgr_no_db):
    """db=None -> returns empty list, no exception."""
    assert mgr_no_db.fetch_all_diary_entries() == []


def test_fetch_all_returns_empty_on_exception(mgr_db, mock_crud):
    """CRUD error -> logged at warning level, returns empty list."""
    mock_crud.read_all_text.side_effect = Exception("connection reset")
    with patch("src.memory_manager.logger") as mock_log:
        result = mgr_db.fetch_all_diary_entries()
        assert result == []
        mock_log.warning.assert_called_once()


def test_fetch_all_handles_corrupt_doc(mgr_db, mock_crud):
    """If read_all_text filters corrupt docs, only valid entries pass through."""
    mock_crud.read_all_text.return_value = ["valid"]
    result = mgr_db.fetch_all_diary_entries()
    assert result == ["valid"]


# ---------------------------------------------------------------------------
# push_pending_diaries
# ---------------------------------------------------------------------------

def test_push_pending_pushes_unsynced_only(mgr_db, mock_crud):
    """Only entries after synced count are pushed to Firebase."""
    diary_store = MagicMock()
    mock_crud.add.return_value = "id"
    mgr_db.push_pending_diaries(diary_store, ["a", "b", "c"], synced=2)
    # Only "c" is pending (index 2)
    assert mock_crud.add.call_count == 1
    args, _ = mock_crud.add.call_args
    assert args[0] == "daemon_diary/test-uid/entries"
    assert args[1]["text"] == "c"
    diary_store.write.assert_called_once_with(["a", "b", "c"], 3)


def test_push_pending_no_op_when_all_synced(mgr_db, mock_crud):
    """When synced == len(entries), no Firebase writes."""
    diary_store = MagicMock()
    mgr_db.push_pending_diaries(diary_store, ["a", "b"], synced=2)
    mock_crud.add.assert_not_called()


def test_push_pending_no_op_when_db_none(mgr_no_db):
    """CRUD unavailable -> no-op, returns original synced count."""
    diary_store = MagicMock()
    result = mgr_no_db.push_pending_diaries(diary_store, ["a"], synced=0)
    assert result == 0
    diary_store.write.assert_not_called()


def test_push_pending_returns_updated_synced(mgr_db, mock_crud):
    """Returns len(entries) as new synced count; delegates write to DiaryStore."""
    diary_store = MagicMock()
    mock_crud.add.return_value = "id"
    result = mgr_db.push_pending_diaries(diary_store, ["a", "b", "c"], synced=0)
    assert result == 3
    diary_store.write.assert_called_once_with(["a", "b", "c"], 3)


# ---------------------------------------------------------------------------
# sync_to_local
# ---------------------------------------------------------------------------

def test_sync_to_local_writes_brain_fields_to_memory(tmp_path):
    """sync_to_local reads core_brain from Firestore and writes to local Memory."""
    from src.memory_manager import MemoryManager
    from src.memory import Memory

    mem = Memory(path=str(tmp_path / "mem.json"))

    brain = {
        "user_name": "Rohan",
        "user_profession": "SDE",
        "user_habits": ["Habit A", "Habit B"],
        "daemon_quirks": ["Quirk X"],
        "daemon_origin": "Born here",
    }

    mock_crud = MagicMock()
    mock_crud.available = True
    mock_crud.get.return_value = brain

    mm = MemoryManager.__new__(MemoryManager)
    mm.crud = mock_crud
    mm._uid = "test-uid"
    mm._pending_writes = deque()

    mm.sync_to_local(mem)

    assert mem.recall("user_name") == "Rohan"
    assert mem.recall("user_profession") == "SDE"
    assert mem.recall("user_habits") == "Habit A; Habit B"
    assert mem.recall("daemon_quirks") == "Quirk X"
    assert mem.recall("daemon_origin") == "Born here"


def test_sync_to_local_no_op_when_crud_unavailable(tmp_path):
    """sync_to_local returns early if crud unavailable."""
    from src.memory_manager import MemoryManager
    from src.memory import Memory

    mem = Memory(path=str(tmp_path / "mem.json"))
    mock_crud = MagicMock()
    mock_crud.available = False
    mm = MemoryManager.__new__(MemoryManager)
    mm.crud = mock_crud
    mm._uid = "test-uid"
    mm._pending_writes = deque()

    mm.sync_to_local(mem)  # must not raise

    assert mem.get_all() == {}


# ---------------------------------------------------------------------------
# sync_from_local
# ---------------------------------------------------------------------------

def test_sync_from_local_pushes_memory_facts(tmp_path):
    """sync_from_local reads Memory facts and pushes to Firestore core_brain top-level fields."""
    from src.memory_manager import MemoryManager
    from src.memory import Memory

    mem = Memory(path=str(tmp_path / "mem.json"))
    mem.remember("user_name", "Rohan")
    mem.remember("daemon_quirks", "Collects Hot Wheels")

    mock_crud = MagicMock()
    mock_crud.available = True
    mock_crud.get.return_value = {}
    mock_crud.set.return_value = True

    mm = MemoryManager.__new__(MemoryManager)
    mm.crud = mock_crud
    mm._uid = "test-uid"
    mm._pending_writes = deque()

    mm.sync_from_local(mem)

    mock_crud.get.assert_called_with("daemon_data/test-uid", "core_brain")
    mock_crud.set.assert_called_once()
    call_args = mock_crud.set.call_args
    pushed = call_args[0][2]
    assert pushed["user_name"] == "Rohan"
    assert pushed["daemon_quirks"] == "Collects Hot Wheels"
    assert call_args[1]["merge"] is True


def test_sync_from_local_no_op_when_crud_unavailable(tmp_path):
    """sync_from_local returns early if crud unavailable."""
    from src.memory_manager import MemoryManager
    from src.memory import Memory

    mem = Memory(path=str(tmp_path / "mem.json"))
    mem.remember("k", "v")
    mock_crud = MagicMock()
    mock_crud.available = False
    mm = MemoryManager.__new__(MemoryManager)
    mm.crud = mock_crud
    mm._uid = "test-uid"
    mm._pending_writes = deque()

    mm.sync_from_local(mem)  # must not raise


def test_sync_from_local_no_op_when_memory_empty(tmp_path):
    """sync_from_local does nothing if Memory has no facts."""
    from src.memory_manager import MemoryManager
    from src.memory import Memory

    mem = Memory(path=str(tmp_path / "mem.json"))
    mock_crud = MagicMock()
    mock_crud.available = True
    mm = MemoryManager.__new__(MemoryManager)
    mm.crud = mock_crud
    mm._uid = "test-uid"
    mm._pending_writes = deque()

    mm.sync_from_local(mem)

    mock_crud.set.assert_not_called()


def test_sync_from_local_silent_on_exception(tmp_path):
    """sync_from_local logs info on CRUD.set failure (crud handles exceptions)."""
    from src.memory_manager import MemoryManager
    from src.memory import Memory

    mem = Memory(path=str(tmp_path / "mem.json"))
    mem.remember("k", "v")
    mock_crud = MagicMock()
    mock_crud.available = True
    mock_crud.get.return_value = {}
    mock_crud.set.return_value = False

    mm = MemoryManager.__new__(MemoryManager)
    mm.crud = mock_crud
    mm._uid = "test-uid"
    mm._pending_writes = deque()

    mm.sync_from_local(mem)
    mock_crud.set.assert_called_once()


# ── _BRAIN_SCHEMA & apply_brain_update tests ─────────────────────────────────


def test_apply_brain_update_strips_locked_fields():
    from src.memory_manager import apply_brain_update, _BRAIN_SCHEMA
    locked_keys = {k for k, v in _BRAIN_SCHEMA.items() if v["locked"]}
    update = {k: "new value" for k in _BRAIN_SCHEMA}
    result = apply_brain_update(update)
    for k in locked_keys:
        assert k not in result, f"{k} is locked but appeared in result"


def test_apply_brain_update_appends_to_list_fields():
    from src.memory_manager import apply_brain_update
    update = {"blackmail_material": ["new item 1", "new item 2"]}
    result = apply_brain_update(update)
    assert "blackmail_material" in result
    assert "new item 1" in result["blackmail_material"]
    assert "new item 2" in result["blackmail_material"]


def test_apply_brain_update_deduplicates_list_items():
    from src.memory_manager import apply_brain_update
    update = {"blackmail_material": ["same item", "same item"]}
    result = apply_brain_update(update)
    assert result["blackmail_material"] == ["same item"]


def test_apply_brain_update_rejects_unknown_field():
    from src.memory_manager import apply_brain_update
    result = apply_brain_update({"nonexistent_field": "value"})
    assert result == {}


def test_apply_brain_update_rejects_wrong_type():
    from src.memory_manager import apply_brain_update, _BRAIN_SCHEMA
    list_field = next(k for k, v in _BRAIN_SCHEMA.items()
                      if v["type"] == "list" and not v["locked"])
    result = apply_brain_update({list_field: "not a list"})
    assert list_field not in result


def test_apply_brain_update_editable_string_fields_accepted():
    from src.memory_manager import apply_brain_update
    result = apply_brain_update({"long_term_goals": ["new goal"]})
    assert "long_term_goals" in result
    assert "new goal" in result["long_term_goals"]


# ---------------------------------------------------------------------------
# Retry queue
# ---------------------------------------------------------------------------

def test_add_diary_entry_queues_on_failure(mgr_db, mock_crud):
    """Failed Firebase write is queued for retry."""
    mock_crud.add.return_value = None
    mgr_db.add_diary_entry("test entry")
    assert len(mgr_db._pending_writes) == 1
    assert mgr_db._pending_writes[0][0] == "diary"


def test_retry_pending_writes_succeeds(mgr_db, mock_crud):
    """retry_pending_writes flushes queued writes."""
    mock_crud.add.return_value = "id"
    mock_crud.set.return_value = True
    mgr_db._pending_writes.append(("diary", {"text": "retry me", "timestamp": None}))
    result = mgr_db.retry_pending_writes()
    assert result == 1
    assert len(mgr_db._pending_writes) == 0


def test_retry_pending_writes_no_op_when_db_none(mgr_no_db):
    """retry_pending_writes returns 0 when crud unavailable (add returns None)."""
    mgr_no_db._pending_writes.append(("diary", {}))
    assert mgr_no_db.retry_pending_writes() == 0


def test_fetch_all_diary_respects_limit(mgr_db, mock_crud):
    """fetch_all_diary_entries passes limit to CRUD."""
    mgr_db.fetch_all_diary_entries(limit=50)
    mock_crud.read_all_text.assert_called_with(
        "daemon_diary/test-uid/entries", text_field="text", order_by="timestamp", limit=50, ascending=True
    )
