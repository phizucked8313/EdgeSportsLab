import pandas as pd

from fantasy_draft_model.engines.talent_engine import (
    calculate_rookie_talent_score,
)


def rookie_frame():
    return pd.DataFrame([
        {"player_name_clean": "Pick One", "position": "RB", "team": "AAA", "status": "Active", "is_rookie": True, "draft_number": 1},
        {"player_name_clean": "Pick Thirty Two", "position": "RB", "team": "BBB", "status": "Active", "is_rookie": True, "draft_number": 32},
        {"player_name_clean": "Pick One Hundred", "position": "RB", "team": "CCC", "status": "Active", "is_rookie": True, "draft_number": 100},
        {"player_name_clean": "Missing Pick", "position": "RB", "team": "DDD", "status": "Active", "is_rookie": True, "draft_number": None},
        {"player_name_clean": "Veteran", "position": "RB", "team": "EEE", "status": "Active", "is_rookie": False, "draft_number": 1},
    ])


def test_earlier_draft_capital_scores_higher_and_is_smooth():
    result = calculate_rookie_talent_score(rookie_frame()).set_index("player_name_clean")

    assert result.loc["Pick One", "rookie_talent_score"] > result.loc["Pick Thirty Two", "rookie_talent_score"]
    assert result.loc["Pick Thirty Two", "rookie_talent_score"] > result.loc["Pick One Hundred", "rookie_talent_score"]
    assert result.loc["Pick One", "rookie_talent_score"] == 100.0


def test_missing_draft_capital_is_low_but_nonzero_and_veterans_stay_neutral():
    result = calculate_rookie_talent_score(rookie_frame()).set_index("player_name_clean")

    assert result.loc["Missing Pick", "rookie_talent_score"] == 30.0
    assert result.loc["Veteran", "rookie_talent_score"] == 50.0
