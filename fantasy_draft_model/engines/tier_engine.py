"""
EdgeIQ Tier Engine
Version 1
"""

import pandas as pd


# ============================================================
# SETTINGS
# ============================================================

POSITION_TIER_THRESHOLDS = {
    "QB": 18,
    "RB": 14,
    "WR": 14,
    "TE": 12,
}

TIER_THRESHOLD_MULTIPLIERS = {
    1: 1.00,
    2: 1.25,
    3: 1.50,
}

TIER_DEPTH_FACTORS = {
    1: 1.00,
    2: 0.85,
    3: 0.70,
    4: 0.55,
}


def get_tier_threshold(position, current_tier):
    base = float(POSITION_TIER_THRESHOLDS.get(position, 15))
    multiplier = TIER_THRESHOLD_MULTIPLIERS.get(int(current_tier), 1.75)
    return base * multiplier


def _tier_depth_factor(tier):
    return TIER_DEPTH_FACTORS.get(int(tier), 0.40)


# ============================================================
# CREATE POSITION TIERS
# ============================================================

def assign_position_tiers(df: pd.DataFrame) -> pd.DataFrame:
    """
    Assign tiers within each position.

    A new tier starts when the projected-point drop
    from the previous player becomes meaningful.

    VORP is also used as a secondary check.
    """

    df = df.copy()

    df["tier"] = 0
    df["tier_drop"] = 0.0
    df["tier_vorp_drop"] = 0.0
    df["tier_threshold"] = 0.0

    for position in [
        "QB",
        "RB",
        "WR",
        "TE",
    ]:

        position_mask = (
            df["position"] == position
        )

        position_df = (
            df[position_mask]
            .sort_values(
                by=[
                    "projected_points",
                    "vorp",
                ],
                ascending=False,
            )
            .copy()
        )

        if position_df.empty:
            continue

        current_tier = 1

        previous_points = None
        previous_vorp = None

        tier_values = []
        tier_drops = []
        tier_vorp_drops = []
        tier_thresholds = []

        for _, row in position_df.iterrows():

            projected_points = (
                row["projected_points"]
            )

            vorp = (
                row["vorp"]
            )

            if previous_points is None:

                threshold = get_tier_threshold(
                    position,
                    current_tier,
                )

                tier_values.append(
                    current_tier
                )

                tier_drops.append(
                    0.0
                )

                tier_vorp_drops.append(
                    0.0
                )

                tier_thresholds.append(
                    threshold
                )

            else:

                points_drop = (
                    previous_points
                    - projected_points
                )

                vorp_drop = (
                    previous_vorp
                    - vorp
                )

                threshold = get_tier_threshold(
                    position,
                    current_tier,
                )

                tier_drops.append(
                    round(
                        points_drop,
                        2,
                    )
                )

                tier_vorp_drops.append(
                    round(
                        vorp_drop,
                        2,
                    )
                )

                tier_thresholds.append(
                    threshold
                )

                # ------------------------------------
                # START NEW TIER
                # ------------------------------------

                if (
                    points_drop >= threshold
                    or vorp_drop >= threshold
                ):

                    current_tier += 1

                tier_values.append(
                    current_tier
                )

            previous_points = (
                projected_points
            )

            previous_vorp = (
                vorp
            )

        position_df[
            "tier"
        ] = tier_values

        position_df[
            "tier_drop"
        ] = tier_drops

        position_df[
            "tier_vorp_drop"
        ] = tier_vorp_drops

        position_df[
            "tier_threshold"
        ] = tier_thresholds

        df.loc[
            position_df.index,
            "tier"
        ] = (
            position_df["tier"]
        )

        df.loc[
            position_df.index,
            "tier_drop"
        ] = (
            position_df["tier_drop"]
        )

        df.loc[
            position_df.index,
            "tier_vorp_drop"
        ] = (
            position_df["tier_vorp_drop"]
        )

        df.loc[
            position_df.index,
            "tier_threshold"
        ] = (
            position_df["tier_threshold"]
        )

    df["tier"] = (
        df["tier"]
        .astype(int)
    )

    return df


# ============================================================
# TIER SIZE
# ============================================================

def add_tier_size(df: pd.DataFrame) -> pd.DataFrame:
    """
    Count how many players are in each position tier.
    """

    df = df.copy()

    tier_counts = (
        df.groupby(
            [
                "position",
                "tier",
            ]
        )
        .size()
        .rename(
            "tier_size"
        )
        .reset_index()
    )

    df = df.merge(
        tier_counts,
        on=[
            "position",
            "tier",
        ],
        how="left",
    )

    return df


# ============================================================
# TIER BOUNDARY METADATA
# ============================================================

def add_tier_boundary_metadata(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add the projection and VORP drop to the next tier for each player.
    """

    df = df.copy()

    df["tier_next_projection_drop"] = 0.0
    df["tier_next_vorp_drop"] = 0.0

    for position, position_df in df.groupby("position"):
        position_df = position_df.sort_values(
            by=["projected_points", "vorp"],
            ascending=False,
        )

        next_projection_drops = (
            position_df.groupby("tier", sort=True)["tier_drop"]
            .first()
            .shift(-1)
            .fillna(0.0)
        )
        next_vorp_drops = (
            position_df.groupby("tier", sort=True)["tier_vorp_drop"]
            .first()
            .shift(-1)
            .fillna(0.0)
        )

        position_mask = df["position"] == position
        df.loc[position_mask, "tier_next_projection_drop"] = (
            df.loc[position_mask, "tier"].map(next_projection_drops)
        )
        df.loc[position_mask, "tier_next_vorp_drop"] = (
            df.loc[position_mask, "tier"].map(next_vorp_drops)
        )

    return df


# ============================================================
# LIVE TIER SCARCITY
# ============================================================

def add_live_tier_scarcity(df: pd.DataFrame) -> pd.DataFrame:
    """
    Score scarcity from the players currently remaining in each tier.
    """

    df = df.copy()

    if "tier" not in df.columns:
        df["tier"] = pd.NA

    df["tier_remaining"] = (
        df.groupby(["position", "tier"], dropna=False)["tier"]
        .transform("size")
        .astype(int)
    )

    tier_values = pd.to_numeric(df["tier"], errors="coerce")
    tierless_mask = tier_values.isna()
    df.loc[tierless_mask, "tier_remaining"] = 0

    tier_remaining = df["tier_remaining"]
    tier_threshold = pd.to_numeric(
        df.get("tier_threshold", pd.Series(0.0, index=df.index)),
        errors="coerce",
    ).fillna(0.0)
    projection_drop = pd.to_numeric(
        df.get("tier_next_projection_drop", pd.Series(0.0, index=df.index)),
        errors="coerce",
    ).fillna(0.0)
    vorp_drop = pd.to_numeric(
        df.get("tier_next_vorp_drop", pd.Series(0.0, index=df.index)),
        errors="coerce",
    ).fillna(0.0)

    remaining_pressure = (100.0 / tier_remaining.clip(lower=1)).clip(upper=100.0)
    projection_drop_pressure = (
        100.0 * projection_drop / tier_threshold.clip(lower=1.0)
    ).clip(upper=100.0)
    vorp_drop_pressure = (
        100.0 * vorp_drop / tier_threshold.clip(lower=1.0)
    ).clip(upper=100.0)
    drop_pressure = pd.concat(
        [projection_drop_pressure, vorp_drop_pressure],
        axis=1,
    ).max(axis=1)
    depth_factor = tier_values.map(
        lambda tier: _tier_depth_factor(tier) if pd.notna(tier) else 0.0
    )

    df["tier_scarcity_score"] = (
        depth_factor * (0.60 * remaining_pressure + 0.40 * drop_pressure)
    ).round(2)

    return df


# ============================================================
# TIER STATUS
# ============================================================

def add_tier_status(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add simple draft intelligence about tier scarcity.
    """

    df = df.copy()

    def tier_status(row):
        size = row["tier_size"]

        if size == 1:
            return "ELITE SOLO TIER"

        if size == 2:
            return "SMALL TIER"

        if size <= 4:
            return "LIMITED TIER"

        return "DEPTH AVAILABLE"
    df[
        "tier_status"
    ] = (
        df.apply(
            tier_status,
            axis=1,
        )
    )

    return df


# ============================================================
# FULL TIER ENGINE
# ============================================================


def calculate_tiers(df: pd.DataFrame) -> pd.DataFrame:
    """
    Run complete EdgeIQ tier logic.

    Safe to rerun after:
    - keepers are removed
    - players are drafted
    - rankings change
    """

    df = df.copy()

    # --------------------------------------------------------
    # REMOVE OLD TIER DATA
    # --------------------------------------------------------

    old_tier_columns = [
        "tier",
        "tier_drop",
        "tier_vorp_drop",
        "tier_threshold",
        "tier_size",
        "tier_next_projection_drop",
        "tier_next_vorp_drop",
        "tier_remaining",
        "tier_scarcity_score",
        "tier_status",
    ]

    existing_columns = [
        column
        for column in old_tier_columns
        if column in df.columns
    ]

    if existing_columns:

        df = df.drop(
            columns=existing_columns
        )

    # --------------------------------------------------------
    # RECALCULATE TIERS
    # --------------------------------------------------------

    df = assign_position_tiers(
        df
    )

    df = add_tier_size(
        df
    )

    df = add_tier_boundary_metadata(
        df
    )

    df = add_live_tier_scarcity(
        df
    )

    df = add_tier_status(
        df
    )

    return df




# ============================================================
# TEST
# ============================================================

def main():

    print(
        "EdgeIQ Tier Engine ready."
    )


if __name__ == "__main__":
    main()
