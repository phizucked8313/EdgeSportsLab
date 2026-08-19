import pandas as pd

from fantasy_draft_model.engines import projection_engine


def test_build_projections_attaches_current_injury_state_and_blocks_positive_self_ripple(
    monkeypatch,
):
    players = pd.DataFrame([
        {
            "player_id": "00-injured-wr",
            "player_name_clean": "Injured WR",
            "team": "AAA",
            "position": "WR",
            "is_fantasy_draftable": True,
        },
        {
            "player_id": "00-healthy-wr",
            "player_name_clean": "Healthy WR",
            "team": "AAA",
            "position": "WR",
            "is_fantasy_draftable": True,
        },
    ])

    injuries = pd.DataFrame([
        {
            "gsis_id": "00-injured-wr",
            "player_name": "Injured WR",
            "team": "AAA",
            "position": "WR",
            "report_status": "Out",
            "edgeiq_injury_body_part": "Hamstring",
            "injury_data_quality": "D",
            "injury_source": "Sleeper",
            "edgeiq_role": "STARTER",
            "injury_unit": "PASS_CATCHERS",
            "player_injury_impact": 5.0,
        }
    ])

    monkeypatch.setattr(
        projection_engine,
        "load_league_settings",
        lambda league_key: {},
    )
    monkeypatch.setattr(
        projection_engine,
        "build_player_profiles",
        lambda league_key: players.copy(),
    )

    for name in [
        "add_rookie_projection_components",
        "add_rookie_baseline_projection",
        "add_per_game_metrics",
        "add_rushing_usage_scores",
        "add_qb_contact_exposure",
        "calculate_opportunity_score",
        "add_target_regression",
        "add_manual_adjustments",
        "calculate_floor_ceiling",
        "calculate_projection_confidence",
        "calculate_edgescore",
        "calculate_tiers",
    ]:
        monkeypatch.setattr(
            projection_engine,
            name,
            lambda df: df.copy(),
        )

    def add_injury_scores(df):
        result = df.copy()
        result["injury_risk_score"] = 12.0
        result["durability_score"] = 88.0
        return result

    def calculate_projection(df):
        result = df.copy()
        result["projected_points"] = 100.0
        return result

    def neutral_opportunity(df, injury_df):
        result = df.copy()
        result["injury_opportunity_multiplier"] = 1.0
        return result

    monkeypatch.setattr(projection_engine, "add_injury_scores", add_injury_scores)
    monkeypatch.setattr(projection_engine, "injury_risk_label", lambda score: "LOW")
    monkeypatch.setattr(projection_engine, "calculate_projection", calculate_projection)
    monkeypatch.setattr(
        projection_engine,
        "load_normalized_current_injuries",
        lambda: injuries.copy(),
    )
    monkeypatch.setattr(
        projection_engine,
        "add_team_injury_impact",
        lambda df: df.copy(),
    )
    monkeypatch.setattr(
        projection_engine,
        "add_player_opportunity_ripple",
        neutral_opportunity,
    )
    monkeypatch.setattr(
        projection_engine,
        "build_team_offensive_ripple",
        lambda df: pd.DataFrame([{"team": "AAA"}]),
    )
    monkeypatch.setattr(
        projection_engine,
        "add_fantasy_ripple_scores",
        lambda df: df.copy(),
    )

    def positive_team_ripple(df):
        result = df.copy()
        result["qb_ripple_multiplier"] = 1.0
        result["rb_ripple_multiplier"] = 1.0
        result["wr_ripple_multiplier"] = 1.04
        result["te_ripple_multiplier"] = 1.0
        return result

    monkeypatch.setattr(
        projection_engine,
        "add_projection_multipliers",
        positive_team_ripple,
    )
    monkeypatch.setattr(
        projection_engine,
        "calculate_vorp",
        lambda df, league_settings: df.copy(),
    )

    result = projection_engine.build_2026_projections("drunk_sundays")
    indexed = result.set_index("player_name_clean")

    assert bool(indexed.loc["Injured WR", "is_currently_injured"]) is True
    assert indexed.loc["Injured WR", "current_injury_status"] == "Out"
    assert indexed.loc["Injured WR", "current_injury_body_part"] == "Hamstring"
    assert indexed.loc["Injured WR", "injury_risk_score"] == 12.0
    assert indexed.loc["Injured WR", "durability_score"] == 88.0

    assert bool(indexed.loc["Healthy WR", "is_currently_injured"]) is False
    assert indexed.loc["Healthy WR", "current_injury_status"] == ""

    assert indexed.loc["Injured WR", "injury_ripple_multiplier"] == 1.0
    assert indexed.loc["Healthy WR", "injury_ripple_multiplier"] == 1.04
    assert indexed.loc["Injured WR", "projected_points"] == 100.0
    assert indexed.loc["Healthy WR", "projected_points"] == 104.0
