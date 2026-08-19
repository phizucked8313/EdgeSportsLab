"""Historical long-play aggregation for league-specific scoring."""

from functools import reduce

import pandas as pd


LONG_PLAY_COUNTERS = [
    "plays_40_pass_completion",
    "plays_40_pass_td",
    "plays_40_rush",
    "plays_40_rush_td",
    "plays_40_reception",
    "plays_40_reception_td",
]


def aggregate_long_play_counts(pbp_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate 40+ yard offensive events by GSIS player ID."""

    long_plays = pbp_df.loc[
        pd.to_numeric(pbp_df["yards_gained"], errors="coerce").fillna(0) >= 40
    ].copy()

    passing = (
        long_plays[
            long_plays["passer_player_id"].notna()
            & long_plays["complete_pass"].fillna(0).eq(1)
        ]
        .groupby("passer_player_id", as_index=False)
        .agg(
            plays_40_pass_completion=("passer_player_id", "size"),
            plays_40_pass_td=("pass_touchdown", "sum"),
        )
        .rename(columns={"passer_player_id": "player_id"})
    )

    receiving = (
        long_plays[
            long_plays["receiver_player_id"].notna()
            & long_plays["complete_pass"].fillna(0).eq(1)
        ]
        .groupby("receiver_player_id", as_index=False)
        .agg(
            plays_40_reception=("receiver_player_id", "size"),
            plays_40_reception_td=("pass_touchdown", "sum"),
        )
        .rename(columns={"receiver_player_id": "player_id"})
    )

    rushing = (
        long_plays[long_plays["rusher_player_id"].notna()]
        .groupby("rusher_player_id", as_index=False)
        .agg(
            plays_40_rush=("rusher_player_id", "size"),
            plays_40_rush_td=("rush_touchdown", "sum"),
        )
        .rename(columns={"rusher_player_id": "player_id"})
    )

    result = reduce(
        lambda left, right: left.merge(right, on="player_id", how="outer"),
        [passing, receiving, rushing],
    )

    for column in LONG_PLAY_COUNTERS:
        if column not in result.columns:
            result[column] = 0

    result[LONG_PLAY_COUNTERS] = (
        result[LONG_PLAY_COUNTERS]
        .fillna(0)
        .astype(int)
    )

    return result[["player_id", *LONG_PLAY_COUNTERS]]
