"""
EdgeIQ VORP Engine
Version 1
"""

import pandas as pd


FLEX_ELIGIBLE_POSITIONS = ("RB", "WR")
VORP_POSITIONS = ("QB", "RB", "WR", "TE")


def calculate_replacement_ranks(
    df: pd.DataFrame,
    league_settings,
) -> dict[str, int]:
    """Derive replacement ranks from lineup demand plus projected FLEX use."""

    settings = league_settings
    teams = int(settings["teams"])
    lineup = settings["lineup"]

    replacement_ranks = {
        position: teams * int(lineup.get(position, 0))
        for position in VORP_POSITIONS
    }

    flex_slots = teams * int(lineup.get("FLEX", 0))
    flex_candidates = []

    for position in FLEX_ELIGIBLE_POSITIONS:
        mandatory = replacement_ranks[position]
        players = (
            df[df["position"] == position]
            .sort_values("projected_points", ascending=False)
            .copy()
        )
        flex_candidates.append(players.iloc[mandatory:])

    if flex_slots > 0 and flex_candidates:
        candidate_pool = pd.concat(flex_candidates, ignore_index=True)
        selected = (
            candidate_pool
            .sort_values("projected_points", ascending=False)
            .head(flex_slots)
        )

        for position in FLEX_ELIGIBLE_POSITIONS:
            replacement_ranks[position] += int(
                (selected["position"] == position).sum()
            )

    return replacement_ranks


def calculate_vorp(
    df: pd.DataFrame,
    league_settings,
):

    df = df.copy()
    replacement_ranks = calculate_replacement_ranks(
        df,
        league_settings,
    )

    df["position_rank"] = 0
    df["vorp"] = 0.0
    df["replacement_points"] = 0.0

    for position, replacement_rank in replacement_ranks.items():

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
