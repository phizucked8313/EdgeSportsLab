import pandas as pd

from fantasy_draft_model.integrations.current_injury_normalizer import (
    normalize_current_injuries,
)


def sample_players():
    return pd.DataFrame([
        {
            "sleeper_id": "1",
            "espn_id": 101,
            "yahoo_id": 201,
            "player_name": "IR Player",
            "team": "AAA",
            "position": "RB",
            "status": "Inactive",
            "injury_status": "IR",
            "injury_body_part": "Knee - ACL",
            "injury_start_date": "2026-08-01",
            "practice_participation": None,
        },
        {
            "sleeper_id": "2",
            "espn_id": 102,
            "yahoo_id": 202,
            "player_name": "Questionable Player",
            "team": "BBB",
            "position": "WR",
            "status": "Active",
            "injury_status": "Questionable",
            "injury_body_part": "Hamstring",
            "injury_start_date": None,
            "practice_participation": "Limited Participation in Practice",
        },
        {
            "sleeper_id": "3",
            "espn_id": 103,
            "yahoo_id": 203,
            "player_name": "Mystery Player",
            "team": "CCC",
            "position": "WR",
            "status": "Active",
            "injury_status": "Questionable",
            "injury_body_part": "Undisclosed",
            "injury_start_date": None,
            "practice_participation": None,
        },
        {
            "sleeper_id": "4",
            "espn_id": 104,
            "yahoo_id": 204,
            "player_name": "Healthy Player",
            "team": "DDD",
            "position": "TE",
            "status": "Active",
            "injury_status": None,
            "injury_body_part": None,
            "injury_start_date": None,
            "practice_participation": None,
        },
    ])


def test_normalizer_maps_current_statuses_and_filters_healthy_players():
    result = normalize_current_injuries(sample_players())

    assert set(result["player_name"]) == {
        "IR Player",
        "Questionable Player",
        "Mystery Player",
    }
    assert result.set_index("player_name").loc["IR Player", "report_status"] == "IR"
    assert result.set_index("player_name").loc["Questionable Player", "report_status"] == "Questionable"


def test_undisclosed_is_flagged_for_research():
    result = normalize_current_injuries(sample_players()).set_index("player_name")

    assert bool(result.loc["Mystery Player", "needs_research"]) is True
    assert result.loc["Mystery Player", "injury_data_quality"] == "F"
    assert result.loc["Mystery Player", "source_injury_body_part"] == "Undisclosed"


def test_specific_sleeper_injury_starts_at_quality_d():
    result = normalize_current_injuries(sample_players()).set_index("player_name")

    assert bool(result.loc["IR Player", "needs_research"]) is False
    assert result.loc["IR Player", "injury_data_quality"] == "D"
    assert result.loc["IR Player", "edgeiq_injury_body_part"] == "Knee - ACL"


def test_missing_source_timestamp_does_not_pretend_injury_is_fresh():
    result = normalize_current_injuries(sample_players()).set_index("player_name")
    row = result.loc["Questionable Player"]

    assert row["injury_source_timestamp"] == ""
    assert pd.isna(row["injury_age_hours"])
    assert bool(row["injury_freshness_known"]) is False
    assert bool(row["injury_is_stale"]) is False
