"""Deterministic production board assembly for the EdgeIQ draft-night War Room."""

from __future__ import annotations

from hashlib import sha256

import pandas as pd

from fantasy_draft_model.config import DATA_DIR
from fantasy_draft_model.final_snapshot import load_frozen_snapshot_offline
from fantasy_draft_model.keepers import load_keepers
from fantasy_draft_model.live_war_room import build_keeper_reservations, resolve_league
from fantasy_draft_model.models.schedule import BYE_WEEKS, get_bye_week
from fantasy_draft_model.models.special_teams import (
    build_defense_rankings,
    build_kicker_rankings,
)
from fantasy_draft_model.rankings_snapshot import RankingDataStatus


FROZEN_TOP_300_CSV = (
    DATA_DIR / "frozen" / "2026" / "edgeiq-top-300-2026.csv"
)
FROZEN_TOP_300_MANIFEST = (
    DATA_DIR / "frozen" / "2026" / "edgeiq-top-300-2026.manifest.json"
)
EXPECTED_FROZEN_TOP_300_SHA256 = (
    "1be7a6ce7e2f3b598b3e2419c837923b743796c4a68a5caf3cc5b334f64c5cf6"
)
FROZEN_RANKING_SOURCE = "FROZEN/OFFLINE"
SUPPLEMENTAL_RANKING_SOURCE = "SUPPLEMENTAL/OFFLINE"
UNSCORED_SUPPLEMENTAL_STATUS = "VALUE PENDING VERIFIED COMPONENT DATA"


def build_offline_special_teams_supplement() -> pd.DataFrame:
    """Build the committed K/DEF universe without inventing frozen ranks or value."""
    kickers = build_kicker_rankings().copy()
    defenses = build_defense_rankings().copy()
    special = pd.concat([kickers, defenses], ignore_index=True, sort=False)

    special["position"] = special["position"].astype(str).str.strip().str.upper()
    special["team"] = special["team"].astype(str).str.strip().str.upper()
    special["supplemental_position_rank"] = pd.to_numeric(
        special["position_rank"], errors="raise"
    ).astype(int)
    special["position_rank_label"] = (
        special["position"] + special["supplemental_position_rank"].astype(str)
    )
    special["bye_week"] = special["team"].map(get_bye_week)
    if special["bye_week"].eq(0).any():
        bad = sorted(special.loc[special["bye_week"].eq(0), "team"].unique())
        raise ValueError(f"supplemental special teams have unknown bye weeks: {bad}")

    # Supplemental rows intentionally have no frozen rank or fabricated model value.
    special["draft_rank"] = float("nan")
    special["is_supplemental"] = True
    special["ranking_source"] = SUPPLEMENTAL_RANKING_SOURCE
    special["supplemental_advisory_status"] = UNSCORED_SUPPLEMENTAL_STATUS
    return special


def load_production_draft_night_board(
    league_key: str,
    *,
    csv_path=FROZEN_TOP_300_CSV,
    manifest_path=FROZEN_TOP_300_MANIFEST,
    keeper_loader=None,
):
    """Load the immutable player baseline and append deterministic offline K/DEF rows.

    The frozen artifact is authoritative. Any validation/checksum problem fails closed;
    this function never calls a live rankings builder or mutable rankings cache.
    """
    league = resolve_league(league_key)
    loader = keeper_loader or load_keepers
    keepers = loader(league["name"])
    reservations = build_keeper_reservations(league, keepers)

    frozen, manifest = load_frozen_snapshot_offline(
        csv_path,
        manifest_path,
        bye_by_team=BYE_WEEKS,
        keepers=keepers,
        keeper_reservations=reservations,
    )

    actual_sha256 = sha256(csv_path.read_bytes()).hexdigest()
    manifest_sha256 = manifest.get("snapshot_sha256")
    if actual_sha256 != EXPECTED_FROZEN_TOP_300_SHA256:
        raise ValueError("production frozen snapshot does not match the verified draft-night checksum")
    if manifest_sha256 != EXPECTED_FROZEN_TOP_300_SHA256:
        raise ValueError("production frozen manifest does not reference the verified draft-night checksum")

    frozen = frozen.copy()
    frozen["is_supplemental"] = False
    frozen["ranking_source"] = FROZEN_RANKING_SOURCE
    supplement = build_offline_special_teams_supplement()
    board = pd.concat([frozen, supplement], ignore_index=True, sort=False)

    created_at = manifest.get("generated_at")
    status = RankingDataStatus(
        source=FROZEN_RANKING_SOURCE,
        created_at=created_at,
        age_seconds=None,
    )
    return board, status
