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

        threshold = (
            POSITION_TIER_THRESHOLDS
            .get(
                position,
                15,
            )
        )

        current_tier = 1

        previous_points = None
        previous_vorp = None

        tier_values = []
        tier_drops = []

        for _, row in position_df.iterrows():

            projected_points = (
                row["projected_points"]
            )

            vorp = (
                row["vorp"]
            )

            if previous_points is None:

                tier_values.append(
                    current_tier
                )

                tier_drops.append(
                    0.0
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

                tier_drops.append(
                    round(
                        points_drop,
                        2,
                    )
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
# TIER STATUS
# ============================================================

def add_tier_status(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add simple draft intelligence about tier scarcity.
    """

    df = df.copy()

    def tier_status(row):

        size = row[
            "tier_size"
        ]

        if size == 1:
            return "LAST PLAYER IN TIER"

        if size == 2:
            return "TIER ALMOST GONE"

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
        "tier_size",
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