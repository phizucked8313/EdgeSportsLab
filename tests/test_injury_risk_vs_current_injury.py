import pandas as pd

from fantasy_draft_model.integrations import current_injury_normalizer
from fantasy_draft_model.engines import projection_engine


def _players():
    return pd.DataFrame([
        {
            "player_id": "00-healthy-high-risk",
            "player_name_clean": "Healthy High Risk",
            "team": "AAA",
            "position": "WR",
            "injury_risk_score": 72.0,
            "durability_score": 28.0,
        },
        {
            "player_id": "00-current-low-risk",
            "player_name_clean": "Current Low Risk",
            "team": "BBB",
            "position": "RB",
            "injury_risk_score": 12.0,
            "durability_score": 88.0,
        },
        {
            "player_id": "00-fallback",
            "player_name_clean": "Fallback Player",
            "team": "CCC",
            "position": "TE",
            "injury_risk_score": 20.0,
            "durability_score": 80.0,
        },
    ])


def _current_injuries():
    return pd.DataFrame([
        {
            "gsis_id": "00-current-low-risk",
            "player_name": "Current Low Risk",
            "team": "BBB",
            "position": "RB",
            "report_status": "Out",
            "edgeiq_injury_body_part": "Hamstring",
            "injury_data_quality": "D",
            "injury_source": "Sleeper",
        },
        {
            "gsis_id": None,
            "player_name": "fallback player",
            "team": "CCC",
            "position": "TE",
            "report_status": "Questionable",
            "edgeiq_injury_body_part": "Knee",
            "injury_data_quality": "D",
            "injury_source": "Sleeper",
        },
    ])


def test_current_injury_state_stays_separate_from_historical_risk():
    result = current_injury_normalizer.attach_current_injury_state(
        _players(),
        _current_injuries(),
    ).set_index("player_name_clean")

    healthy = result.loc["Healthy High Risk"]
    injured = result.loc["Current Low Risk"]

    assert healthy["injury_risk_score"] == 72.0
    assert healthy["durability_score"] == 28.0
    assert bool(healthy["is_currently_injured"]) is False
    assert healthy["current_injury_status"] == ""

    assert injured["injury_risk_score"] == 12.0
    assert injured["durability_score"] == 88.0
    assert bool(injured["is_currently_injured"]) is True
    assert injured["current_injury_status"] == "Out"
    assert injured["current_injury_body_part"] == "Hamstring"


def test_current_injury_state_matches_by_gsis_first_and_name_team_position_fallback():
    result = current_injury_normalizer.attach_current_injury_state(
        _players(),
        _current_injuries(),
    ).set_index("player_name_clean")

    gsis_match = result.loc["Current Low Risk"]
    fallback_match = result.loc["Fallback Player"]

    assert bool(gsis_match["is_currently_injured"]) is True
    assert gsis_match["current_injury_status"] == "Out"

    assert bool(fallback_match["is_currently_injured"]) is True
    assert fallback_match["current_injury_status"] == "Questionable"
    assert fallback_match["current_injury_body_part"] == "Knee"


def test_positive_team_ripple_is_neutralized_for_currently_injured_player():
    players = pd.DataFrame([
        {
            "player_name_clean": "Injured WR",
            "is_currently_injured": True,
            "injury_ripple_multiplier": 1.04,
        },
        {
            "player_name_clean": "Healthy WR",
            "is_currently_injured": False,
            "injury_ripple_multiplier": 1.04,
        },
    ])

    result = projection_engine.neutralize_positive_ripple_for_current_injuries(
        players
    ).set_index("player_name_clean")

    assert result.loc["Injured WR", "injury_ripple_multiplier"] == 1.0
    assert result.loc["Healthy WR", "injury_ripple_multiplier"] == 1.04


def test_negative_team_ripple_is_preserved_for_currently_injured_player():
    players = pd.DataFrame([
        {
            "player_name_clean": "Injured QB",
            "is_currently_injured": True,
            "injury_ripple_multiplier": 0.96,
        }
    ])

    result = projection_engine.neutralize_positive_ripple_for_current_injuries(
        players
    )

    assert result.loc[0, "injury_ripple_multiplier"] == 0.96
