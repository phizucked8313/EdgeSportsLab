"""
EdgeIQ Draft Pressure Meter
Version 1

Estimates how urgent it is to draft an available player.

IMPORTANT:
This is currently a HEURISTIC pressure score,
not a calibrated probability.
"""

import pandas as pd


def calculate_pressure_score(
    df: pd.DataFrame
) -> pd.DataFrame:

    df = df.copy()

    # --------------------------------------------------------
    # AVAILABLE BOARD POSITION
    # --------------------------------------------------------

    df = (
        df.sort_values(
            "draft_rank"
        )
        .reset_index(
            drop=True
        )
    )

    df["available_rank"] = (
        df.index + 1
    )


    # --------------------------------------------------------
    # BOARD PRESSURE
    # --------------------------------------------------------
    #
    # Players near the top of the remaining board
    # receive more pressure.

    df["board_pressure"] = (
        100
        - (
            (df["available_rank"] - 1)
            * 4
        )
    )

    df["board_pressure"] = (
        df["board_pressure"]
        .clip(
            lower=0,
            upper=100
        )
    )


    # --------------------------------------------------------
    # TIER PRESSURE
    # --------------------------------------------------------

    df["tier_pressure"] = 30.0

    df.loc[
        df["tier_status"]
        == "LIMITED TIER",
        "tier_pressure"
    ] = 60

    df.loc[
        df["tier_status"].isin(["SMALL TIER", "TIER ALMOST GONE"]),
        "tier_pressure"
    ] = 85

    df.loc[
        df["tier_status"].isin(["ELITE SOLO TIER", "LAST PLAYER IN TIER"]),
        "tier_pressure"
    ] = 100


    # --------------------------------------------------------
    # VORP PRESSURE
    # --------------------------------------------------------

    vorp_values = (
        pd.to_numeric(
            df["vorp"],
            errors="coerce",
        )
        .fillna(0.0)
        .clip(lower=0)
    )

    max_vorp = vorp_values.max()

    if max_vorp > 0:

        df["vorp_pressure"] = (
            vorp_values
            / max_vorp
            * 100
        )

    else:

        df["vorp_pressure"] = 0.0


    # --------------------------------------------------------
    # DRAFT SCORE PRESSURE
    # --------------------------------------------------------

    df["value_pressure"] = (
        pd.to_numeric(
            df["draft_score"],
            errors="coerce",
        )
        .fillna(0.0)
        .clip(
            lower=0,
            upper=100
        )
    )


    # --------------------------------------------------------
    # FINAL PRESSURE SCORE
    # --------------------------------------------------------

    df["pressure_score"] = (

        df["board_pressure"] * 0.30

        +

        df["tier_pressure"] * 0.30

        +

        df["vorp_pressure"] * 0.20

        +

        df["value_pressure"] * 0.20

    )


    df["pressure_score"] = (
        df["pressure_score"]
        .clip(
            lower=0,
            upper=100
        )
        .round(1)
    )


    return df


def pressure_label(
    score
):

    if score >= 90:
        return "DRAFT NOW"

    if score >= 75:
        return "HIGH"

    if score >= 60:
        return "ELEVATED"

    if score >= 40:
        return "MODERATE"

    return "SAFE TO WAIT"


def pressure_bar(
    score
):

    filled = round(
        score / 10
    )

    empty = (
        10 - filled
    )

    return (
        "█" * filled
        +
        "░" * empty
    )


def add_pressure_meter(
    df: pd.DataFrame
) -> pd.DataFrame:

    df = calculate_pressure_score(
        df
    )

    df["pressure_label"] = (
        df["pressure_score"]
        .apply(
            pressure_label
        )
    )

    df["pressure_bar"] = (
        df["pressure_score"]
        .apply(
            pressure_bar
        )
    )

    return df


def main():

    print(
        "EdgeIQ Draft Pressure Meter ready."
    )


if __name__ == "__main__":

    main()
