import pandas as pd

from fantasy_draft_model.integrations import depth_chart_loader
from fantasy_draft_model.rankings_snapshot import (
    load_rankings_with_fallback,
    save_rankings_snapshot,
)


class FakeDepthFrame:
    def __init__(self, dataframe):
        self._dataframe = dataframe

    def to_pandas(self):
        return self._dataframe.copy()


def _sample_depth_rows():
    return pd.DataFrame(
        [
            {
                "dt": "2026-08-18T07:00:00Z",
                "team": "CLE",
                "player_name": "Old Starter",
                "gsis_id": "00-old-cle",
                "pos_name": "Running Back",
                "pos_abb": "RB",
                "pos_rank": 1,
            },
            {
                "dt": "2026-08-19T07:00:00Z",
                "team": "CLE",
                "player_name": "Current Starter",
                "gsis_id": "00-current-cle",
                "pos_name": "Running Back",
                "pos_abb": "RB",
                "pos_rank": 1,
            },
            {
                "dt": "2026-08-17T07:00:00Z",
                "team": "PIT",
                "player_name": "Old Backup",
                "gsis_id": "00-old-pit",
                "pos_name": "Wide Receiver",
                "pos_abb": "WR",
                "pos_rank": 2,
            },
            {
                "dt": "2026-08-19T07:00:00Z",
                "team": "PIT",
                "player_name": "Current Backup",
                "gsis_id": "00-current-pit",
                "pos_name": "Wide Receiver",
                "pos_abb": "WR",
                "pos_rank": 2,
            },
        ]
    )


def test_load_depth_charts_uses_nflreadpy_current_season_default(monkeypatch):
    called = {}

    def fake_load_depth_charts(*args, **kwargs):
        called["args"] = args
        called["kwargs"] = kwargs
        return FakeDepthFrame(_sample_depth_rows())

    monkeypatch.setattr(
        depth_chart_loader.nfl,
        "load_depth_charts",
        fake_load_depth_charts,
    )

    depth_chart_loader.load_depth_charts()

    assert called["args"] == ()
    assert called["kwargs"] == {}


def test_load_depth_charts_keeps_latest_snapshot_per_team(monkeypatch):
    monkeypatch.setattr(
        depth_chart_loader.nfl,
        "load_depth_charts",
        lambda *args, **kwargs: FakeDepthFrame(_sample_depth_rows()),
    )

    depth = depth_chart_loader.load_depth_charts()

    assert depth["player_name"].tolist() == [
        "Current Starter",
        "Current Backup",
    ]
    assert depth["gsis_id"].tolist() == [
        "00-current-cle",
        "00-current-pit",
    ]
    assert depth["edgeiq_role"].tolist() == [
        "STARTER",
        "BACKUP",
    ]


def test_depth_chart_upstream_failure_falls_back_through_rankings_coordinator(tmp_path):
    paths = {
        "data_path": tmp_path / "rankings.csv",
        "metadata_path": tmp_path / "rankings.json",
    }
    cached = pd.DataFrame(
        [{"player_name_clean": "Cached RB", "position": "RB", "team": "DET", "draft_rank": 1}]
    )
    save_rankings_snapshot(cached, "drunk_sundays", **paths)
    calls = []

    def stalled_depth_chart_load():
        calls.append(True)
        raise TimeoutError("nflverse depth-chart upstream stalled")

    def builder(_league_key):
        depth_chart_loader.load_depth_charts(
            depth_chart_loader=stalled_depth_chart_load,
        )

    loaded, status = load_rankings_with_fallback(
        "drunk_sundays",
        builder=builder,
        paths=paths,
        timeout_seconds=15,
    )

    assert calls == [True]
    assert loaded["player_name_clean"].tolist() == ["Cached RB"]
    assert status.source == "CACHED/OFFLINE"
    assert "stalled" in status.failure_reason
