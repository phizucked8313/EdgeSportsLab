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

    df["edgescore"] = df["edgescore"].round(2)

    return df