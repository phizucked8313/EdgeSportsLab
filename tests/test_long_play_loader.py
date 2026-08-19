import pandas as pd

from fantasy_draft_model.integrations import long_play_loader
from fantasy_draft_model.integrations.long_play_loader import (
    aggregate_long_play_counts,
    load_2025_long_play_counts,
)
from fantasy_draft_model.models import projections


def test_40_plus_play_counts_are_attributed_by_player_id():
    pbp = pd.DataFrame(
        {
            "yards_gained": [39, 40, 45, 50],
            "complete_pass": [1, 1, 0, 0],
            "pass_touchdown": [0, 1, 0, 0],
            "rush_touchdown": [0, 0, 1, 0],
            "passer_player_id": ["QB1", "QB1", None, None],
            "receiver_player_id": ["WR1", "WR1", None, None],
            "rusher_player_id": [None, None, "RB1", "RB2"],
        }
    )

    result = aggregate_long_play_counts(pbp).set_index("player_id")

    assert result.loc["QB1", "plays_40_pass_completion"] == 1
    assert result.loc["QB1", "plays_40_pass_td"] == 1
    assert result.loc["WR1", "plays_40_reception"] == 1
    assert result.loc["WR1", "plays_40_reception_td"] == 1
    assert result.loc["RB1", "plays_40_rush"] == 1
    assert result.loc["RB1", "plays_40_rush_td"] == 1
    assert result.loc["RB2", "plays_40_rush"] == 1
    assert result.loc["RB2", "plays_40_rush_td"] == 0


def test_load_2025_long_play_counts_uses_regular_season_only(monkeypatch):
    calls = []

    pbp = pd.DataFrame(
        {
            "season_type": ["REG", "POST"],
            "yards_gained": [40, 60],
            "complete_pass": [1, 1],
            "pass_touchdown": [1, 1],
            "rush_touchdown": [0, 0],
            "passer_player_id": ["QB_REG", "QB_POST"],
            "receiver_player_id": ["WR_REG", "WR_POST"],
            "rusher_player_id": [None, None],
        }
    )

    class FakeFrame:
        def to_pandas(self):
            return pbp.copy()

    def fake_load_pbp(*, seasons):
        calls.append(seasons)
        return FakeFrame()

    monkeypatch.setattr(long_play_loader.nfl, "load_pbp", fake_load_pbp)

    result = load_2025_long_play_counts().set_index("player_id")

    assert calls == [[2025]]
    assert "QB_REG" in result.index
    assert "WR_REG" in result.index
    assert "QB_POST" not in result.index
    assert "WR_POST" not in result.index


def test_master_player_table_merges_long_play_counts_by_player_id(monkeypatch):
    weekly = pd.DataFrame(
        {
            "player_id": ["P1", "P2"],
            "player_name_clean": ["Player One", "Player Two"],
            "position": ["WR", "WR"],
            "team": ["AAA", "BBB"],
            "week": [1, 1],
            "completions": [0, 0],
            "attempts": [0, 0],
            "passing_yards": [0, 0],
            "passing_tds": [0, 0],
            "passing_interceptions": [0, 0],
            "carries": [0, 0],
            "rushing_yards": [0, 0],
            "rushing_tds": [0, 0],
            "receptions": [4, 3],
            "targets": [5, 4],
            "receiving_yards": [80, 30],
            "receiving_tds": [1, 0],
            "receiving_air_yards": [100, 50],
            "target_share": [0.20, 0.15],
            "air_yards_share": [0.25, 0.10],
            "wopr": [0.40, 0.25],
            "fantasy_points_ppr": [18.0, 6.0],
        }
    )

    long_plays = pd.DataFrame(
        {
            "player_id": ["P1"],
            "plays_40_pass_completion": [0],
            "plays_40_pass_td": [0],
            "plays_40_rush": [0],
            "plays_40_rush_td": [0],
            "plays_40_reception": [2],
            "plays_40_reception_td": [1],
        }
    )

    monkeypatch.setattr(projections, "prepare_weekly_data", lambda: weekly.copy())
    monkeypatch.setattr(
        projections,
        "load_2025_long_play_counts",
        lambda: long_plays.copy(),
        raising=False,
    )

    result = projections.build_master_player_table().set_index("player_id")

    assert result.loc["P1", "plays_40_reception"] == 2
    assert result.loc["P1", "plays_40_reception_td"] == 1
    assert result.loc["P2", "plays_40_reception"] == 0
    assert result.loc["P2", "plays_40_reception_td"] == 0
