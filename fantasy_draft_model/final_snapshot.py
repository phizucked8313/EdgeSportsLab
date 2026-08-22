"""Final, immutable EdgeIQ draft-night snapshot contracts."""

from __future__ import annotations

import json
import os
import re
import unicodedata
from hashlib import sha256
from io import StringIO
from pathlib import Path
from uuid import uuid4

import pandas as pd


CANONICAL_TEAMS = frozenset(
    "ARI ATL BAL BUF CAR CHI CIN CLE DAL DEN DET GB HOU IND JAX KC LV "
    "LAC LAR MIA MIN NE NO NYG NYJ PHI PIT SEA SF TB TEN WAS".split()
)
TEAM_ALIASES = {"AZ": "ARI", "LA": "LAR"}
SUPPORTED_POSITIONS = frozenset({"QB", "RB", "WR", "TE"})
REQUIRED_RANKING_INPUTS = (
    "projected_points",
    "vorp",
    "edgescore",
    "draft_score",
    "projection_confidence",
    "tier",
    "injury_risk_score",
    "is_currently_injured",
    "team",
    "bye_week",
    "position",
)
FREEZE_SCHEMA = "edgeiq-final-draft-snapshot/v1"
FROZEN_OPTIONAL_STRING_COLUMNS = (
    "prior_roster_team",
    "roster_status_provenance",
    "roster_status_source",
    "roster_status_source_date",
    "roster_status_retrieved_at",
    "current_injury_status",
    "current_injury_body_part",
    "current_injury_practice_status",
    "current_injury_source_timestamp",
    "current_injury_source_quality",
    "current_injury_data_quality",
    "current_injury_source",
    "current_injury_expected_return",
    "current_injury_timeline_source",
    "current_injury_timeline_source_date",
    "current_injury_timeline_note",
)
FROZEN_NULL_SENTINEL = "__EDGEIQ_FROZEN_NULL_V1__"


def normalize_player_name(value):
    text = str(value).strip().casefold().replace("estim�", "estime")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(character for character in text if not unicodedata.combining(character))
    return " ".join(re.findall(r"[a-z0-9]+", text))


def normalize_player_identity_name(value):
    """Normalize display names for cross-source identity fallback matching."""
    parts = normalize_player_name(value).split()
    if parts and parts[-1] in {"jr", "sr", "ii", "iii", "iv", "v"}:
        parts.pop()
    return " ".join(parts)


def _canonicalize_snapshot_values(board):
    result = board.copy(deep=True)
    result["team"] = (
        result["team"].astype(str).str.strip().str.upper().replace(TEAM_ALIASES)
    )
    result["position"] = result["position"].astype(str).str.strip().str.upper()
    corrupted = result["player_name_clean"].astype(str).eq("Audric Estim�")
    result.loc[corrupted, "player_name_clean"] = "Audric Estime"
    return result


def _clean_text(value):
    if pd.isna(value):
        return ""
    return str(value).strip()


def audit_depth_chart(board, depth):
    """Attach latest depth evidence, preferring stable GSIS identity."""
    players = board.copy(deep=True).reset_index(drop=True)
    depth_metadata_columns = (
        "depth_match_method",
        "depth_source_position",
        "depth_position_mismatch",
        "depth_pos_rank",
        "depth_role",
        "depth_timestamp",
        "prior_depth_pos_rank",
        "prior_depth_timestamp",
        "depth_role_changed",
        "depth_role_change_direction",
    )
    players = players.drop(
        columns=[column for column in depth_metadata_columns if column in players],
    )
    source = depth.copy(deep=True)
    for column in (
        "gsis_id", "player_name", "team", "pos_abb", "pos_rank",
        "edgeiq_role", "dt", "prior_depth_pos_rank",
        "prior_depth_timestamp", "depth_role_changed",
        "depth_role_change_direction",
    ):
        if column not in source.columns:
            source[column] = None
    source["_team"] = source["team"].astype(str).str.upper().replace(TEAM_ALIASES)
    source["_position"] = source["pos_abb"].astype(str).str.upper()
    source["_name"] = source["player_name"].map(normalize_player_name)
    source["_identity_name"] = source["player_name"].map(normalize_player_identity_name)
    records = source.to_dict("records")
    by_id = {
        _clean_text(row["gsis_id"]): row
        for row in records
        if _clean_text(row["gsis_id"])
    }
    by_fallback = {
        (row["_name"], row["_team"], row["_position"]): row
        for row in records
        if row["_name"] and row["_team"] and row["_position"]
    }
    suffix_candidates = {}
    for row in records:
        key = (row["_identity_name"], row["_team"], row["_position"])
        if all(key):
            suffix_candidates.setdefault(key, []).append(row)
    by_suffix_fallback = {
        key: matches[0]
        for key, matches in suffix_candidates.items()
        if len(matches) == 1
    }
    evidence = []
    for row in players.itertuples(index=False):
        if bool(getattr(row, "is_unsigned_free_agent", False)):
            evidence.append(
                {
                    "depth_match_method": "not_applicable_unsigned",
                    "depth_source_position": "",
                    "depth_position_mismatch": False,
                    "depth_pos_rank": None,
                    "depth_role": None,
                    "depth_timestamp": "",
                    "prior_depth_pos_rank": None,
                    "prior_depth_timestamp": "",
                    "depth_role_changed": False,
                    "depth_role_change_direction": "NOT_APPLICABLE",
                }
            )
            continue
        player_position = _clean_text(getattr(row, "position", "")).upper()
        match = by_id.get(_clean_text(getattr(row, "player_id", "")))
        id_position_mismatch = (
            match is not None and match.get("_position") != player_position
        )
        mismatched_id_match = match if id_position_mismatch else None
        if id_position_mismatch:
            match = None
        method = "gsis_id" if match is not None else ""
        if match is None:
            key = (
                normalize_player_name(getattr(row, "player_name_clean", "")),
                TEAM_ALIASES.get(_clean_text(getattr(row, "team", "")).upper(), _clean_text(getattr(row, "team", "")).upper()),
                player_position,
            )
            match = by_fallback.get(key)
            method = "name_team_position" if match is not None else ""
        if match is None:
            suffix_key = (
                normalize_player_identity_name(getattr(row, "player_name_clean", "")),
                TEAM_ALIASES.get(_clean_text(getattr(row, "team", "")).upper(), _clean_text(getattr(row, "team", "")).upper()),
                player_position,
            )
            match = by_suffix_fallback.get(suffix_key)
            method = "name_team_position_suffix" if match is not None else ""
        evidence.append(
            {
                "depth_match_method": method,
                "depth_source_position": _clean_text(
                    (match or mismatched_id_match or {}).get("pos_abb", "")
                ).upper(),
                "depth_position_mismatch": id_position_mismatch,
                "depth_pos_rank": match.get("pos_rank") if match is not None else None,
                "depth_role": match.get("edgeiq_role") if match is not None else None,
                "depth_timestamp": _clean_text(match.get("dt")) if match is not None else "",
                "prior_depth_pos_rank": match.get("prior_depth_pos_rank") if match is not None else None,
                "prior_depth_timestamp": _clean_text(match.get("prior_depth_timestamp")) if match is not None else "",
                "depth_role_changed": bool(match.get("depth_role_changed", False)) if match is not None else False,
                "depth_role_change_direction": _clean_text(match.get("depth_role_change_direction")) if match is not None else "",
            }
        )
    enriched = pd.concat([players, pd.DataFrame(evidence)], axis=1)
    missing = enriched.loc[enriched["depth_match_method"].eq(""), "player_name_clean"].tolist()
    return (
        {
            "reviewed_count": len(enriched),
            "matched_count": len(enriched) - len(missing),
            "missing_count": len(missing),
            "missing_players": missing,
        },
        enriched,
    )


def audit_rookies(audit_scope, *, top_300=None, expected_scope_count=None):
    """Review a declared rookie scope independently of Top-300 membership."""
    rookies = audit_scope.loc[
        audit_scope.get("is_rookie", False).fillna(False).astype(bool)
    ].copy()
    selected = rookies if top_300 is None else top_300.loc[
        top_300.get("is_rookie", False).fillna(False).astype(bool)
    ].copy()
    required = (
        "player_id", "player_name_clean", "team", "position", "rookie_year",
        "draft_number", "status", "on_current_roster", "depth_pos_rank", "depth_role",
        "projected_points", "projection_confidence",
    )
    failures = []
    authoritative_scope_count = (
        len(rookies) if expected_scope_count is None else expected_scope_count
    )
    if len(rookies) != authoritative_scope_count:
        failures.append(
            f"expected {authoritative_scope_count} audit-scope rookies, found {len(rookies)}"
        )
    for row in rookies.itertuples(index=False):
        missing = [column for column in required if column not in rookies or pd.isna(getattr(row, column, None)) or _clean_text(getattr(row, column, "")) == ""]
        if pd.to_numeric(pd.Series([getattr(row, "rookie_year", None)]), errors="coerce").iloc[0] != 2026:
            missing.append("rookie_year=2026")
        if missing:
            failures.append(f"{getattr(row, 'player_name_clean', '<unknown>')}: {sorted(set(missing))}")
    players = []
    for row in rookies.itertuples(index=False):
        depth_rank = pd.to_numeric(
            pd.Series([getattr(row, "depth_pos_rank", None)]),
            errors="coerce",
        ).iloc[0]
        players.append(
            {
                "player_id": _clean_text(getattr(row, "player_id", "")),
                "player_name": _clean_text(getattr(row, "player_name_clean", "")),
                "team": _clean_text(getattr(row, "team", "")),
                "position": _clean_text(getattr(row, "position", "")),
                "rookie_year": int(getattr(row, "rookie_year")),
                "draft_number": int(getattr(row, "draft_number")),
                "roster_status": _clean_text(getattr(row, "status", "")),
                "depth_rank": None if pd.isna(depth_rank) else int(depth_rank),
                "projected_role": _clean_text(getattr(row, "depth_role", "")),
                "projected_points": float(getattr(row, "projected_points")),
                "projection_confidence": float(getattr(row, "projection_confidence")),
            }
        )
    selected_ids = set(selected["player_id"].astype(str))
    outside_top_300 = [
        {
            "player_id": _clean_text(getattr(row, "player_id", "")),
            "player_name": _clean_text(getattr(row, "player_name_clean", "")),
            "draft_rank": int(getattr(row, "draft_rank")),
        }
        for row in rookies.itertuples(index=False)
        if _clean_text(getattr(row, "player_id", "")) not in selected_ids
    ]
    return {
        "expected_scope_count": authoritative_scope_count,
        "reviewed_count": len(rookies),
        "top_300_rookie_count": len(selected),
        "outside_top_300": outside_top_300,
        "failures": failures,
        "players": players,
    }


def audit_injuries(board, retrieved_at):
    """Classify every current injury and block unverified material statuses."""
    injured = board.loc[board.get("is_currently_injured", False).fillna(False).astype(bool)].copy()
    material = {"IR", "PUP", "OUT", "DOUBTFUL"}
    blocking = []
    records = []
    for row in injured.itertuples(index=False):
        status = _clean_text(getattr(row, "current_injury_status", "")).upper()
        source_timestamp = _clean_text(getattr(row, "current_injury_source_timestamp", ""))
        timeline_source = _clean_text(getattr(row, "current_injury_timeline_source", ""))
        expected_return = _clean_text(getattr(row, "current_injury_expected_return", ""))
        if status in material and not (source_timestamp or (timeline_source and expected_return)):
            blocking.append(_clean_text(getattr(row, "player_name_clean", "")))
        records.append(
            {
                "player_name": _clean_text(getattr(row, "player_name_clean", "")),
                "team": _clean_text(getattr(row, "team", "")),
                "position": _clean_text(getattr(row, "position", "")),
                "status": status,
                "body_part": _clean_text(getattr(row, "current_injury_body_part", "")),
                "source": _clean_text(getattr(row, "current_injury_source", "")),
                "source_timestamp": source_timestamp,
                "timeline_source": timeline_source,
                "expected_return": expected_return,
                "retrieved_at": retrieved_at,
            }
        )
    return {
        "reviewed_count": len(injured),
        "blocking_players": blocking,
        "players": records,
    }


def select_top_300(board):
    if not isinstance(board, pd.DataFrame):
        raise ValueError("production board must be a pandas DataFrame")
    if "draft_rank" not in board.columns:
        raise ValueError("production board is missing draft_rank")
    ranks = pd.to_numeric(board["draft_rank"], errors="coerce")
    selected = board.loc[ranks.between(1, 300)].copy()
    selected["draft_rank"] = pd.to_numeric(selected["draft_rank"], errors="raise").astype(int)
    selected = selected.sort_values("draft_rank", kind="stable").reset_index(drop=True)
    return _canonicalize_snapshot_values(selected)


def _require_columns(board, columns):
    missing = [column for column in columns if column not in board.columns]
    if missing:
        raise ValueError(f"Top 300 is missing ranking input columns: {missing}")


def _validate_keepers(board, keepers, keeper_reservations):
    if not isinstance(keepers, pd.DataFrame):
        raise ValueError("keeper declarations must be a DataFrame")
    declarations = [normalize_player_name(name) for name in keepers["player_name"]]
    reservations = [
        normalize_player_name(reservation.get("player_name", ""))
        for reservation in keeper_reservations
    ]
    if len(declarations) != len(set(declarations)):
        raise ValueError("keeper declarations contain a duplicate keeper")
    if len(reservations) != len(set(reservations)) or sorted(reservations) != sorted(declarations):
        raise ValueError("keeper reservations do not match keepers exactly once")
    board_names = board["player_name_clean"].map(normalize_player_name)
    missing = [name for name in declarations if int(board_names.eq(name).sum()) != 1]
    if missing:
        raise ValueError(f"keeper identities do not exist exactly once: {missing}")
    return len(declarations)


def validate_top_300(
    board,
    *,
    bye_by_team,
    keepers,
    keeper_reservations,
):
    if len(board) != 300:
        raise ValueError(f"final snapshot must contain exactly 300 rows, found {len(board)}")
    _require_columns(
        board,
        ("player_id", "player_name_clean", "draft_rank") + REQUIRED_RANKING_INPUTS,
    )
    ranks = pd.to_numeric(board["draft_rank"], errors="coerce")
    if ranks.tolist() != list(range(1, 301)):
        raise ValueError("final snapshot requires ranks 1 through 300 without gaps or duplicates")

    identifiers = board["player_id"].astype("string").str.strip()
    if identifiers.isna().any() or identifiers.eq("").any() or identifiers.duplicated().any():
        raise ValueError("final snapshot requires unique valid player IDs")
    names = board["player_name_clean"].astype("string").str.strip()
    normalized_names = names.map(normalize_player_name)
    if names.isna().any() or names.eq("").any() or normalized_names.duplicated().any():
        raise ValueError("final snapshot requires unique exact and normalized player names")
    if names.str.contains("\ufffd", regex=False).any():
        raise ValueError("final snapshot contains a corrupted exact player name")

    teams = board["team"].astype("string").str.strip().str.upper()
    if not teams.isin(CANONICAL_TEAMS).all():
        bad = sorted(teams.loc[~teams.isin(CANONICAL_TEAMS)].unique().tolist())
        raise ValueError(f"final snapshot contains a non-canonical NFL team: {bad}")
    positions = board["position"].astype("string").str.strip().str.upper()
    if not positions.isin(SUPPORTED_POSITIONS).all():
        raise ValueError("final snapshot contains an unsupported position")

    for column in REQUIRED_RANKING_INPUTS:
        if board[column].isna().any():
            raise ValueError(f"final snapshot has a missing ranking input: {column}")

    canonical_byes = {TEAM_ALIASES.get(str(team).upper(), str(team).upper()): int(bye) for team, bye in bye_by_team.items()}
    actual_byes = pd.to_numeric(board["bye_week"], errors="coerce")
    expected_byes = teams.map(canonical_byes)
    if expected_byes.isna().any() or not actual_byes.eq(expected_byes).all():
        raise ValueError("final snapshot contains an invalid team/bye pair")

    keeper_count = _validate_keepers(board, keepers, keeper_reservations)
    return {
        "row_count": 300,
        "rank_integrity": True,
        "identity_unique": True,
        "canonical_teams": True,
        "supported_positions": True,
        "team_bye_valid": True,
        "keeper_count": keeper_count,
    }


def build_freeze_manifest(
    board,
    *,
    source_commit,
    league_key,
    league_config_sha256,
    generated_at,
    inputs,
    audit,
    exclusions,
    waivers,
):
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        raise ValueError("source commit must be a full lowercase SHA-1")
    if not re.fullmatch(r"[0-9a-f]{64}", league_config_sha256):
        raise ValueError("league configuration hash must be SHA-256")
    if not isinstance(inputs, dict) or not inputs:
        raise ValueError("freeze manifest requires production input provenance")
    return {
        "schema": FREEZE_SCHEMA,
        "immutable": True,
        "source_commit_sha": source_commit,
        "league_key": league_key,
        "league_config_sha256": league_config_sha256,
        "generated_at": generated_at,
        "selected_row_count": len(board),
        "inputs": inputs,
        "audit": audit,
        "exclusions": list(exclusions),
        "waivers": list(waivers),
        "snapshot_file": None,
        "snapshot_sha256": None,
    }


def _json_safe_frame(board):
    safe = board.copy(deep=True)
    for column in safe.columns:
        safe[column] = safe[column].map(
            lambda value: json.dumps(value, ensure_ascii=False, sort_keys=True)
            if isinstance(value, (list, tuple, dict))
            else value
        )
    return safe


def _freeze_csv_frame(board):
    """Encode the narrow optional-string schema before CSV serialization."""
    safe = _json_safe_frame(board)
    for column in FROZEN_OPTIONAL_STRING_COLUMNS:
        if column not in safe:
            continue
        values = safe[column].astype("object")
        if values.eq(FROZEN_NULL_SENTINEL).any():
            raise ValueError(f"frozen CSV string field contains reserved null sentinel: {column}")
        safe[column] = values.where(values.notna(), FROZEN_NULL_SENTINEL)
    return safe


def _read_frozen_csv(payload):
    """Restore the explicit optional-string schema without dtype inference."""
    converters = {column: str for column in FROZEN_OPTIONAL_STRING_COLUMNS}
    board = pd.read_csv(StringIO(payload.decode("utf-8")), converters=converters)
    for column in FROZEN_OPTIONAL_STRING_COLUMNS:
        if column in board:
            values = board[column].astype("string")
            board[column] = values.mask(values.eq(FROZEN_NULL_SENTINEL), pd.NA)
    return board


def _atomic_write(path, payload):
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


def write_frozen_snapshot(board, manifest, csv_path, manifest_path):
    csv_path = Path(csv_path)
    manifest_path = Path(manifest_path)
    csv_payload = _freeze_csv_frame(board).to_csv(index=False).encode("utf-8")
    frozen_manifest = dict(manifest)
    frozen_manifest["snapshot_file"] = csv_path.name
    frozen_manifest["snapshot_sha256"] = sha256(csv_payload).hexdigest()
    manifest_payload = (
        json.dumps(frozen_manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    _atomic_write(csv_path, csv_payload)
    _atomic_write(manifest_path, manifest_payload)
    return frozen_manifest


def load_frozen_snapshot_offline(
    csv_path,
    manifest_path,
    *,
    bye_by_team,
    keepers,
    keeper_reservations,
):
    csv_path = Path(csv_path)
    manifest_path = Path(manifest_path)
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("frozen manifest is unavailable or invalid") from error
    if manifest.get("schema") != FREEZE_SCHEMA or manifest.get("immutable") is not True:
        raise ValueError("frozen manifest contract is invalid")
    if manifest.get("snapshot_file") != csv_path.name:
        raise ValueError("frozen manifest snapshot file does not match")
    payload = csv_path.read_bytes()
    if sha256(payload).hexdigest() != manifest.get("snapshot_sha256"):
        raise ValueError("frozen snapshot checksum does not match manifest")
    try:
        board = _read_frozen_csv(payload)
    except (UnicodeDecodeError, pd.errors.ParserError) as error:
        raise ValueError("frozen snapshot CSV is invalid") from error
    validate_top_300(
        board,
        bye_by_team=bye_by_team,
        keepers=keepers,
        keeper_reservations=keeper_reservations,
    )
    if manifest.get("selected_row_count") != len(board):
        raise ValueError("frozen manifest row count does not match snapshot")
    return board, manifest
