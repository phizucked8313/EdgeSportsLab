import pandas as pd

from fantasy_draft_model.ui import draft_war_room


def _rankings():
    return pd.DataFrame(
        [
            {
                "player_name_clean": "Alpha WR",
                "position": "WR",
                "team": "CLE",
                "draft_rank": 1,
            },
            {
                "player_name_clean": "Beta RB",
                "position": "RB",
                "team": "DET",
                "draft_rank": 2,
            },
            {
                "player_name_clean": "Keeper TE",
                "position": "TE",
                "team": "KC",
                "draft_rank": 3,
            },
        ]
    )


def test_filter_available_players_removes_manual_picks_and_keepers():
    state = {
        "manual_picks": [{"player_name": " alpha wr "}],
        "keeper_reservations": [{"player_name": "KEEPER TE"}],
    }

    available = draft_war_room.filter_available_players(_rankings(), state)

    assert available["player_name_clean"].tolist() == ["Beta RB"]
