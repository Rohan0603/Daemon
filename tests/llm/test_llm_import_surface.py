from src.llm import (
    ContextManager,
    OpencodeWorker,
    StrandsAutonomousWorker,
    load_session, save_session, LLMSessionState,
)
from src.context_manager import ContextManager as LegacyContextManager
from src.opencode_worker import OpencodeWorker as LegacyOpencodeWorker
from src.strands_worker import StrandsAutonomousWorker as LegacyStrandsAutonomousWorker
from src.llm_session_persistence import (
    load_session as legacy_load_session,
    save_session as legacy_save_session,
    LLMSessionState as LegacyLLMSessionState,
)

def test_llm_package_exports_current_services():
    assert ContextManager is LegacyContextManager
    assert OpencodeWorker is LegacyOpencodeWorker
    assert StrandsAutonomousWorker is LegacyStrandsAutonomousWorker
    assert load_session is legacy_load_session
    assert save_session is legacy_save_session
    assert LLMSessionState is LegacyLLMSessionState