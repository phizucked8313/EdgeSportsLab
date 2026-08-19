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


def test_apply_player_filters_combines_search_and_position():
    filtered = draft_war_room.apply_player_filters(
        _rankings(),
        search_text="beta",
        position="RB",
    )

    assert filtered["player_name_clean"].tolist() == ["Beta RB"]


def test_select_display_columns_ignores_missing_optional_columns():
    columns = draft_war_room.select_display_columns(
        _rankings(),
        ["player_name_clean", "position", "tier", "vorp", "draft_rank"],
    )

    assert columns == ["player_name_clean", "position", "draft_rank"]


def test_build_recent_history_returns_newest_manual_picks_first():
    state = {
        "manual_picks": [
            {
                "pick_number": 1,
                "round": 1,
                "fantasy_team": "A",
                "player_name": "One",
                "position": "WR",
            },
            {
                "pick_number": 2,
                "round": 1,
                "fantasy_team": "B",
                "player_name": "Two",
                "position": "RB",
            },
        ]
    }

    history = draft_war_room.build_recent_history(state, limit=10)

    assert history["pick_number"].tolist() == [2, 1]
