import pandas as pd

from fantasy_draft_model.integrations.current_injury_overrides import (
    attach_current_injury_overrides,
)


def test_verified_override_attaches_timeline_and_marks_missing_feed_injury_current():
    players = pd.DataFrame([
        {
            "player_name_clean": "Example Runner",
            "team": "AAA",
            "position": "RB",
            "is_currently_injured": False,
        }
    ])
    overrides = pd.DataFrame([
        {
            "player_name": "Example Runner",
            "team": "AAA",
            "position": "RB",
            "injury_body_part": "Groin",
            "expected_games_missed": 3,
            "expected_return": "Week 4 target",
            "season_ending": False,
            "source_url": "https://example.com/report",
            "source_date": "2026-08-20",
        }
    ])

    result = attach_current_injury_overrides(players, overrides).iloc[0]

    assert bool(result["is_currently_injured"]) is True
    assert result["current_injury_body_part"] == "Groin"
    assert result["current_injury_expected_games_missed"] == 3
    assert result["current_injury_expected_return"] == "Week 4 target"
    assert bool(result["current_injury_season_ending"]) is False
    assert result["current_injury_timeline_source"] == "https://example.com/report"
    assert result["current_injury_timeline_source_date"] == "2026-08-20"
    assert bool(result["current_injury_research_override"]) is True


def test_unmatched_player_stays_neutral():
    players = pd.DataFrame([
        {
            "player_name_clean": "Healthy Receiver",
            "team": "BBB",
            "position": "WR",
            "is_currently_injured": False,
        }
    ])
    overrides = pd.DataFrame([
        {
            "player_name": "Other Player",
            "team": "CCC",
            "position": "WR",
            "expected_games_missed": 4,
            "season_ending": False,
        }
    ])

    result = attach_current_injury_overrides(players, overrides).iloc[0]

    assert bool(result["is_currently_injured"]) is False
    assert pd.isna(result["current_injury_expected_games_missed"])
    assert result["current_injury_expected_return"] == ""
    assert bool(result["current_injury_season_ending"]) is False


def test_blank_optional_source_date_remains_blank_in_provenance():
    players = pd.DataFrame([{
        "player_name_clean": "Season Ending Receiver",
        "team": "AAA",
        "position": "WR",
        "is_currently_injured": True,
    }])
    overrides = pd.DataFrame([{
        "player_name": "Season Ending Receiver",
        "team": "AAA",
        "position": "WR",
        "season_ending": True,
        "expected_return": "Out for 2026 season",
        "source_url": "https://example.com/season-ending",
        "source_date": float("nan"),
    }])

    result = attach_current_injury_overrides(players, overrides).iloc[0]

    assert result["current_injury_timeline_source_date"] == ""
