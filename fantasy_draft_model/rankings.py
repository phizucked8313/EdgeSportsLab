"""
EdgeIQ Draft Rankings Engine
Version 1
"""

import pandas as pd

from fantasy_draft_model.engines.projection_engine import (
    build_2026_projections,
)
from fantasy_draft_model.models.football_intelligence import (
    add_football_intelligence,
)
from fantasy_draft_model.models.special_teams import (
    build_kicker_rankings,
    build_defense_rankings,
)


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
    df = add_position_projection_score(df)
    df["tier_scarcity_score"] = 0.0

    df.loc[
        df["tier_status"] == "LAST PLAYER IN TIER",
        "tier_scarcity_score",
    ] = 100
    df.loc[
        df["tier_status"] == "TIER ALMOST GONE",
        "tier_scarcity_score",
    ] = 80
    df.loc[
        df["tier_status"] == "LIMITED TIER",
        "tier_scarcity_score",
    ] = 60
    df.loc[
        df["tier_status"] == "DEPTH AVAILABLE",
        "tier_scarcity_score",
    ] = 35

    df["draft_score"] = (
        df["vorp_score"] * 0.35
        + df["edgescore"] * 0.25
        + df["projection_score"] * 0.20
        + df["projection_confidence"] * 0.10
        + df["tier_scarcity_score"] * 0.10
    )

    df["draft_score"] = df["draft_score"].clip(0, 100).round(2)
    return df


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
        "tier_status",
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
