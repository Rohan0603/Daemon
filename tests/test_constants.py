import pytest
from src.constants import RISKY_KEYWORDS


def test_risky_keywords_is_dict():
    assert isinstance(RISKY_KEYWORDS, dict)

def test_risky_keywords_has_expected_keys():
    expected = {"--force", "rm -rf", "drop table", "TODO", "FIXME", "git push"}
    assert expected.issubset(RISKY_KEYWORDS.keys())

def test_risky_keyword_entries_have_dialogue_and_action():
    for keyword, responses in RISKY_KEYWORDS.items():
        assert len(responses) >= 2, f"{keyword} needs at least 2 responses"
        for item in responses:
            assert "dialogue" in item
            assert "action" in item

def test_risky_keyword_actions_are_valid():
    valid = {"idle", "wander", "celebrate", "devastated",
             "hyper", "shake", "bounce", "spin", "look_away", "fall"}
    for keyword, responses in RISKY_KEYWORDS.items():
        for item in responses:
            assert item["action"] in valid, f"{keyword}: {item['action']} not valid"
