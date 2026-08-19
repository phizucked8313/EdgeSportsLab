import pandas as pd

from fantasy_draft_model.engines.talent_engine import (
    calculate_rookie_talent_score,
    add_rookie_opportunity_score,
    add_rookie_position_curve,
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


def test_high_capital_rookie_gets_more_opportunity_than_late_pick():
    df = pd.DataFrame([
        {"player_name_clean": "Early", "position": "WR", "team": "AAA", "status": "Active", "is_rookie": True, "draft_number": 10},
        {"player_name_clean": "Late", "position": "WR", "team": "BBB", "status": "Active", "is_rookie": True, "draft_number": 220},
    ])
    df = calculate_rookie_talent_score(df)
    result = add_rookie_opportunity_score(df).set_index("player_name_clean")

    assert result.loc["Early", "rookie_opportunity_score"] > result.loc["Late", "rookie_opportunity_score"]
    assert result["rookie_opportunity_score"].between(35.0, 90.0).all()


def test_position_curves_are_distinct_and_veterans_are_neutral():
    df = pd.DataFrame([
        {"player_name_clean": "RB Rookie", "position": "RB", "is_rookie": True},
        {"player_name_clean": "WR Rookie", "position": "WR", "is_rookie": True},
        {"player_name_clean": "TE Rookie", "position": "TE", "is_rookie": True},
        {"player_name_clean": "QB Rookie", "position": "QB", "is_rookie": True},
        {"player_name_clean": "Veteran", "position": "RB", "is_rookie": False},
    ])
    result = add_rookie_position_curve(df).set_index("player_name_clean")

    assert result.loc["RB Rookie", "rookie_position_curve_score"] == 85.0
    assert result.loc["WR Rookie", "rookie_position_curve_score"] == 75.0
    assert result.loc["QB Rookie", "rookie_position_curve_score"] == 65.0
    assert result.loc["TE Rookie", "rookie_position_curve_score"] == 55.0
    assert result.loc["Veteran", "rookie_position_curve_score"] == 50.0
