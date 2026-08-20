import pandas as pd

from fantasy_draft_model import draft_assistant
from fantasy_draft_model.ui import streamlit_app


def _base_board():
    return pd.DataFrame([
        {
            "player_name_clean": "Alpha WR",
            "position": "WR",
            "team": "CLE",
            "draft_rank": 1,
        }
    ])


def _state():
    return {
        "league_name": "Drunk Sundays",
        "league_key": "drunk_sundays",
        "user_team": "BLKWDW'S",
        "team_count": 12,
        "draft_rounds": 15,
        "current_pick": 2,
        "manual_picks": [],
        "keeper_reservations": [],
    }


def test_build_draft_assistant_from_rankings_uses_live_context(monkeypatch):
    base = _base_board()
    captured = {}

    monkeypatch.setattr(
        draft_assistant,
        "add_pressure_meter",
        lambda rankings: rankings.assign(pressure_score=50.0),
    )

    def fake_brain(rankings, draft_context):
        captured["draft_context"] = draft_context
        return rankings.assign(brain_score=77.0)

    monkeypatch.setattr(draft_assistant, "add_draft_brain", fake_brain)

    result = draft_assistant.build_draft_assistant_from_rankings(
        base,
        draft_context={"picks_until_user": 7},
    )

    assert captured["draft_context"] == {"picks_until_user": 7}
    assert result["brain_score"].tolist() == [77.0]
    assert "brain_score" not in base.columns


def test_get_or_build_base_rankings_reuses_cache(monkeypatch):
    cache = {}
    board = _base_board()
    calls = []

    def fake_build(league_key):
        calls.append(league_key)
        return board

    monkeypatch.setattr(streamlit_app, "build_draft_rankings", fake_build, raising=False)

    first = streamlit_app.get_or_build_base_rankings(cache, "drunk_sundays")
    second = streamlit_app.get_or_build_base_rankings(cache, "drunk_sundays")

    assert first is board
    assert second is board
    assert calls == ["drunk_sundays"]


def test_build_live_view_uses_supplied_base_rankings(monkeypatch):
    state = _state()
    base = _base_board()
    captured = {}

    monkeypatch.setattr(streamlit_app, "load_or_initialize_war_room_state", lambda: state)
    monkeypatch.setattr(
        streamlit_app,
        "build_live_draft_context",
        lambda supplied_state: {
            "current_pick": 2,
            "next_user_pick": 9,
            "picks_until_user": 7,
            "user_on_clock": False,
        },
    )

    def fake_live_assistant(rankings, draft_context=None):
        captured["rankings"] = rankings
        captured["draft_context"] = draft_context
        return rankings.assign(brain_score=80.0)

    monkeypatch.setattr(
        streamlit_app,
        "build_draft_assistant_from_rankings",
        fake_live_assistant,
        raising=False,
    )
    monkeypatch.setattr(
        streamlit_app,
        "build_war_room_snapshot",
        lambda rankings, supplied_state, search_text="", position=None: {
            "rankings": rankings,
            "state": supplied_state,
        },
    )

    snapshot = streamlit_app.build_live_view(base_rankings=base)

    assert captured["rankings"] is base
    assert captured["draft_context"]["picks_until_user"] == 7
    assert snapshot["state"] is state
