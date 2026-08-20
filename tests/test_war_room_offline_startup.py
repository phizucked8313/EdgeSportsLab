import pandas as pd
import pytest

from fantasy_draft_model.config import DATA_DIR
from fantasy_draft_model.rankings_snapshot import RankingDataStatus
from fantasy_draft_model.ui import streamlit_app


def _board():
    return pd.DataFrame(
        [{"player_name_clean": "Alpha WR", "position": "WR", "team": "CLE", "draft_rank": 1}]
    )


def _paths(tmp_path):
    return {
        "data_path": tmp_path / "rankings.csv",
        "metadata_path": tmp_path / "rankings.json",
    }


def _production_snapshot_artifacts():
    return {
        path.name: path.read_bytes()
        for path in sorted(DATA_DIR.glob("war_room_rankings*"))
        if path.is_file()
    }


def test_ui_cache_loads_rankings_once_and_never_refreshes_per_pick(monkeypatch, tmp_path):
    cache = {}
    paths = _paths(tmp_path)
    calls = []

    def builder(league_key):
        calls.append(league_key)
        return _board()

    first = streamlit_app.get_or_build_base_rankings(
        cache,
        "drunk_sundays",
        paths=paths,
        builder=builder,
        timeout_seconds=1,
    )
    second = streamlit_app.get_or_build_base_rankings(
        cache,
        "drunk_sundays",
        paths=paths,
        builder=builder,
        timeout_seconds=1,
    )

    assert first is second
    assert calls == ["drunk_sundays"]


def test_get_or_build_base_rankings_uses_supplied_bounded_snapshot_path(monkeypatch, tmp_path):
    cache = {}
    board = _board()
    captured = {}
    paths = _paths(tmp_path)

    monkeypatch.setattr(
        streamlit_app,
        "build_draft_rankings",
        lambda _league_key: (_ for _ in ()).throw(AssertionError("direct build is unbounded")),
    )

    def fake_fallback(league_key, *, builder, paths, timeout_seconds):
        captured.update(
            league_key=league_key,
            builder=builder,
            paths=paths,
            timeout_seconds=timeout_seconds,
        )
        return board, RankingDataStatus("LIVE", "2026-08-20T00:00:00+00:00", 0.0)

    monkeypatch.setattr(streamlit_app, "load_rankings_with_fallback", fake_fallback)

    assert streamlit_app.get_or_build_base_rankings(
        cache,
        "drunk_sundays",
        paths=paths,
    ) is board
    assert captured["league_key"] == "drunk_sundays"
    assert captured["paths"] is paths


def test_get_or_build_base_rankings_requires_explicit_snapshot_paths(monkeypatch):
    cache = {}
    monkeypatch.setattr(
        streamlit_app,
        "load_rankings_with_fallback",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("fallback must not receive implicit production paths")
        ),
    )

    with pytest.raises(ValueError, match="explicit snapshot paths"):
        streamlit_app.get_or_build_base_rankings(cache, "drunk_sundays")


def test_build_live_view_uses_bounded_fallback_when_base_board_is_not_supplied(monkeypatch, tmp_path):
    board = _board()
    state = {
        "league_name": "Drunk Sundays",
        "league_key": "drunk_sundays",
        "user_team": "BLKWDW'S",
        "team_count": 12,
        "draft_rounds": 15,
        "current_pick": 1,
        "manual_picks": [],
        "keeper_reservations": [],
    }
    captured = {}
    paths = _paths(tmp_path)
    monkeypatch.setattr(streamlit_app, "load_or_initialize_war_room_state", lambda: state)
    monkeypatch.setattr(streamlit_app, "build_live_draft_context", lambda _state: {})
    monkeypatch.setattr(
        streamlit_app,
        "build_draft_rankings",
        lambda _league_key: (_ for _ in ()).throw(AssertionError("direct build is unbounded")),
    )
    monkeypatch.setattr(
        streamlit_app,
        "load_rankings_with_fallback",
        lambda league_key, *, builder, paths, timeout_seconds: (
            captured.update(league_key=league_key, paths=paths) or board,
            RankingDataStatus("LIVE", "2026-08-20T00:00:00+00:00", 0.0),
        ),
    )
    monkeypatch.setattr(streamlit_app, "build_draft_assistant_from_rankings", lambda rankings, **_: rankings)
    monkeypatch.setattr(
        streamlit_app,
        "build_war_room_snapshot",
        lambda rankings, supplied_state, **_: {"context": {}, "rankings": rankings, "state": supplied_state},
    )

    snapshot = streamlit_app.build_live_view(paths=paths)

    assert captured == {
        "league_key": "drunk_sundays",
        "paths": paths,
    }
    assert snapshot["rankings"] is board


def test_direct_live_view_requires_injected_paths_and_preserves_production_snapshot(
    monkeypatch,
    tmp_path,
):
    """A representative helper path may create only its injected snapshot pair."""
    state = {
        "league_name": "Drunk Sundays",
        "league_key": "drunk_sundays",
        "user_team": "BLKWDW'S",
        "team_count": 12,
        "draft_rounds": 15,
        "current_pick": 1,
        "manual_picks": [],
        "keeper_reservations": [],
    }
    board = _board()
    production_before = _production_snapshot_artifacts()
    real_fallback = streamlit_app.load_rankings_with_fallback

    monkeypatch.setattr(streamlit_app, "load_or_initialize_war_room_state", lambda: state)
    monkeypatch.setattr(streamlit_app, "build_live_draft_context", lambda _state: {})
    monkeypatch.setattr(
        streamlit_app,
        "build_draft_assistant_from_rankings",
        lambda rankings, **_kwargs: rankings,
    )
    monkeypatch.setattr(
        streamlit_app,
        "build_war_room_snapshot",
        lambda rankings, supplied_state, **_kwargs: {
            "rankings": rankings,
            "state": supplied_state,
        },
    )

    def reject_implicit_production_paths(*_args, **kwargs):
        assert kwargs["paths"] is not streamlit_app.RANKINGS_SNAPSHOT_PATHS
        raise AssertionError("fallback was reached without injected paths")

    monkeypatch.setattr(
        streamlit_app,
        "load_rankings_with_fallback",
        reject_implicit_production_paths,
    )
    with pytest.raises(ValueError, match="explicit snapshot paths"):
        streamlit_app.build_live_view()
    assert _production_snapshot_artifacts() == production_before

    monkeypatch.setattr(streamlit_app, "load_rankings_with_fallback", real_fallback)
    paths = _paths(tmp_path)
    snapshot = streamlit_app.build_live_view(
        paths=paths,
        builder=lambda _league_key: board,
        timeout_seconds=1,
    )

    assert snapshot["rankings"] is board
    assert paths["metadata_path"].exists()
    assert _production_snapshot_artifacts() == production_before


def test_sleeper_request_uses_connect_and_read_timeout(monkeypatch):
    from fantasy_draft_model.integrations import sleeper_api

    captured = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {}

    def fake_get(url, timeout):
        captured["url"] = url
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr(sleeper_api.requests, "get", fake_get)
    sleeper_api.load_sleeper_players()

    assert captured["timeout"] == (
        sleeper_api.SLEEPER_CONNECT_TIMEOUT_SECONDS,
        sleeper_api.SLEEPER_READ_TIMEOUT_SECONDS,
    )
