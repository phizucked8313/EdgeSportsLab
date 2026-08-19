import pandas as pd

from fantasy_draft_model.engines import projection_engine


def test_build_projections_applies_player_opportunity_ripple(monkeypatch):
    players = pd.DataFrame([
        {
            "player_name_clean": "Injured WR",
            "team": "AAA",
            "position": "WR",
            "is_fantasy_draftable": True,
            "injury_risk_score": 0.0,
        },
        {
            "player_name_clean": "Healthy WR",
            "team": "AAA",
            "position": "WR",
            "is_fantasy_draftable": True,
            "injury_risk_score": 0.0,
        },
    ])

    injuries = pd.DataFrame([
        {
            "player_name": "Injured WR",
            "team": "AAA",
            "position": "WR",
            "report_status": "Out",
            "practice_status": "",
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

    identity_names = [
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
    ]
    for name in identity_names:
        monkeypatch.setattr(
            projection_engine,
            name,
            lambda df: df.copy(),
        )

    def add_injury_scores(df):
        result = df.copy()
        result["injury_risk_score"] = 0.0
        return result

    def calculate_projection(df):
        result = df.copy()
        result["projected_points"] = 100.0
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
        "build_team_offensive_ripple",
        lambda df: pd.DataFrame([{"team": "AAA"}]),
    )
    monkeypatch.setattr(
        projection_engine,
        "add_fantasy_ripple_scores",
        lambda df: df.copy(),
    )

    def neutral_team_multipliers(df):
        result = df.copy()
        for position in ("qb", "rb", "wr", "te"):
            result[f"{position}_ripple_multiplier"] = 1.0
        return result

    monkeypatch.setattr(
        projection_engine,
        "add_projection_multipliers",
        neutral_team_multipliers,
    )
    monkeypatch.setattr(
        projection_engine,
        "calculate_vorp",
        lambda df, league_settings: df.copy(),
    )

    result = projection_engine.build_2026_projections("drunk_sundays")
    indexed = result.set_index("player_name_clean")

    assert "injury_opportunity_multiplier" in result.columns
    assert indexed.loc[
        "Injured WR", "injury_opportunity_multiplier"
    ] == 1.0
    assert indexed.loc[
        "Healthy WR", "injury_opportunity_multiplier"
    ] == 1.05
    assert indexed.loc["Injured WR", "projected_points"] == 100.0
    assert indexed.loc["Healthy WR", "projected_points"] == 105.0
