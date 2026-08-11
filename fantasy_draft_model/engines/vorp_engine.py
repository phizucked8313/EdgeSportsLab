"""
EdgeIQ VORP Engine
Version 1
"""

import pandas as pd

# 12-team league replacement players
REPLACEMENT_RANKS = {
    "QB": 12,
    "RB": 24,
    "WR": 24,
    "TE": 12
}


def calculate_vorp(df: pd.DataFrame):

    df = df.copy()

    df["position_rank"] = 0
    df["vorp"] = 0.0
    df["replacement_points"] = 0.0

    for position, replacement_rank in REPLACEMENT_RANKS.items():

        position_mask = df["position"] == position

        position_players = (
            df[position_mask]
            .sort_values(
                "projected_points",
                ascending=False
            )
            .copy()
        )

        position_players["position_rank"] = (
            range(
                1,
                len(position_players) + 1
            )
        )

        if len(position_players) >= replacement_rank:

            replacement_points = (
                position_players.iloc[
                    replacement_rank - 1
                ]["projected_points"]
            )

        else:

            replacement_points = (
                position_players[
                    "projected_points"
                ].min()
            )

        position_players["replacement_points"] = replacement_points

        position_players["vorp"] = (
            position_players["projected_points"]
            - replacement_points
        )

        df.loc[
            position_players.index,
            "position_rank"
        ] = (
            position_players["position_rank"]
        )

        df.loc[
            position_players.index,
            "replacement_points"
        ] = replacement_points

        df.loc[
            position_players.index,
            "vorp"
        ] = (
            position_players["vorp"]
        )

    df["overall_rank"] = (
        df["projected_points"]
        .rank(
            ascending=False,
            method="min"
        )
        .astype(int)
    )

    return df