import pandas as pd

from fantasy_draft_model.integrations.long_play_loader import (
    aggregate_long_play_counts,
)


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
