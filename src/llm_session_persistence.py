"""Persistent LLM session state — saves and resumes opencode sessions across restarts.

Stores session ID, conversation history, and metadata to
``data/llm_session.json`` so the daemon can reconnect to the same opencode
session after a restart, preserving conversation context.

If the server has restarted and the old session is gone (404/500), a new
session is created but the previous conversation history is injected as
context in the first message, providing continuity.

Design:
- History is truncated to MAX_HISTORY_TURNS (30) to bound file size and context.
- Each turn stores role, content, and a monotonic timestamp for ordering.
- Writes use atomic swap (write .tmp → os.replace) to prevent corruption.
- Load handles missing/corrupt files gracefully (returns empty state).
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

import requests
from src.config import load_config, DEFAULT_SERVER_URL

logger = logging.getLogger(__name__)

MAX_HISTORY_TURNS = 30  # Keep last 30 exchanges (user + assistant pairs)

SESSION_FILE_NAME = "llm_session.json"


@dataclass
class ChatTurn:
    """A single turn in the conversation history."""

    role: str  # "user" | "assistant"
    content: str
    timestamp: float = 0.0

    def to_dict(self) -> dict:
        return {"role": self.role, "content": self.content, "timestamp": self.timestamp}

    @classmethod
    def from_dict(cls, data: dict) -> "ChatTurn":
        return cls(
            role=data["role"],
            content=data["content"],
            timestamp=data.get("timestamp", 0.0),
        )


@dataclass
class LLMSessionState:
    """Persisted state for an opencode LLM session."""

    session_id: Optional[str] = None
    model: str = ""
    skill: str = "kenny"
    history: list[ChatTurn] = field(default_factory=list)
    summary: str = ""
    created_at: float = 0.0
    last_used_at: float = 0.0

    def add_turn(self, role: str, content: str) -> None:
        """Append a conversation turn, trimming to MAX_HISTORY_TURNS."""
        self.history.append(ChatTurn(role=role, content=content, timestamp=time.time()))
        if len(self.history) > MAX_HISTORY_TURNS:
            self.history = self.history[-MAX_HISTORY_TURNS:]
        self.last_used_at = time.time()

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "model": self.model,
            "skill": self.skill,
            "history": [t.to_dict() for t in self.history],
            "summary": self.summary,
            "created_at": self.created_at,
            "last_used_at": self.last_used_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "LLMSessionState":
        history = [
            ChatTurn.from_dict(t) for t in data.get("history", [])
            if isinstance(t, dict) and "role" in t and "content" in t
        ]
        return cls(
            session_id=data.get("session_id"),
            model=data.get("model", ""),
            skill=data.get("skill", "kenny"),
            history=history,
            summary=data.get("summary", ""),
            created_at=data.get("created_at", 0.0),
            last_used_at=data.get("last_used_at", 0.0),
        )

    @property
    def history_context(self) -> str:
        """Format history as compact context for injecting into a new session."""
        if not self.history:
            return ""
        lines = []
        lines.append("[Previous conversation resumed after restart]")
        for turn in self.history[-MAX_HISTORY_TURNS:]:
            label = "User" if turn.role == "user" else "Assistant"
            # Truncate long turns to avoid ballooning the prompt
            content = turn.content[:500] if len(turn.content) > 500 else turn.content
            lines.append(f"{label}: {content}")
        if self.summary:
            lines.append(f"[Conversation summary: {self.summary}]")
        return "\n".join(lines)


def _get_session_path() -> Path:
    """Return the path to the session persistence file."""
    from src.constants import STORAGE_DIR
    return STORAGE_DIR / SESSION_FILE_NAME


def save_session(state: LLMSessionState) -> None:
    """Save session state to disk using atomic write."""
    # Generate and set summary if we have a session ID
    if state.session_id:
        try:
            config = load_config()
            summary = _generate_summary(state.session_id, state.history, config)
            if summary:
                state.summary = summary
        except Exception as e:
            logger.warning("Failed to generate summary for session %s: %s", state.session_id, e)
            # Continue without setting summary
    
    path = _get_session_path()
    tmp_path = path.with_suffix(".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = state.to_dict()
        tmp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp_path.replace(path)
        logger.debug("Saved LLM session state (%d turns, summary: %d chars) to %s", 
                    len(state.history), len(state.summary), path)
    except Exception as e:
        logger.warning("Failed to save LLM session state: %s", e)


def load_session() -> LLMSessionState:
    """Load session state from disk. Returns empty state on any failure."""
    path = _get_session_path()
    if not path.exists():
        logger.debug("No saved LLM session found at %s", path)
        return LLMSessionState()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        state = LLMSessionState.from_dict(data)
        logger.debug(
            "Loaded LLM session %s (%d turns) from %s",
            state.session_id or "none",
            len(state.history),
            path,
        )
        return state
    except (json.JSONDecodeError, OSError, ValueError) as e:
        logger.warning("Failed to load LLM session from %s: %s", path, e)
        return LLMSessionState()


def _generate_summary(session_id: str, history: list[ChatTurn], config: dict) -> str:
    """Generate a summary of the conversation history using the opencode server.
    
    Args:
        session_id: The ID of the session to summarize
        history: List of ChatTurn objects representing the conversation history
        config: The application configuration dictionary
        
    Returns:
        A string summary of the conversation, or empty string if summarization fails
    """
    if not session_id or not history:
        return ""
    
    try:
        # Format history as a prompt
        history_lines = []
        for turn in history:
            label = "User" if turn.role == "user" else "Assistant"
            # Truncate long turns to avoid excessively long prompts
            content = turn.content[:1000] if len(turn.content) > 1000 else turn.content
            history_lines.append(f"{label}: {content}")
        
        history_text = "\n".join(history_lines)
        
        # Create summarization prompt
        prompt = f"""Please provide a concise summary of the following conversation:

{history_text}

Summary:"""
        
        # Get LLM configuration
        llm_cfg = config.get("llm", {})
        server_url = llm_cfg.get("server_url") or DEFAULT_SERVER_URL
        timeout_sec = llm_cfg.get("timeout_sec", 180)

        # Create a temporary session to avoid polluting the active session
        try:
            create_resp = requests.post(f"{server_url}/session", json={}, timeout=10)
            if create_resp.status_code >= 400:
                logger.warning("Failed to create temporary summary session: HTTP %s", create_resp.status_code)
                return ""
            temp_session_id = create_resp.json().get("session_id")
            if not temp_session_id:
                logger.warning("Failed to get temporary summary session ID")
                return ""
        except Exception as e:
            logger.warning("Failed to create temporary summary session: %s", e)
            return ""

        try:
            # Prepare the request payload
            payload = {
                "parts": [{"type": "text", "text": prompt}],
                "structured": {"type": "object", "properties": {"summary": {"type": "string"}}, "required": ["summary"]},
            }
            
            # Send the request to the temporary session
            response = requests.post(
                f"{server_url}/session/{temp_session_id}/message",
                json=payload,
                timeout=timeout_sec
            )
            
            if response.status_code >= 400:
                logger.warning("Failed to generate summary: HTTP %s", response.status_code)
                return ""
            
            # Extract summary from response
            data = response.json()
            parts = data.get("parts", [])
            text_parts = [p.get("text", "") for p in parts if p.get("type") == "text"]
            summary = "".join(text_parts).strip()
        finally:
            # Always clean up the temporary session
            try:
                requests.delete(f"{server_url}/session/{temp_session_id}", timeout=5)
            except Exception as e:
                logger.debug("Failed to delete temporary summary session: %s", e)
        
        # If the response is wrapped in markdown or has extra text, try to extract just the summary
        # Look for common patterns like "Summary:" or just take the last meaningful line
        if summary:
            lines = [line.strip() for line in summary.split("\n") if line.strip()]
            if lines:
                # Take the last non-empty line as the summary, or join if it's short
                if len(lines) == 1:
                    return lines[0]
                elif len(lines) > 1 and len(lines[-1]) < 200:  # Last line is reasonably short
                    return lines[-1]
                else:
                    # Join last few lines if they seem to be part of the summary
                    return " ".join(lines[-3:]) if len(lines) >= 3 else " ".join(lines)
        
        return summary
        
    except requests.exceptions.RequestException as e:
        logger.warning("Failed to generate summary due to request error: %s", e)
        return ""
    except Exception as e:
        logger.warning("Failed to generate summary due to unexpected error: %s", e)
        return ""


def clear_session() -> None:
    """Delete the saved session state file."""
    path = _get_session_path()
    try:
        if path.exists():
            path.unlink()
            logger.debug("Cleared saved LLM session at %s", path)
    except OSError as e:
        logger.warning("Failed to clear LLM session: %s", e)
