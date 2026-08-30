from __future__ import annotations
import re
from .context_manager import ContextManager
from .opencode_worker import OpencodeWorker
from .ollama_worker import OllamaWorker
from .ollama_manager import OllamaManager
from .opencode_session_manager import OpenCodeSessionManager, OpencodeSessionManager
from .provider_gateway import (
    Provider, ProviderRequest, ProviderResult, ProviderError,
    Health, FallbackDecision, ProviderGateway,
)
from .interactive_fast_path import FastPathResult, InteractiveFastPath

def extract_dialogue_stream(accumulated_text: str) -> str:
    """Extract dialogue text from accumulated LLM output stream."""
    stripped = accumulated_text.strip()
    if not stripped:
        return ""

    # Find the start of JSON array or object
    json_start = -1
    for i, char in enumerate(accumulated_text):
        if char in ("[", "{"):
            json_start = i
            break
            
    if json_start != -1:
        # Ignore preamble before JSON start
        json_content = accumulated_text[json_start:]
        
        # Search for closed dialogue inside the JSON content
        match = re.search(r"\"dialogue\"\s*:\s*\"((?:[^\"\\]|\\.)*)\"", json_content)
        if match:
            try:
                val = match.group(1)
                if val.endswith("\\") and not val.endswith("\\\\"):
                    val = val[:-1]
                return val.encode("utf-8").decode("unicode_escape", errors="ignore")
            except Exception:
                return match.group(1)
                
        # Search for open dialogue inside the JSON content
        match_open = re.search(r"\"dialogue\"\s*:\s*\"((?:[^\"\\]|\\.|\\)*)$", json_content)
        if match_open:
            try:
                val = match_open.group(1)
                if val.endswith("\\") and not val.endswith("\\\\"):
                    val = val[:-1]
                return val.encode("utf-8").decode("unicode_escape", errors="ignore")
            except Exception:
                return match_open.group(1)
                
        return ""  # We have JSON start, but dialogue key is not here yet
    # No JSON delimiters found at all. Treat as free-form text.
    if stripped.startswith("`"):
        return ""
        
    return accumulated_text

__all__ = [
    "ContextManager",
    "OpencodeWorker",
    "OllamaWorker",
    "OllamaManager",
    "OpenCodeSessionManager",
    "OpencodeSessionManager",
    "Provider",
    "ProviderRequest",
    "ProviderResult",
    "ProviderError",
    "Health",
    "FallbackDecision",
    "ProviderGateway",
    "FastPathResult",
    "InteractiveFastPath",
    "extract_dialogue_stream",
]