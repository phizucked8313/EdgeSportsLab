import pandas as pd

from fantasy_draft_model.ui import streamlit_app


def _state():
    return {
        "league_name": "Drunk Sundays",
        "league_key": "drunk_sundays",
        "user_team": "BLKWDW'S",
        "team_count": 12,
        "draft_rounds": 15,
        "current_pick": 10,
        "manual_picks": [],
        "keeper_reservations": [],
    }


def test_build_live_view_uses_state_context_and_assistant_board(monkeypatch):
    state = _state()
    board = pd.DataFrame(
        [
            {
                "player_name_clean": "Beta RB",
                "position": "RB",
                "team": "DET",
                "draft_rank": 2,
            }
        ]
    )
    calls = {}

    monkeypatch.setattr(
        streamlit_app,
        "load_war_room_state",
        lambda: state,
        raising=False,
    )

    def fake_build_draft_assistant(league_key, draft_context=None):
        calls["league_key"] = league_key
        calls["draft_context"] = draft_context
        return board

    monkeypatch.setattr(
        streamlit_app,
        "build_draft_assistant",
        fake_build_draft_assistant,
        raising=False,
    )
    monkeypatch.setattr(
        streamlit_app,
        "build_live_draft_context",
        lambda supplied_state: {
            "current_pick": 10,
            "next_user_pick": 16,
            "picks_until_user": 6,
            "user_on_clock": False,
        },
        raising=False,
    )
    monkeypatch.setattr(
        streamlit_app,
        "build_war_room_snapshot",
        lambda rankings, supplied_state, search_text="", position=None: {
            "rankings": rankings,
            "state": supplied_state,
            "search_text": search_text,
            "position": position,
        },
        raising=False,
    )

    snapshot = streamlit_app.build_live_view()

    assert calls["league_key"] == "drunk_sundays"
    assert calls["draft_context"]["picks_until_user"] == 6
    assert snapshot["rankings"] is board
    assert snapshot["state"] is state


def test_build_live_view_forwards_ui_filters(monkeypatch):
    state = _state()
    board = pd.DataFrame(
        [
            {
                "player_name_clean": "Beta RB",
                "position": "RB",
                "team": "DET",
                "draft_rank": 2,
            }
        ]
    )

    monkeypatch.setattr(
        streamlit_app,
        "load_war_room_state",
        lambda: state,
        raising=False,
    )
    monkeypatch.setattr(
        streamlit_app,
        "build_draft_assistant",
        lambda league_key, draft_context=None: board,
        raising=False,
    )
    monkeypatch.setattr(
        streamlit_app,
        "build_live_draft_context",
        lambda supplied_state: {
            "picks_until_user": 6,
        },
        raising=False,
    )

    captured = {}

    def fake_snapshot(rankings, supplied_state, search_text="", position=None):
        captured["search_text"] = search_text
        captured["position"] = position
        return {"ok": True}

    monkeypatch.setattr(
        streamlit_app,
        "build_war_room_snapshot",
        fake_snapshot,
        raising=False,
    )

    result = streamlit_app.build_live_view(
        search_text="beta",
        position="RB",
    )

    assert result == {"ok": True}
    assert captured == {
        "search_text": "beta",
        "position": "RB",
    }
