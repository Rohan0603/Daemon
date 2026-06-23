# tests/autonomy/test_reactions.py
from __future__ import annotations

import pytest
from src.autonomy.reactions import build_reminder_effect, evaluate_risky_typing_reaction


def test_build_reminder_effect_returns_expression_action_not_deleted_fsm_state():
    reminders = {"abc": object()}
    effect = build_reminder_effect(reminders, "abc", "ship it")
    assert effect["removed"] is True
    assert effect["bubble"] == "ship it"
    assert effect["toast"] == ("Reminder", "ship it")
    assert effect["expression_action"]["name"] == "bounce"


def test_evaluate_risky_typing_reaction_returns_dialogue_and_action():
    risky_keywords = {
        "rm -rf": [{"dialogue": "Nope.", "action": "shake"}],
    }
    effect = evaluate_risky_typing_reaction(
        typing_content="please do rm -rf / now",
        current_len=23,
        last_len=0,
        risky_keywords=risky_keywords,
    )
    assert effect is not None
    assert effect["dialogue"] == "Nope."
    assert effect["action"] == "shake"
    assert effect["matched_keyword"] == "rm -rf"
    assert effect["new_last_len"] == 23


def test_evaluate_risky_typing_returns_none_no_match():
    risky_keywords = {
        "rm -rf": [{"dialogue": "Nope.", "action": "shake"}],
    }
    effect = evaluate_risky_typing_reaction(
        typing_content="just coding normally",
        current_len=20,
        last_len=0,
        risky_keywords=risky_keywords,
    )
    assert effect is None


def test_reminder_not_in_reminders():
    """Effect should have removed=False when rem_id not found."""
    reminders: dict = {}
    effect = build_reminder_effect(reminders, "missing", "hello")
    assert effect["removed"] is False
    assert effect["bubble"] == "hello"
