import numpy as np
import pandas as pd


def percentile_score(
    df,
    column,
    position
):
    """
    Score a stat from 0-100 within position.
    """

    scores = pd.Series(
        0.0,
        index=df.index
    )

    mask = (
        df["position"] == position
    )

    if column not in df.columns:
        return scores

    scores.loc[mask] = (
        df.loc[
            mask,
            column
        ]
        .fillna(0)
        .rank(
            pct=True
        )
        * 100
    )

    return scores


def add_rushing_usage_scores(df):
    """
    Add position-specific rushing intelligence.

    QB:
    - carries per game
    - rushing yards per game
    - rushing TDs per game

    WR:
    - carries per game
    - rushing yards per game
    - rushing TDs per game

    RB:
    - retains rushing workload scoring
    """

    df = df.copy()

    games = (
        df["games_played"]
        .replace(
            0,
            np.nan
        )
    )

    df["carries_per_game"] = (
        df["carries"]
        / games
    ).fillna(0)

    df["rushing_yards_per_game"] = (
        df["rushing_yards"]
        / games
    ).fillna(0)

    df["rushing_tds_per_game"] = (
        df["rushing_tds"]
        / games
    ).fillna(0)

    df["rushing_usage_score"] = 0.0

    # QB
    qb_carries = percentile_score(
        df,
        "carries_per_game",
        "QB"
    )

    qb_yards = percentile_score(
        df,
        "rushing_yards_per_game",
        "QB"
    )

    qb_tds = percentile_score(
        df,
        "rushing_tds_per_game",
        "QB"
    )

    qb_mask = (
        df["position"] == "QB"
    )

    df.loc[
        qb_mask,
        "rushing_usage_score"
    ] = (
        qb_carries[qb_mask] * 0.35
        + qb_yards[qb_mask] * 0.35
        + qb_tds[qb_mask] * 0.30
    )

    # WR
    wr_carries = percentile_score(
        df,
        "carries_per_game",
        "WR"
    )

    wr_yards = percentile_score(
        df,
        "rushing_yards_per_game",
        "WR"
    )

    wr_tds = percentile_score(
        df,
        "rushing_tds_per_game",
        "WR"
    )

    wr_mask = (
        df["position"] == "WR"
    )

    df.loc[
        wr_mask,
        "rushing_usage_score"
    ] = (
        wr_carries[wr_mask] * 0.45
        + wr_yards[wr_mask] * 0.35
        + wr_tds[wr_mask] * 0.20
    )

    # RB
    rb_carries = percentile_score(
        df,
        "carries_per_game",
        "RB"
    )

    rb_yards = percentile_score(
        df,
        "rushing_yards_per_game",
        "RB"
    )

    rb_tds = percentile_score(
        df,
        "rushing_tds_per_game",
        "RB"
    )

    rb_mask = (
        df["position"] == "RB"
    )

    df.loc[
        rb_mask,
        "rushing_usage_score"
    ] = (
        rb_carries[rb_mask] * 0.50
        + rb_yards[rb_mask] * 0.30
        + rb_tds[rb_mask] * 0.20
    )

    return df


def add_qb_contact_exposure(df):
    """
    Version 1 QB contact exposure.

    Later we will improve this with:
    designed runs
    scrambles
    inside-5 carries
    inside-2 carries
    QB sneaks
    goal-line rush attempts
    """

    df = df.copy()

    df["qb_contact_exposure"] = 0.0

    qb_mask = (
        df["position"] == "QB"
    )

    df.loc[
        qb_mask,
        "qb_contact_exposure"
    ] = (
        df.loc[
            qb_mask,
            "rushing_usage_score"
        ]
    )

    return df


def main():

    print(
        "Rushing Usage Intelligence engine ready."
    )


if __name__ == "__main__":
    main()