"""
EdgeIQ Draft Rankings Engine
Version 1
"""

import pandas as pd

from fantasy_draft_model.config import load_league_settings
from fantasy_draft_model.engines.projection_engine import (
    build_2026_projections,
)
from fantasy_draft_model.engines.tier_engine import add_live_tier_scarcity
from fantasy_draft_model.engines.vorp_engine import calculate_replacement_ranks
from fantasy_draft_model.models.football_intelligence import (
    add_football_intelligence,
)
from fantasy_draft_model.models.special_teams import (
    build_kicker_rankings,
    build_defense_rankings,
)
from fantasy_draft_model.models.schedule import get_bye_week


# ============================================================
# POSITION DEMAND SCALING
# ============================================================

def add_position_demand_metadata(
    df: pd.DataFrame,
    replacement_ranks,
    min_multiplier: float = 0.70,
    max_multiplier: float = 1.25,
) -> pd.DataFrame:
    """Add league-demand metadata for positional scarcity.

    The existing square-root multiplier remains the conservative tier signal.
    A second linear multiplier is retained for the available-supply signal so
    one-start QB/TE demand does not receive the same scarcity leverage as the
    much deeper RB/WR demand in FLEX leagues.
    """

    result = df.copy()
    positions = ("QB", "RB", "WR", "TE")
    demand = {
        position: max(0, int(replacement_ranks.get(position, 0)))
        for position in positions
    }
    positive_demand = [value for value in demand.values() if value > 0]
    neutral_demand = (
        sum(positive_demand) / len(positive_demand)
        if positive_demand
        else 1.0
    )

    position = (
        result.get("position", pd.Series("", index=result.index))
        .astype(str)
        .str.strip()
        .str.upper()
    )
    result["position_replacement_rank"] = (
        position.map(demand).fillna(0).astype(int)
    )

    replacement = pd.to_numeric(
        result["position_replacement_rank"],
        errors="coerce",
    ).fillna(0.0)
    active = replacement > 0

    multiplier = pd.Series(1.0, index=result.index, dtype=float)
    multiplier.loc[active] = (
        replacement.loc[active] / float(neutral_demand)
    ).pow(0.5)
    result["position_demand_multiplier"] = multiplier.clip(
        lower=float(min_multiplier),
        upper=float(max_multiplier),
    )

    supply_multiplier = pd.Series(1.0, index=result.index, dtype=float)
    supply_multiplier.loc[active] = (
        replacement.loc[active] / float(neutral_demand)
    )
    result["position_supply_demand_multiplier"] = supply_multiplier.clip(
        lower=0.50,
        upper=float(max_multiplier),
    )
    return result


def add_keeper_depletion_metadata(
    df: pd.DataFrame,
    keeper_counts,
    *,
    max_multiplier: float = 1.50,
) -> pd.DataFrame:
    """Attach keeper-driven remaining-demand and depletion metadata.

    This is positional supply math only. It never contains player-specific
    boosts. A position with many keepers inside its replacement-level demand
    receives a larger depletion multiplier because fewer starter-quality
    options remain available to the live draft room.
    """

    result = df.copy()
    positions = ("QB", "RB", "WR", "TE")
    normalized_counts = {
        position: max(0, int((keeper_counts or {}).get(position, 0)))
        for position in positions
    }
    position = (
        result.get("position", pd.Series("", index=result.index))
        .astype(str)
        .str.strip()
        .str.upper()
    )
    result["position_keeper_count"] = (
        position.map(normalized_counts).fillna(0).astype(int)
    )

    replacement = pd.to_numeric(
        result.get(
            "position_replacement_rank",
            pd.Series(0.0, index=result.index),
        ),
        errors="coerce",
    ).fillna(0.0).clip(lower=0.0)
    keeper_count = pd.to_numeric(
        result["position_keeper_count"],
        errors="coerce",
    ).fillna(0.0).clip(lower=0.0)
    keeper_count = keeper_count.where(
        replacement <= 0.0,
        keeper_count.clip(upper=replacement),
    )
    remaining = (replacement - keeper_count).clip(lower=0.0)
    result["position_remaining_replacement_demand"] = remaining.astype(int)

    depletion = pd.Series(1.0, index=result.index, dtype=float)
    active = (replacement > 0.0) & (remaining > 0.0)
    depletion.loc[active] = (
        replacement.loc[active] / remaining.loc[active]
    ).pow(0.5)
    depletion.loc[(replacement > 0.0) & (remaining <= 0.0)] = float(max_multiplier)
    result["keeper_depletion_multiplier"] = depletion.clip(
        lower=1.0,
        upper=float(max_multiplier),
    )
    return result


# ============================================================
# VORP NORMALIZATION
# ============================================================

def add_zero_based_vorp_score(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize positive VORP to 0-100 while treating replacement-level
    and below-replacement players as zero draft value.
    """

    df = df.copy()
    positive_vorp = df["vorp"].clip(lower=0)
    vorp_max = positive_vorp.max()

    if vorp_max > 0:
        df["vorp_score"] = positive_vorp / vorp_max * 100
    else:
        df["vorp_score"] = 0.0

    return df


# ============================================================
# POSITION PROJECTION NORMALIZATION
# ============================================================

def add_position_projection_score(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize projection value within position."""

    df = df.copy()
    df["projection_score"] = 50.0

    for position in df["position"].dropna().unique():
        position_mask = df["position"] == position

        if position == "QB" and "replacement_points" in df.columns:
            qb_value = (
                df.loc[position_mask, "projected_points"]
                - df.loc[position_mask, "replacement_points"]
            ).clip(lower=0)

            qb_value_max = qb_value.max()
            if qb_value_max > 0:
                df.loc[position_mask, "projection_score"] = (
                    qb_value / qb_value_max * 100
                )
            else:
                df.loc[position_mask, "projection_score"] = 0.0
            continue

        projection_min = df.loc[position_mask, "projected_points"].min()
        projection_max = df.loc[position_mask, "projected_points"].max()

        if projection_max != projection_min:
            df.loc[position_mask, "projection_score"] = (
                (
                    df.loc[position_mask, "projected_points"]
                    - projection_min
                )
                / (projection_max - projection_min)
                * 100
            )

    return df


# ============================================================
# DRAFT SCORE
# ============================================================

def calculate_draft_score(df: pd.DataFrame) -> pd.DataFrame:
    """Create one overall draft score."""

    df = df.copy()
    df = add_zero_based_vorp_score(df)
    if "projected_points" in df.columns:
        df = add_position_projection_score(df)
    if "tier_scarcity_score" not in df.columns:
        df["tier_scarcity_score"] = 0.0

    df["draft_score"] = (
        df["vorp_score"] * 0.35
        + df["edgescore"] * 0.25
        + df["projection_score"] * 0.20
        + df["projection_confidence"] * 0.10
        + df["tier_scarcity_score"] * 0.10
    )

    df["draft_score"] = df["draft_score"].clip(0, 100).round(2)
    return df


def recalculate_live_draft_score(df: pd.DataFrame) -> pd.DataFrame:
    """Recompute live draft scores without changing baseline draft order."""

    result = df.copy()
    baseline_rank = (
        result["draft_rank"].copy()
        if "draft_rank" in result.columns
        else None
    )
    result = calculate_draft_score(result)
    if baseline_rank is not None:
        result["draft_rank"] = baseline_rank
    return result


# ============================================================
# OVERALL RANKINGS
# ============================================================

def create_overall_rankings(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = (
        df.sort_values(
            by=["draft_score", "vorp", "projected_points"],
            ascending=False,
        )
        .reset_index(drop=True)
    )
    df["draft_rank"] = df.index + 1
    return df


# ============================================================
# POSITION RANK LABEL
# ============================================================

def add_position_rank_label(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["position_rank_label"] = (
        df["position"].astype(str)
        + df["position_rank"].astype(int).astype(str)
    )
    return df


# ============================================================
# DRAFT VALUE LABEL
# ============================================================

def add_draft_value_label(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    def value_label(row):
        if row["edgescore"] >= 90 and row["vorp"] > 0:
            return "ELITE TARGET"
        if row["draft_score"] >= 80:
            return "STRONG TARGET"
        if row["draft_score"] >= 65:
            return "GOOD VALUE"
        if row["draft_score"] >= 50:
            return "DEPTH VALUE"
        return "LATE / WATCH"

    df["draft_value"] = df.apply(value_label, axis=1)
    return df


# ============================================================
# BUILD COMPLETE DRAFT BOARD
# ============================================================

def build_draft_rankings(league_key):
    """Build draft rankings for one explicitly selected league."""
    print("\nBuilding EdgeIQ Draft Rankings...")

    df = build_2026_projections(league_key)
    df = df.loc[:, ~df.columns.duplicated()].copy()
    league_settings = load_league_settings(league_key)
    replacement_ranks = calculate_replacement_ranks(df, league_settings)
    df = add_position_demand_metadata(df, replacement_ranks)
    df = add_live_tier_scarcity(df)
    df = calculate_draft_score(df)
    df = create_overall_rankings(df)
    df = add_position_rank_label(df)
    df = add_draft_value_label(df)
    df = add_football_intelligence(df)

    kickers = build_kicker_rankings()
    defenses = build_defense_rankings()
    special_teams = pd.concat([kickers, defenses], ignore_index=True)

    special_teams["draft_rank"] = range(
        len(df) + 1,
        len(df) + len(special_teams) + 1,
    )
    special_teams["position_rank_label"] = (
        special_teams["position"].astype(str)
        + special_teams["position_rank"].astype(str)
    )

    df = pd.concat(
        [df, special_teams],
        ignore_index=True,
        sort=False,
    )
    df["bye_week"] = df["team"].map(get_bye_week)
    return df


# ============================================================
# DISPLAY
# ============================================================

def main():
    df = build_draft_rankings("drunk_sundays")

    columns = [
        "draft_rank",
        "player_name_clean",
        "position_rank_label",
        "team",
        "tier",
        "draft_score",
        "edgescore",
        "vorp",
        "projected_points",
        "floor_projection",
        "ceiling_projection",
        "projection_confidence",
        "injury_risk_score",
        "tier_remaining",
        "tier_scarcity_score",
        "tier_next_projection_drop",
        "tier_next_vorp_drop",
        "draft_value",
    ]

    print("\n============================================")
    print("EDGEIQ TOP 100 DRAFT RANKINGS")
    print("============================================\n")
    print(
        df[columns]
        .head(100)
        .round(2)
        .to_string(index=False)
    )
    print(f"\nTotal Ranked Players: {len(df):,}")


if __name__ == "__main__":
    main()
