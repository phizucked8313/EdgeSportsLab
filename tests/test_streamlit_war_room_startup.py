import pandas as pd

from fantasy_draft_model.ui import streamlit_app


def _state():
    return {
        "league_name": "Drunk Sundays",
        "league_key": "drunk_sundays",
        "user_team": "BLKWDW'S",
        "team_count": 12,
        "draft_rounds": 15,
        "current_pick": 1,
        "manual_picks": [],
        "keeper_reservations": [],
        "processed_keeper_picks": [],
    }


def test_load_or_initialize_war_room_state_preserves_existing_state(monkeypatch):
    state = _state()
    calls = {"initialize": 0}

    monkeypatch.setattr(streamlit_app, "load_war_room_state", lambda: state)

    def fake_initialize(league_key):
        calls["initialize"] += 1
        return _state()

    monkeypatch.setattr(
        streamlit_app,
        "initialize_war_room",
        fake_initialize,
        raising=False,
    )

    result = streamlit_app.load_or_initialize_war_room_state()

    assert result is state
    assert calls["initialize"] == 0


def test_load_or_initialize_war_room_state_never_initializes_when_missing(
    monkeypatch,
):
    initialized = _state()
    calls = []

    def missing_state():
        raise FileNotFoundError("live War Room state is missing")

    def fake_initialize(league_key):
        calls.append(league_key)
        return initialized

    monkeypatch.setattr(streamlit_app, "load_war_room_state", missing_state)
    monkeypatch.setattr(
        streamlit_app,
        "initialize_war_room",
        fake_initialize,
        raising=False,
    )

    import pytest

    with pytest.raises(FileNotFoundError, match="missing"):
        streamlit_app.load_or_initialize_war_room_state()

    assert calls == []


def test_build_live_view_uses_startup_state_loader(monkeypatch, tmp_path):
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
        "load_or_initialize_war_room_state",
        lambda: state,
        raising=False,
    )

    def raw_load_must_not_run():
        raise AssertionError("build_live_view bypassed startup state loader")

    monkeypatch.setattr(streamlit_app, "load_war_room_state", raw_load_must_not_run)
    monkeypatch.setattr(
        streamlit_app,
        "build_live_draft_context",
        lambda supplied_state: {"picks_until_user": 8},
    )
    monkeypatch.setattr(
        streamlit_app,
        "build_draft_rankings",
        lambda league_key: board,
    )
    monkeypatch.setattr(
        streamlit_app,
        "build_draft_assistant_from_rankings",
        lambda rankings, draft_context=None: rankings,
    )
    monkeypatch.setattr(
        streamlit_app,
        "build_war_room_snapshot",
        lambda rankings, supplied_state, search_text="", position=None: {
            "rankings": rankings,
            "state": supplied_state,
        },
    )

    snapshot = streamlit_app.build_live_view(
        paths={
            "data_path": tmp_path / "rankings.csv",
            "metadata_path": tmp_path / "rankings.json",
        },
    )

    assert snapshot["rankings"] is board
    assert snapshot["state"] is state
