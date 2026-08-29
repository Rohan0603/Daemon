"""Semantic memory helpers."""

import importlib.util
from pathlib import Path

from .embedding_engine import EmbeddingEngine
from .rag_retriever import RAGRetriever

_legacy_spec = importlib.util.spec_from_file_location(
    "src._legacy_memory", Path(__file__).resolve().parent.parent / "memory.py"
)
if _legacy_spec is None or _legacy_spec.loader is None:
    raise ImportError("Unable to load legacy Memory store")
_legacy_module = importlib.util.module_from_spec(_legacy_spec)
_legacy_spec.loader.exec_module(_legacy_module)
Memory = _legacy_module.Memory

__all__ = ["EmbeddingEngine", "RAGRetriever", "Memory"]
