import pandas as pd

from fantasy_draft_model.engines import injury_ripple_engine
from fantasy_draft_model.integrations.current_injury_normalizer import (
    normalize_current_injuries,
)
from fantasy_draft_model.models import team_injury_impact_engine
from fantasy_draft_model.models.team_injury_impact_engine import (
    calculate_player_injury_impact,
)


def test_normalizer_preserves_gsis_id_when_source_provides_it():
    sleeper_rows = pd.DataFrame([
        {
            "sleeper_id": "10",
            "gsis_id": "00-0039999",
            "player_name": "Injured Receiver",
            "team": "AAA",
            "position": "WR",
            "status": "Active",
            "injury_status": "Out",
            "injury_body_part": "Hamstring",
            "practice_participation": "Did Not Participate in Practice",
            "injury_start_date": "2026-08-18",
        }
    ])

    normalized = normalize_current_injuries(sleeper_rows)

    assert "gsis_id" in normalized.columns
    assert normalized.loc[0, "gsis_id"] == "00-0039999"


def test_role_matching_falls_back_to_team_name_position_when_gsis_missing(monkeypatch):
    injuries = pd.DataFrame([
        {
            "player_name": "starting receiver",
            "team": "AAA",
            "position": "WR",
            "report_status": "Out",
            "practice_status": "",
        }
    ])

    depth = pd.DataFrame([
        {
            "player_name": "Starting Receiver",
            "team": "AAA",
            "pos_abb": "WR",
            "gsis_id": "00-0031111",
            "edgeiq_role": "STARTER",
        }
    ])

    monkeypatch.setattr(
        team_injury_impact_engine,
        "load_depth_charts",
        lambda: depth.copy(),
    )

    result = team_injury_impact_engine.add_team_injury_impact(injuries)

    assert result.loc[0, "edgeiq_role"] == "STARTER"


def test_starter_injury_outweighs_backup_injury_same_status():
    starter = calculate_player_injury_impact(
        position="WR",
        report_status="Out",
        role="STARTER",
    )
    backup = calculate_player_injury_impact(
        position="WR",
        report_status="Out",
        role="BACKUP",
    )

    assert starter > backup
    assert starter >= backup * 2


def _player_pool():
    return pd.DataFrame([
        {
            "player_name_clean": "Injured WR",
            "team": "AAA",
            "position": "WR",
        },
        {
            "player_name_clean": "Healthy WR",
            "team": "AAA",
            "position": "WR",
        },
        {
            "player_name_clean": "Healthy TE",
            "team": "AAA",
            "position": "TE",
        },
        {
            "player_name_clean": "Healthy RB",
            "team": "AAA",
            "position": "RB",
        },
    ])


def _injured_wr():
    return pd.DataFrame([
        {
            "player_name": "Injured WR",
            "team": "AAA",
            "position": "WR",
            "report_status": "Out",
            "edgeiq_role": "STARTER",
            "player_injury_impact": 5.0,
        }
    ])


def test_healthy_teammate_gets_opportunity_boost_from_starting_wr_absence():
    result = injury_ripple_engine.add_player_opportunity_ripple(
        _player_pool(),
        _injured_wr(),
    )

    multipliers = result.set_index("player_name_clean")[
        "injury_opportunity_multiplier"
    ]

    assert multipliers["Healthy WR"] > 1.0
    assert multipliers["Healthy RB"] == 1.0


def test_injured_player_does_not_receive_own_opportunity_boost():
    result = injury_ripple_engine.add_player_opportunity_ripple(
        _player_pool(),
        _injured_wr(),
    )

    multipliers = result.set_index("player_name_clean")[
        "injury_opportunity_multiplier"
    ]

    assert multipliers["Injured WR"] == 1.0
    assert multipliers["Healthy WR"] > multipliers["Injured WR"]


def test_projection_ripple_multiplier_remains_conservatively_capped():
    assert injury_ripple_engine.ripple_to_projection_multiplier(1000) == 1.08
    assert injury_ripple_engine.ripple_to_projection_multiplier(-1000) == 0.92
