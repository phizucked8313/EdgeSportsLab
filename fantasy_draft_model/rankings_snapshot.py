"""Validated, generation-safe rankings snapshots for draft-night startup."""

from __future__ import annotations

import json
import os
import queue
import re
import threading
from io import StringIO
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

import pandas as pd


SNAPSHOT_SCHEMA = "edgeiq-rankings-snapshot/v1"
REQUIRED_RANKING_COLUMNS = (
    "player_name_clean",
    "position",
    "team",
    "draft_rank",
)
VALID_POSITIONS = frozenset({"QB", "RB", "WR", "TE", "K", "DEF"})

# All live-startup limits belong here so upstream integrations and the UI use
# the same bounded draft-night policy.
DRAFT_NIGHT_CONNECT_TIMEOUT_SECONDS = 5
DRAFT_NIGHT_READ_TIMEOUT_SECONDS = 15
DRAFT_NIGHT_RANKINGS_REFRESH_TIMEOUT_SECONDS = 15


@dataclass(frozen=True)
class RankingDataStatus:
    """Freshness and source facts displayed with a rankings board."""

    source: str
    created_at: str | None
    age_seconds: float | None
    failure_reason: str | None = None


class RankingRefreshError(RuntimeError):
    """No usable rankings are available from either live or cached sources."""


def _utc_now():
    return datetime.now(timezone.utc)


def _utc_timestamp(value):
    if not isinstance(value, str):
        raise ValueError("snapshot created_at must be an ISO UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("snapshot created_at is invalid") from error
    if parsed.tzinfo is None:
        raise ValueError("snapshot created_at must include UTC offset")
    return parsed.astimezone(timezone.utc)


def _normal_name(value):
    return str(value).strip().casefold()


def _validate_rankings(rankings):
    if not isinstance(rankings, pd.DataFrame):
        raise ValueError("rankings snapshot requires a pandas DataFrame")
    missing = [column for column in REQUIRED_RANKING_COLUMNS if column not in rankings]
    if missing:
        raise ValueError(f"rankings snapshot missing required columns: {missing}")
    if rankings.empty:
        raise ValueError("rankings snapshot cannot be empty")

    names = rankings["player_name_clean"]
    normalized_names = names.map(_normal_name)
    if names.isna().any() or normalized_names.eq("").any():
        raise ValueError("rankings snapshot contains an empty player name")
    if normalized_names.duplicated().any():
        raise ValueError("rankings snapshot contains duplicate normalized player names")

    positions = rankings["position"]
    normalized_positions = positions.astype(str).str.strip().str.upper()
    if positions.isna().any() or not normalized_positions.isin(VALID_POSITIONS).all():
        raise ValueError("rankings snapshot contains an invalid position")
    if rankings["team"].isna().any() or rankings["draft_rank"].isna().any():
        raise ValueError("rankings snapshot has missing required values")


def _json_safe_frame(rankings):
    """Make list-valued explanation fields CSV-safe without changing scalars."""
    safe = rankings.copy(deep=True)
    for column in safe.columns:
        if safe[column].map(lambda value: isinstance(value, (list, tuple, dict))).any():
            safe[column] = safe[column].map(
                lambda value: json.dumps(value, ensure_ascii=False)
                if isinstance(value, (list, tuple, dict))
                else value
            )
    return safe


def _data_path_from_metadata(data_path, metadata):
    data_path = Path(data_path)
    data_file = metadata.get("data_file")
    if not isinstance(data_file, str) or not data_file:
        raise ValueError("snapshot metadata is missing data_file")
    candidate = Path(data_file)
    if candidate.is_absolute() or candidate.name != data_file:
        raise ValueError("snapshot metadata data_file is invalid")
    expected_prefix = f"{data_path.stem}."
    if not candidate.name.startswith(expected_prefix) or candidate.suffix != data_path.suffix:
        raise ValueError("snapshot metadata does not match the requested data path")
    return data_path.parent / candidate


def _validate_metadata(metadata, league_key):
    if not isinstance(metadata, dict):
        raise ValueError("snapshot metadata must be an object")
    if metadata.get("schema") != SNAPSHOT_SCHEMA:
        raise ValueError("snapshot metadata schema is invalid")
    if metadata.get("league_key") != league_key:
        raise ValueError("snapshot metadata league does not match requested league")
    if metadata.get("source") != "LIVE":
        raise ValueError("snapshot metadata source is invalid")
    if metadata.get("required_columns") != list(REQUIRED_RANKING_COLUMNS):
        raise ValueError("snapshot metadata required columns are invalid")
    if not isinstance(metadata.get("row_count"), int) or metadata["row_count"] < 1:
        raise ValueError("snapshot metadata row count is invalid")
    if not isinstance(metadata.get("columns"), list):
        raise ValueError("snapshot metadata columns are invalid")
    checksum = metadata.get("csv_sha256")
    if not isinstance(checksum, str) or not re.fullmatch(r"[0-9a-f]{64}", checksum):
        raise ValueError("snapshot metadata checksum is invalid")
    _utc_timestamp(metadata.get("created_at"))


def _atomic_write_bytes(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{uuid4().hex}")
    try:
        with temporary.open("xb") as file:
            file.write(payload)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def save_rankings_snapshot(rankings, league_key, data_path, metadata_path):
    """Validate then publish a new CSV generation through an atomic JSON pointer."""
    _validate_rankings(rankings)
    data_path = Path(data_path)
    metadata_path = Path(metadata_path)
    safe_rankings = _json_safe_frame(rankings)
    generation_name = f"{data_path.stem}.{uuid4().hex}{data_path.suffix}"
    generation_path = data_path.parent / generation_name
    csv_payload = safe_rankings.to_csv(index=False).encode("utf-8")
    created_at = _utc_now().isoformat()
    metadata = {
        "schema": SNAPSHOT_SCHEMA,
        "league_key": league_key,
        "created_at": created_at,
        "row_count": len(safe_rankings),
        "required_columns": list(REQUIRED_RANKING_COLUMNS),
        "columns": list(safe_rankings.columns),
        "csv_sha256": sha256(csv_payload).hexdigest(),
        "source": "LIVE",
        "data_file": generation_name,
    }

    # Validate the exact serialized candidate before it can become live.
    _validate_metadata(metadata, league_key)
    candidate = pd.read_csv(StringIO(csv_payload.decode("utf-8")))
    _validate_rankings(candidate)
    if list(candidate.columns) != metadata["columns"] or len(candidate) != metadata["row_count"]:
        raise ValueError("serialized snapshot does not match its metadata")

    generation_path.parent.mkdir(parents=True, exist_ok=True)
    with generation_path.open("xb") as file:
        file.write(csv_payload)
        file.flush()
        os.fsync(file.fileno())
    pointer_payload = (json.dumps(metadata, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
    _atomic_write_bytes(metadata_path, pointer_payload)
    return RankingDataStatus("LIVE", created_at, 0.0)


def load_rankings_snapshot(league_key, data_path, metadata_path):
    """Load only a complete, checksum-verified rankings generation."""
    metadata_path = Path(metadata_path)
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("snapshot metadata is unavailable or invalid") from error
    _validate_metadata(metadata, league_key)
    generation_path = _data_path_from_metadata(data_path, metadata)
    try:
        csv_payload = generation_path.read_bytes()
    except OSError as error:
        raise ValueError("snapshot CSV is unavailable") from error
    if sha256(csv_payload).hexdigest() != metadata["csv_sha256"]:
        raise ValueError("snapshot CSV checksum does not match metadata")
    try:
        rankings = pd.read_csv(StringIO(csv_payload.decode("utf-8")))
    except (UnicodeDecodeError, pd.errors.ParserError) as error:
        raise ValueError("snapshot CSV is invalid") from error
    _validate_rankings(rankings)
    if list(rankings.columns) != metadata["columns"]:
        raise ValueError("snapshot CSV columns do not match metadata")
    if len(rankings) != metadata["row_count"]:
        raise ValueError("snapshot CSV row count does not match metadata")
    created_at = _utc_timestamp(metadata["created_at"])
    age_seconds = max(0.0, (_utc_now() - created_at).total_seconds())
    return rankings, RankingDataStatus("CACHED/OFFLINE", metadata["created_at"], age_seconds)


def run_with_timeout(callable_, timeout_seconds):
    """Run callable in a daemon worker so a timed-out request cannot delay exit."""
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    result_queue = queue.Queue(maxsize=1)

    def invoke():
        try:
            result_queue.put((True, callable_()))
        except BaseException as error:  # Preserve builder failures for fallback.
            result_queue.put((False, error))

    worker = threading.Thread(target=invoke, name="edgeiq-rankings-refresh", daemon=True)
    worker.start()
    try:
        succeeded, value = result_queue.get(timeout=timeout_seconds)
    except queue.Empty as error:
        raise TimeoutError(f"live rankings refresh exceeded {timeout_seconds:g}s") from error
    if succeeded:
        return value
    raise value


def _paths_from(paths):
    if isinstance(paths, dict):
        data_path = paths.get("data_path", paths.get("csv_path"))
        metadata_path = paths.get("metadata_path", paths.get("meta_path"))
    elif isinstance(paths, (tuple, list)) and len(paths) == 2:
        data_path, metadata_path = paths
    else:
        data_path = getattr(paths, "data_path", None)
        metadata_path = getattr(paths, "metadata_path", None)
    if data_path is None or metadata_path is None:
        raise ValueError("paths must supply data_path and metadata_path")
    return data_path, metadata_path


def load_rankings_with_fallback(league_key, builder, paths, timeout_seconds):
    """Bound live construction and otherwise return the latest validated snapshot."""
    data_path, metadata_path = _paths_from(paths)
    try:
        rankings = run_with_timeout(lambda: builder(league_key), timeout_seconds)
        _validate_rankings(rankings)
        status = save_rankings_snapshot(rankings, league_key, data_path, metadata_path)
        return rankings, status
    except Exception as live_error:
        try:
            rankings, cached_status = load_rankings_snapshot(
                league_key,
                data_path,
                metadata_path,
            )
        except Exception as cache_error:
            raise RankingRefreshError(
                f"Live rankings refresh failed ({live_error}); no valid cache is available ({cache_error})"
            ) from cache_error
        return rankings, replace(cached_status, failure_reason=str(live_error))
