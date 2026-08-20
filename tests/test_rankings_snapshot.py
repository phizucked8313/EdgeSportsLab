import json
import queue
import time
from hashlib import sha256

import pandas as pd
import pytest

from fantasy_draft_model.rankings_snapshot import (
    RankingRefreshError,
    load_rankings_snapshot,
    load_rankings_with_fallback,
    run_with_timeout,
    save_rankings_snapshot,
)


def _board():
    return pd.DataFrame(
        [
            {
                "player_name_clean": "Alpha WR",
                "position": "WR",
                "team": "CLE",
                "draft_rank": 1,
                "explanation_drivers": ["volume", "role"],
            },
            {
                "player_name_clean": "Beta RB",
                "position": "RB",
                "team": "DET",
                "draft_rank": 2,
                "explanation_drivers": ["touches"],
            },
        ]
    )


def _paths(tmp_path):
    return {
        "data_path": tmp_path / "rankings.csv",
        "metadata_path": tmp_path / "rankings.json",
    }


def test_snapshot_round_trip_reports_cached_freshness(tmp_path):
    paths = _paths(tmp_path)
    board = _board()

    save_rankings_snapshot(board, "drunk_sundays", **paths)
    loaded, status = load_rankings_snapshot("drunk_sundays", **paths)

    assert loaded.drop(columns=["explanation_drivers"]).to_dict("records") == board.drop(
        columns=["explanation_drivers"]
    ).to_dict("records")
    assert loaded["explanation_drivers"].tolist() == [
        '["volume", "role"]',
        '["touches"]',
    ]
    assert status.source == "CACHED/OFFLINE"
    assert status.created_at
    assert status.age_seconds >= 0


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda paths: paths["metadata_path"].write_text("{}", encoding="utf-8"), "schema"),
        (
            lambda paths: paths["metadata_path"].write_text(
                paths["metadata_path"].read_text(encoding="utf-8").replace(
                    '"drunk_sundays"', '"other_league"'
                ),
                encoding="utf-8",
            ),
            "league",
        ),
    ],
)
def test_snapshot_rejects_invalid_metadata(tmp_path, mutate, message):
    paths = _paths(tmp_path)
    save_rankings_snapshot(_board(), "drunk_sundays", **paths)
    mutate(paths)

    with pytest.raises(ValueError, match=message):
        load_rankings_snapshot("drunk_sundays", **paths)


def test_snapshot_rejects_tampered_csv_checksum(tmp_path):
    paths = _paths(tmp_path)
    save_rankings_snapshot(_board(), "drunk_sundays", **paths)
    metadata = json.loads(paths["metadata_path"].read_text(encoding="utf-8"))
    (tmp_path / metadata["data_file"]).write_text("tampered", encoding="utf-8")

    with pytest.raises(ValueError, match="checksum"):
        load_rankings_snapshot("drunk_sundays", **paths)


def test_snapshot_rejects_tampered_csv_missing_required_column(tmp_path):
    paths = _paths(tmp_path)
    save_rankings_snapshot(_board(), "drunk_sundays", **paths)
    metadata = json.loads(paths["metadata_path"].read_text(encoding="utf-8"))
    generation_path = tmp_path / metadata["data_file"]
    tampered = pd.read_csv(generation_path).drop(columns=["team"])
    payload = tampered.to_csv(index=False).encode("utf-8")
    generation_path.write_bytes(payload)
    metadata["csv_sha256"] = sha256(payload).hexdigest()
    paths["metadata_path"].write_text(json.dumps(metadata), encoding="utf-8")

    with pytest.raises(ValueError, match="required"):
        load_rankings_snapshot("drunk_sundays", **paths)


def test_snapshot_rejects_mismatched_metadata_column_list(tmp_path):
    paths = _paths(tmp_path)
    save_rankings_snapshot(_board(), "drunk_sundays", **paths)
    metadata = json.loads(paths["metadata_path"].read_text(encoding="utf-8"))
    metadata["columns"].append("not_present")
    paths["metadata_path"].write_text(json.dumps(metadata), encoding="utf-8")

    with pytest.raises(ValueError, match="columns"):
        load_rankings_snapshot("drunk_sundays", **paths)


@pytest.mark.parametrize(
    ("board", "message"),
    [
        (_board().drop(columns=["team"]), "required"),
        (_board().assign(player_name_clean=["Alpha WR", " alpha wr "]), "duplicate"),
        (_board().assign(position=["WR", "P"]), "position"),
    ],
)
def test_snapshot_rejects_invalid_rankings(tmp_path, board, message):
    with pytest.raises(ValueError, match=message):
        save_rankings_snapshot(board, "drunk_sundays", **_paths(tmp_path))


def test_snapshot_rejects_mismatched_row_count(tmp_path):
    paths = _paths(tmp_path)
    save_rankings_snapshot(_board(), "drunk_sundays", **paths)
    metadata = json.loads(paths["metadata_path"].read_text(encoding="utf-8"))
    metadata["row_count"] = 999
    paths["metadata_path"].write_text(json.dumps(metadata), encoding="utf-8")

    with pytest.raises(ValueError, match="row count"):
        load_rankings_snapshot("drunk_sundays", **paths)


def test_failed_save_keeps_previous_valid_snapshot_pair(tmp_path):
    paths = _paths(tmp_path)
    save_rankings_snapshot(_board(), "drunk_sundays", **paths)
    pointer_before = paths["metadata_path"].read_bytes()

    with pytest.raises(ValueError, match="position"):
        save_rankings_snapshot(
            _board().assign(position=["WR", "INVALID"]),
            "drunk_sundays",
            **paths,
        )

    loaded, _status = load_rankings_snapshot("drunk_sundays", **paths)
    assert paths["metadata_path"].read_bytes() == pointer_before
    assert loaded["player_name_clean"].tolist() == ["Alpha WR", "Beta RB"]


def test_live_success_saves_original_board_and_labels_live(tmp_path):
    paths = _paths(tmp_path)
    board = _board()

    loaded, status = load_rankings_with_fallback(
        "drunk_sundays",
        builder=lambda _league: board,
        paths=paths,
        timeout_seconds=1,
    )

    assert loaded is board
    assert status.source == "LIVE"
    cached, _cached_status = load_rankings_snapshot("drunk_sundays", **paths)
    assert cached["player_name_clean"].tolist() == board["player_name_clean"].tolist()


def test_live_timeout_uses_cached_snapshot_and_returns_promptly(tmp_path):
    paths = _paths(tmp_path)
    save_rankings_snapshot(_board(), "drunk_sundays", **paths)

    def too_slow(_league):
        time.sleep(0.5)
        return _board()

    started = time.monotonic()
    loaded, status = load_rankings_with_fallback(
        "drunk_sundays",
        builder=too_slow,
        paths=paths,
        timeout_seconds=0.01,
    )

    assert time.monotonic() - started < 0.25
    assert loaded["player_name_clean"].tolist() == ["Alpha WR", "Beta RB"]
    assert status.source == "CACHED/OFFLINE"
    assert "exceeded" in status.failure_reason


def test_timeout_uses_injected_daemon_thread_and_wait_seam_without_wall_clock():
    captured = {}

    class NeverCompletesThread:
        def __init__(self, *, target, name, daemon):
            captured.update(target=target, name=name, daemon=daemon)

        def start(self):
            captured["started"] = True

    def timed_out_wait(_result_queue, timeout_seconds):
        captured["timeout_seconds"] = timeout_seconds
        raise queue.Empty

    with pytest.raises(TimeoutError, match="exceeded 15s"):
        run_with_timeout(
            lambda: _board(),
            15,
            thread_factory=NeverCompletesThread,
            wait_for_result=timed_out_wait,
        )

    assert captured["daemon"] is True
    assert captured["started"] is True
    assert captured["timeout_seconds"] == 15


def test_live_failure_without_valid_cache_raises_refresh_error(tmp_path):
    with pytest.raises(RankingRefreshError, match="cache"):
        load_rankings_with_fallback(
            "drunk_sundays",
            builder=lambda _league: (_ for _ in ()).throw(RuntimeError("upstream down")),
            paths=_paths(tmp_path),
            timeout_seconds=1,
        )
