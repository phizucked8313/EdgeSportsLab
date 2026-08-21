from pathlib import Path

import pandas as pd

from fantasy_draft_model.integrations import roster_loader
from fantasy_draft_model.integrations.roster_loader import add_rookie_identity
from fantasy_draft_model.models import projections


def test_rookie_identity_comes_from_rookie_year_not_missing_stats():
    df = pd.DataFrame([
        {
            "full_name": "True Rookie",
            "rookie_year": 2026,
            "years_exp": 0,
        },
        {
            "full_name": "Veteran",
            "rookie_year": 2024,
            "years_exp": 2,
        },
        {
            "full_name": "Odd Veteran",
            "rookie_year": 2025,
            "years_exp": 0,
        },
    ])

    result = add_rookie_identity(
        df,
        current_season=2026,
    ).set_index("full_name")

    assert bool(result.loc["True Rookie", "is_rookie"]) is True
    assert bool(result.loc["Veteran", "is_rookie"]) is False
    assert bool(result.loc["Odd Veteran", "is_rookie"]) is False


def test_current_roster_presence_is_preserved_after_outer_merge():
    historical = pd.DataFrame([
        {
            "player_id": "old",
            "player_name_clean": "Old Veteran",
            "team": "AAA",
            "position": "WR",
            "games_played": 10,
        },
    ])
    roster = pd.DataFrame([
        {
            "player_id": "rook",
            "roster_player_name": "True Rookie",
            "current_team": "BBB",
            "current_position": "RB",
            "status": "Active",
            "rookie_year": 2026,
            "is_rookie": True,
        },
    ])

    helper = getattr(projections, "merge_current_roster_identity", None)
    assert helper is not None, "merge_current_roster_identity helper is not implemented yet"

    result = helper(historical, roster).set_index("player_id")

    assert bool(result.loc["rook", "on_current_roster"]) is True
    assert bool(result.loc["old", "on_current_roster"]) is False


def test_released_player_preserves_unsigned_provenance_without_stale_team():
    historical = pd.DataFrame([{
        "player_id": "juju",
        "player_name_clean": "JuJu Smith-Schuster",
        "team": "KC",
        "position": "WR",
        "games_played": 17,
    }])
    roster = pd.DataFrame([{
        "player_id": "juju",
        "roster_player_name": "JuJu Smith-Schuster",
        "current_team": "NYG",
        "current_position": "WR",
        "status": "Released",
        "rookie_year": 2017,
        "is_rookie": False,
    }])

    merged = projections.merge_current_roster_identity(historical, roster)
    result = projections.add_fantasy_draftable_flag(merged).iloc[0]

    assert pd.isna(result["team"])
    assert result["prior_roster_team"] == "NYG"
    assert result["roster_status_provenance"] == "Released"
    assert bool(result["is_unsigned_free_agent"]) is True
    assert bool(result["on_current_roster"]) is False
    assert bool(result["is_fantasy_draftable"]) is False


def test_verified_release_override_wins_over_stale_active_roster_feed():
    roster = pd.DataFrame([{
        "gsis_id": "00-0033857",
        "player_name_clean": "JuJu Smith-Schuster",
        "team": "NYG",
        "position": "WR",
        "status": "ACT",
    }])
    overrides = pd.DataFrame([{
        "gsis_id": "00-0033857",
        "player_name": "JuJu Smith-Schuster",
        "prior_team": "NYG",
        "status": "Released",
        "source_url": "https://example.com/juju-release",
        "source_date": "2026-08-18",
        "retrieved_at": "2026-08-21T12:00:00+00:00",
    }])

    helper = getattr(roster_loader, "apply_current_roster_overrides", None)
    assert helper is not None, "apply_current_roster_overrides is not implemented"
    result = helper(roster, overrides).iloc[0]

    assert pd.isna(result["team"])
    assert result["status"] == "Released"
    assert result["prior_roster_team"] == "NYG"
    assert result["roster_status_source"] == "https://example.com/juju-release"
    assert result["roster_status_source_date"] == "2026-08-18"
    assert result["roster_status_retrieved_at"] == "2026-08-21T12:00:00+00:00"
    assert bool(result["is_unsigned_free_agent"]) is True


def test_draftability_is_separate_from_rookie_identity():
    df = pd.DataFrame([
        {
            "player_name_clean": "Drafted Rookie",
            "position": "RB",
            "team": "AAA",
            "on_current_roster": True,
            "is_rookie": True,
            "draft_number": 45,
            "games_played": 0,
            "status": "Active",
        },
        {
            "player_name_clean": "Active UDFA",
            "position": "WR",
            "team": "BBB",
            "on_current_roster": True,
            "is_rookie": True,
            "draft_number": 0,
            "games_played": 0,
            "status": "ACT",
        },
        {
            "player_name_clean": "Fringe Rookie",
            "position": "WR",
            "team": "BBB",
            "on_current_roster": True,
            "is_rookie": True,
            "draft_number": 0,
            "games_played": 0,
            "status": "Inactive",
        },
        {
            "player_name_clean": "Veteran Producer",
            "position": "WR",
            "team": "CCC",
            "on_current_roster": True,
            "is_rookie": False,
            "draft_number": 0,
            "games_played": 12,
            "status": "Active",
        },
        {
            "player_name_clean": "Historical Only",
            "position": "WR",
            "team": "DDD",
            "on_current_roster": False,
            "is_rookie": False,
            "draft_number": 0,
            "games_played": 10,
            "status": None,
        },
        {
            "player_name_clean": "PUP Star",
            "position": "RB",
            "team": "EEE",
            "on_current_roster": True,
            "is_rookie": False,
            "draft_number": 0,
            "games_played": 15,
            "status": "PUP",
        },
    ])

    helper = getattr(projections, "add_fantasy_draftable_flag", None)
    assert helper is not None, "add_fantasy_draftable_flag helper is not implemented yet"

    result = helper(df).set_index("player_name_clean")

    assert bool(result.loc["Drafted Rookie", "is_fantasy_draftable"]) is True
    assert bool(result.loc["Active UDFA", "is_fantasy_draftable"]) is False
    assert bool(result.loc["Fringe Rookie", "is_fantasy_draftable"]) is False
    assert bool(result.loc["Veteran Producer", "is_fantasy_draftable"]) is True
    assert bool(result.loc["Historical Only", "is_fantasy_draftable"]) is False
    assert bool(result.loc["PUP Star", "is_fantasy_draftable"]) is True
    assert bool(result.loc["Active UDFA", "is_rookie"]) is True
    assert bool(result.loc["Fringe Rookie", "is_rookie"]) is True


def test_live_projection_engine_filters_to_fantasy_draftable_pool():
    source = Path(
        "fantasy_draft_model/engines/projection_engine.py"
    ).read_text(encoding="utf-8")

    assert "is_fantasy_draftable" in source
