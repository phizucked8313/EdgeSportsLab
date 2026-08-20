import pandas as pd

from fantasy_draft_model.ui import streamlit_app


def _board():
    return pd.DataFrame(
        [{"player_name_clean": "Alpha WR", "position": "WR", "team": "CLE", "draft_rank": 1}]
    )


def test_ui_cache_loads_rankings_once_and_never_refreshes_per_pick(monkeypatch, tmp_path):
    cache = {}
    paths = {"data_path": tmp_path / "rankings.csv", "metadata_path": tmp_path / "rankings.json"}
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
