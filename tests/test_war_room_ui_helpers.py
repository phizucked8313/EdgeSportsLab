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


def _drunk_sundays_state(current_pick):
    return {
        "league_name": "Drunk Sundays",
        "league_key": "drunk_sundays",
        "user_team": "BLKWDW'S",
        "team_count": 12,
        "draft_rounds": 15,
        "current_pick": current_pick,
    }


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


def test_build_live_draft_context_counts_picks_until_user():
    context = draft_war_room.build_live_draft_context(
        _drunk_sundays_state(current_pick=1)
    )

    assert context["next_user_pick"] == 9
    assert context["picks_until_user"] == 8
    assert context["user_on_clock"] is False


def test_build_live_draft_context_detects_user_on_clock():
    context = draft_war_room.build_live_draft_context(
        _drunk_sundays_state(current_pick=9)
    )

    assert context["next_user_pick"] == 9
    assert context["picks_until_user"] == 0
    assert context["user_on_clock"] is True


def test_build_live_draft_context_finds_next_snake_turn_after_user_pick():
    context = draft_war_room.build_live_draft_context(
        _drunk_sundays_state(current_pick=10)
    )

    assert context["next_user_pick"] == 16
    assert context["picks_until_user"] == 6
    assert context["user_on_clock"] is False


def test_build_user_roster_includes_user_manual_picks_and_keepers():
    state = _drunk_sundays_state(current_pick=20)
    state["manual_picks"] = [
        {
            "pick_number": 9,
            "round": 1,
            "fantasy_team": "BLKWDW'S",
            "player_name": "User WR",
            "position": "WR",
            "nfl_team": "CLE",
        },
        {
            "pick_number": 10,
            "round": 1,
            "fantasy_team": "Door Dash At 2AM",
            "player_name": "Other RB",
            "position": "RB",
            "nfl_team": "DET",
        },
    ]
    state["keeper_reservations"] = [
        {
            "pick_number": 33,
            "round": 3,
            "fantasy_team": "BLKWDW'S",
            "player_name": "User Keeper",
            "position": "RB",
            "nfl_team": "LV",
        }
    ]

    roster = draft_war_room.build_user_roster(state)

    assert roster["player_name"].tolist() == ["User WR", "User Keeper"]
    assert roster["source"].tolist() == ["draft", "keeper"]


def test_build_user_roster_returns_expected_display_columns_when_empty():
    state = _drunk_sundays_state(current_pick=1)
    state["manual_picks"] = []
    state["keeper_reservations"] = []

    roster = draft_war_room.build_user_roster(state)

    assert roster.empty
    assert roster.columns.tolist() == [
        "player_name",
        "position",
        "nfl_team",
        "round",
        "pick_number",
        "source",
    ]


def test_build_war_room_snapshot_composes_read_only_ui_data():
    state = _drunk_sundays_state(current_pick=10)
    state["manual_picks"] = [
        {
            "pick_number": 9,
            "round": 1,
            "fantasy_team": "BLKWDW'S",
            "player_name": "Alpha WR",
            "position": "WR",
            "nfl_team": "CLE",
        }
    ]
    state["keeper_reservations"] = [
        {
            "pick_number": 33,
            "round": 3,
            "fantasy_team": "BLKWDW'S",
            "player_name": "Keeper TE",
            "position": "TE",
            "nfl_team": "KC",
        }
    ]

    snapshot = draft_war_room.build_war_room_snapshot(
        _rankings(),
        state,
        search_text="beta",
        position="RB",
    )

    assert snapshot["context"]["next_user_pick"] == 16
    assert snapshot["available"]["player_name_clean"].tolist() == ["Beta RB"]
    assert snapshot["filtered_available"]["player_name_clean"].tolist() == ["Beta RB"]
    assert snapshot["roster"]["player_name"].tolist() == ["Alpha WR", "Keeper TE"]
    assert snapshot["recent_history"]["player_name"].tolist() == ["Alpha WR"]


def test_build_war_room_snapshot_does_not_mutate_rankings():
    rankings = _rankings()
    original = rankings.copy(deep=True)
    state = _drunk_sundays_state(current_pick=1)
    state["manual_picks"] = []
    state["keeper_reservations"] = []

    draft_war_room.build_war_room_snapshot(rankings, state)

    pd.testing.assert_frame_equal(rankings, original)
