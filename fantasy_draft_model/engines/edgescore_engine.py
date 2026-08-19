"""
EdgeIQ EdgeScore Engine

Combines multiple player evaluation categories into a single
0-100 EdgeScore.
"""

import pandas as pd


def calculate_edgescore(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds an EdgeScore column.

    Returns:
        DataFrame with EdgeScore.
    """

    df = df.copy()

    production = (
        df["custom_points_per_game"] /
        df["custom_points_per_game"].max()
    ) * 100

    opportunity = df["opportunity_score"]

    durability = df["durability_score"]

    injury = 100 - df["injury_risk_score"]

    confidence = df["projection_confidence"]

    df["edgescore"] = (

        production * 0.35 +

        opportunity * 0.25 +

        durability * 0.15 +

        injury * 0.10 +

        confidence * 0.15

    )
    # --------------------------------------------
    # ROOKIE EDGESCORE
    # --------------------------------------------

    if (
        "is_rookie" in df.columns
        and "rookie_talent_score" in df.columns
        and "projected_points" in df.columns
    ):

        rookie_mask = df["is_rookie"] == True

        max_projection = df["projected_points"].max()

        if max_projection > 0:

            rookie_projection_score = (
                df.loc[
                    rookie_mask,
                    "projected_points"
                ]
                / max_projection
                * 100
            )

        else:
            rookie_projection_score = 0.0

        rookie_talent = df.loc[
            rookie_mask,
            "rookie_talent_score"
        ]

        rookie_opportunity = (
            rookie_talent * 0.60
            +
            df.loc[
                rookie_mask,
                "opportunity_score"
            ] * 0.40
        )

        df.loc[
            rookie_mask,
            "edgescore"
        ] = (
            rookie_projection_score * 0.40
            +
            rookie_talent * 0.30
            +
            rookie_opportunity * 0.15
            +
            df.loc[
                rookie_mask,
                "durability_score"
            ] * 0.05
            +
            (
                100
                - df.loc[
                    rookie_mask,
                    "injury_risk_score"
                ]
            ) * 0.05
            +
            df.loc[
                rookie_mask,
                "projection_confidence"
            ] * 0.05
        )
    df["edgescore"] = df["edgescore"].round(2)

    return df









