import json
import queue
import time
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

import pandas as pd
import pytest

import fantasy_draft_model.rankings_snapshot as rankings_snapshot
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


def _production_board():
    """A hand-built Drunk Sundays board at its 12-team, 15-round capacity."""
    positions = ("QB", "RB", "WR", "TE", "K", "DEF")
    return pd.DataFrame(
        [
            {
                "player_name_clean": f"Production Player {index:03d}",
                "position": positions[index % len(positions)],
                "team": f"T{index % 32:02d}",
                "draft_rank": index + 1,
                "position_rank_label": f"P{index + 1}",
                "tier": 1,
                "tier_next_projection_drop": 0.0,
                "tier_next_vorp_drop": 0.0,
                "projected_points": 250.0 - index,
                "vorp": 100.0 - index,
                "edgescore": 90.0 - index / 10,
                "draft_score": 80.0 - index / 10,
                "projection_confidence": 0.8,
                "injury_risk_score": 0.2,
                "bye_week": 7,
            }
            for index in range(180)
        ]
    )


def _failing_live_builder(_league_key):
    raise RuntimeError("live source unavailable")


def _assert_production_cache_is_rejected(paths):
    try:
        _rankings, status = load_rankings_with_fallback(
            "drunk_sundays",
            builder=_failing_live_builder,
            paths=paths,
            timeout_seconds=1,
            production_publication=True,
        )
    except RankingRefreshError:
        return
    pytest.fail(
        "production fallback accepted an incomplete cached board as "
        f"{status.source}; expected RankingRefreshError"
    )


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


def test_production_publication_rejects_one_row_four_column_synthetic_board(tmp_path):
    """A fixture-sized board must never be eligible to publish production data."""
    with pytest.raises(
        ValueError,
        match="minimum canonical draft capacity.*full War Room required columns",
    ):
        save_rankings_snapshot(
            _board().loc[:, ["player_name_clean", "position", "team", "draft_rank"]].iloc[:1],
            "drunk_sundays",
            **_paths(tmp_path),
            production_publication=True,
        )


def test_production_fallback_rejects_fixture_sized_cached_board_after_live_failure(tmp_path):
    paths = _paths(tmp_path)
    save_rankings_snapshot(_board(), "drunk_sundays", **paths)

    _assert_production_cache_is_rejected(paths)


def test_production_snapshot_loader_rejects_fixture_sized_cached_board(tmp_path):
    paths = _paths(tmp_path)
    save_rankings_snapshot(_board(), "drunk_sundays", **paths)

    with pytest.raises(ValueError, match="minimum canonical draft capacity.*full War Room"):
        load_rankings_snapshot(
            "drunk_sundays",
            **paths,
            production_publication=True,
        )


def test_production_fallback_rejects_invalid_current_pointer_even_when_old_generation_exists(
    tmp_path,
):
    paths = _paths(tmp_path)
    save_rankings_snapshot(
        _production_board(),
        "drunk_sundays",
        **paths,
        production_publication=True,
    )
    complete_metadata = json.loads(paths["metadata_path"].read_text(encoding="utf-8"))
    complete_generation = tmp_path / complete_metadata["data_file"]

    save_rankings_snapshot(_board(), "drunk_sundays", **paths)

    assert complete_generation.exists()
    _assert_production_cache_is_rejected(paths)


def test_production_fallback_uses_complete_cached_board_with_freshness_and_live_failure_reason(
    tmp_path,
):
    paths = _paths(tmp_path)
    save_rankings_snapshot(
        _production_board(),
        "drunk_sundays",
        **paths,
        production_publication=True,
    )
    metadata = json.loads(paths["metadata_path"].read_text(encoding="utf-8"))

    loaded, status = load_rankings_with_fallback(
        "drunk_sundays",
        builder=_failing_live_builder,
        paths=paths,
        timeout_seconds=1,
        production_publication=True,
    )

    assert len(loaded) == 180
    assert status.source == "CACHED/OFFLINE"
    assert status.created_at == metadata["created_at"]
    assert status.age_seconds >= 0
    assert status.failure_reason == "live source unavailable"


def test_nonproduction_fallback_keeps_fixture_sized_cached_board_behavior(tmp_path):
    paths = _paths(tmp_path)
    save_rankings_snapshot(_board(), "drunk_sundays", **paths)

    loaded, status = load_rankings_with_fallback(
        "drunk_sundays",
        builder=_failing_live_builder,
        paths=paths,
        timeout_seconds=1,
    )

    assert loaded["player_name_clean"].tolist() == ["Alpha WR", "Beta RB"]
    assert status.source == "CACHED/OFFLINE"
    assert status.failure_reason == "live source unavailable"


def test_archive_rankings_snapshot_preserves_pointer_generation_and_manifest_before_replacement(
    tmp_path,
):
    paths = _paths(tmp_path)
    archive_root = tmp_path / "archives"
    fixed_now = datetime(2026, 8, 20, 12, tzinfo=timezone.utc)
    save_rankings_snapshot(
        _production_board(),
        "drunk_sundays",
        **paths,
        production_publication=True,
    )
    metadata = json.loads(paths["metadata_path"].read_text(encoding="utf-8"))
    generation_path = tmp_path / metadata["data_file"]
    sources_before = {
        paths["metadata_path"].resolve(): paths["metadata_path"].read_bytes(),
        generation_path.resolve(): generation_path.read_bytes(),
    }

    first = rankings_snapshot.archive_rankings_snapshot(
        "drunk_sundays",
        **paths,
        archive_root=archive_root,
        production_publication=True,
        now_func=lambda: fixed_now,
        id_func=lambda: "same-id",
    )
    second = rankings_snapshot.archive_rankings_snapshot(
        "drunk_sundays",
        **paths,
        archive_root=archive_root,
        production_publication=True,
        now_func=lambda: fixed_now,
        id_func=lambda: "same-id",
    )

    assert first != second
    assert first.is_dir()
    assert second.is_dir()
    manifest = json.loads((first / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema"] == "edgeiq-rankings-snapshot-archive/v1"
    assert manifest["archived_at"] == fixed_now.isoformat()
    assert {entry["role"] for entry in manifest["artifacts"]} == {
        "pointer",
        "generation",
    }
    for entry in manifest["artifacts"]:
        source = Path(entry["source_path"])
        archived = Path(entry["archive_path"])
        assert archived.parent == first
        assert archived.read_bytes() == sources_before[source]
        assert entry["byte_length"] == len(sources_before[source])
        assert entry["sha256"] == sha256(sources_before[source]).hexdigest()

    updated_board = _production_board()
    updated_board.loc[0, "projected_points"] = 999.0
    save_rankings_snapshot(
        updated_board,
        "drunk_sundays",
        **paths,
        production_publication=True,
    )

    assert {path: path.read_bytes() for path in sources_before} != sources_before
    assert not list(first.glob("*.tmp-*"))


def test_archive_preserves_checksum_valid_fixture_snapshot_before_remediation(tmp_path):
    paths = _paths(tmp_path)
    archive_root = tmp_path / "archives"
    save_rankings_snapshot(_board(), "drunk_sundays", **paths)
    metadata = json.loads(paths["metadata_path"].read_text(encoding="utf-8"))
    generation_path = tmp_path / metadata["data_file"]
    sources_before = {
        paths["metadata_path"].resolve(): paths["metadata_path"].read_bytes(),
        generation_path.resolve(): generation_path.read_bytes(),
    }

    archive_directory = rankings_snapshot.archive_rankings_snapshot(
        "drunk_sundays",
        **paths,
        archive_root=archive_root,
    )

    manifest = json.loads((archive_directory / "manifest.json").read_text(encoding="utf-8"))
    assert {entry["source_path"] for entry in manifest["artifacts"]} == {
        str(path) for path in sources_before
    }
    assert {path: path.read_bytes() for path in sources_before} == sources_before


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
