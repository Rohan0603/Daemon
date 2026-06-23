from __future__ import annotations
import random
import re

def build_reminder_effect(reminders: dict, rem_id: str, msg: str) -> dict:
    removed = rem_id in reminders
    if removed:
        del reminders[rem_id]
    return {
        "removed": removed,
        "toast": ("Reminder", msg),
        "bubble": msg,
        "expression_action": {"name": "bounce", "duration_ms": 3000, "params": {}},
    }

def evaluate_risky_typing_reaction(
    typing_content: str,
    current_len: int,
    last_len: int,
    risky_keywords: dict[str, list[dict]],
) -> dict | None:
    lower = typing_content.lower()
    for keyword, responses in risky_keywords.items():
        kw = keyword.lower()
        matched = re.search(r"\b" + re.escape(kw) + r"\b", lower) if kw[-1].isalpha() else (kw in lower)
        if not matched:
            continue
        item = random.choice(responses)
        return {
            "dialogue": item["dialogue"],
            "action": item["action"],
            "matched_keyword": keyword,
            "new_last_len": current_len,
        }
    if current_len <= last_len:
        return None
    return None