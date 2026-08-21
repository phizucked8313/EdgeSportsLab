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


def normalize_player_name(value):
    text = str(value).strip().casefold().replace("estim�", "estime")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(character for character in text if not unicodedata.combining(character))
    return " ".join(re.findall(r"[a-z0-9]+", text))


def _canonicalize_snapshot_values(board):
    result = board.copy(deep=True)
    result["team"] = (
        result["team"].astype(str).str.strip().str.upper().replace(TEAM_ALIASES)
    )
    result["position"] = result["position"].astype(str).str.strip().str.upper()
    corrupted = result["player_name_clean"].astype(str).eq("Audric Estim�")
    result.loc[corrupted, "player_name_clean"] = "Audric Estime"
    return result


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
    csv_payload = _json_safe_frame(board).to_csv(index=False).encode("utf-8")
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
        board = pd.read_csv(StringIO(payload.decode("utf-8")))
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
