import pandas as pd

from fantasy_draft_model.engines.talent_engine import (
    calculate_rookie_talent_score,
    add_rookie_opportunity_score,
    add_rookie_position_curve,
    add_touch_efficiency_metrics,
    add_rookie_ramp_factor,
    add_rookie_team_environment,
    add_rookie_projection_components,
    add_rookie_baseline_projection,
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


def test_touch_math_and_fantasy_points_per_touch():
    df = pd.DataFrame([{
        "player_name_clean": "Example RB",
        "position": "RB",
        "is_rookie": False,
        "carries": 14,
        "receptions": 5,
        "custom_fantasy_points": 19.0,
    }])
    result = add_touch_efficiency_metrics(df)

    assert result.loc[0, "touches"] == 19
    assert result.loc[0, "fantasy_points_per_touch"] == 1.0


def test_confirmed_starter_rb_gets_more_opportunity_than_backup():
    df = pd.DataFrame([
        {"player_name_clean": "Starter", "position": "RB", "team": "AAA", "status": "Active", "is_rookie": True, "draft_number": 20, "rookie_role": "STARTER"},
        {"player_name_clean": "Backup", "position": "RB", "team": "AAA", "status": "Active", "is_rookie": True, "draft_number": 20, "rookie_role": "BACKUP"},
    ])
    df = calculate_rookie_talent_score(df)
    result = add_rookie_opportunity_score(df).set_index("player_name_clean")

    assert result.loc["Starter", "rookie_opportunity_score"] > result.loc["Backup", "rookie_opportunity_score"]


def test_wr_gets_modest_six_week_ramp_and_rb_does_not():
    df = pd.DataFrame([
        {"player_name_clean": "WR", "position": "WR", "is_rookie": True},
        {"player_name_clean": "RB", "position": "RB", "is_rookie": True},
        {"player_name_clean": "Veteran", "position": "WR", "is_rookie": False},
    ])
    result = add_rookie_ramp_factor(df).set_index("player_name_clean")

    assert result.loc["WR", "rookie_ramp_weeks"] == 6
    assert result.loc["WR", "rookie_ramp_factor"] == 0.96
    assert result.loc["RB", "rookie_ramp_factor"] == 1.0
    assert result.loc["Veteran", "rookie_ramp_factor"] == 1.0


def test_team_environment_defaults_to_neutral():
    df = pd.DataFrame([
        {"player_name_clean": "Rookie", "position": "RB", "is_rookie": True},
    ])
    result = add_rookie_team_environment(df)
    assert result.loc[0, "rookie_team_environment_multiplier"] == 1.0


def test_composite_score_rewards_stronger_available_inputs():
    df = pd.DataFrame([
        {"player_name_clean": "Strong", "position": "WR", "team": "AAA", "status": "Active", "is_rookie": True, "draft_number": 8},
        {"player_name_clean": "Weak", "position": "WR", "team": "BBB", "status": "Active", "is_rookie": True, "draft_number": 220},
    ])
    result = add_rookie_projection_components(df).set_index("player_name_clean")

    assert result.loc["Strong", "rookie_projection_score"] > result.loc["Weak", "rookie_projection_score"]
    assert result.loc["Strong", "rookie_prospect_profile_score"] == 50.0
    assert result.loc["Weak", "rookie_team_environment_multiplier"] == 1.0


POSITION_BOUNDS = {
    "RB": (70.0, 290.0),
    "WR": (60.0, 260.0),
    "TE": (35.0, 190.0),
    "QB": (40.0, 330.0),
}


def test_rookie_baselines_respect_position_specific_bounds():
    rows = []
    for position in POSITION_BOUNDS:
        rows.append({
            "player_name_clean": f"{position} Rookie",
            "position": position,
            "team": "AAA",
            "status": "Active",
            "is_rookie": True,
            "draft_number": 1,
        })
    df = add_rookie_projection_components(pd.DataFrame(rows))
    result = add_rookie_baseline_projection(df)

    for _, row in result.iterrows():
        low, high = POSITION_BOUNDS[row["position"]]
        assert low <= row["rookie_baseline_projection"] <= high


def test_veterans_and_unsupported_positions_do_not_get_rookie_baseline():
    df = pd.DataFrame([
        {"player_name_clean": "Veteran", "position": "RB", "is_rookie": False, "rookie_projection_score": 100.0},
        {"player_name_clean": "Rookie K", "position": "K", "is_rookie": True, "rookie_projection_score": 100.0},
    ])
    result = add_rookie_baseline_projection(df).set_index("player_name_clean")

    assert result.loc["Veteran", "rookie_baseline_projection"] == 0.0
    assert result.loc["Rookie K", "rookie_baseline_projection"] == 0.0
