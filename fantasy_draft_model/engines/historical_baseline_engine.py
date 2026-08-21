"""Conservative multi-year regression support for veteran projections.

This layer uses standard PPR points per game only as a relative persistence
signal. It never replaces EdgeIQ league scoring directly. Instead, it produces
a bounded multiplier that can temper one-season spikes or slumps in the custom
league-scoring baseline.
"""

import pandas as pd
import nflreadpy as nfl


HISTORICAL_SEASONS = (2023, 2024, 2025)
SEASON_WEIGHTS = {
    2023: 0.20,
    2024: 0.30,
    2025: 0.50,
}
MIN_GAMES_PER_SEASON = 4
RATIO_FLOOR = 0.80
RATIO_CEILING = 1.20
REGRESSION_BLEND = 0.50
MULTIPLIER_FLOOR = 0.90
MULTIPLIER_CEILING = 1.10


def build_multi_year_ppr_summary(
    stats_df: pd.DataFrame,
    *,
    season_weights=None,
    min_games_per_season: int = MIN_GAMES_PER_SEASON,
) -> pd.DataFrame:
    """Return a recency-weighted PPR/G summary by player.

    Only regular-season rows are used. Seasons with fewer than
    ``min_games_per_season`` appearances are excluded to avoid allowing tiny
    samples to dominate the persistence signal. Available season weights are
    renormalized for each player.
    """

    columns = ["player_id", "multi_year_ppr_pg", "multi_year_seasons_used"]
    if stats_df is None or stats_df.empty:
        return pd.DataFrame(columns=columns)

    required = {"player_id", "season", "fantasy_points_ppr"}
    if not required.issubset(stats_df.columns):
        return pd.DataFrame(columns=columns)

    weights = dict(SEASON_WEIGHTS if season_weights is None else season_weights)
    history = stats_df.copy()
    if "season_type" in history.columns:
        history = history.loc[history["season_type"].astype(str).eq("REG")].copy()

    history["season"] = pd.to_numeric(history["season"], errors="coerce")
    history["fantasy_points_ppr"] = pd.to_numeric(
        history["fantasy_points_ppr"],
        errors="coerce",
    ).fillna(0.0)
    history = history.loc[history["season"].isin(weights)].copy()
    if history.empty:
        return pd.DataFrame(columns=columns)

    game_counter = "week" if "week" in history.columns else "fantasy_points_ppr"
    season_summary = (
        history.groupby(["player_id", "season"], as_index=False)
        .agg(
            season_ppr_points=("fantasy_points_ppr", "sum"),
            season_games=(game_counter, "count"),
        )
    )
    season_summary = season_summary.loc[
        season_summary["season_games"] >= int(min_games_per_season)
    ].copy()
    if season_summary.empty:
        return pd.DataFrame(columns=columns)

    season_summary["season_ppr_pg"] = (
        season_summary["season_ppr_points"] / season_summary["season_games"]
    )
    season_summary["season_weight"] = (
        season_summary["season"].astype(int).map(weights).fillna(0.0)
    )

    rows = []
    for player_id, player_history in season_summary.groupby("player_id", sort=False):
        total_weight = float(player_history["season_weight"].sum())
        if total_weight <= 0:
            continue
        weighted_pg = float(
            (player_history["season_ppr_pg"] * player_history["season_weight"]).sum()
            / total_weight
        )
        rows.append(
            {
                "player_id": player_id,
                "multi_year_ppr_pg": weighted_pg,
                "multi_year_seasons_used": int(len(player_history)),
            }
        )

    return pd.DataFrame(rows, columns=columns)


def load_multi_year_ppr_summary() -> pd.DataFrame:
    """Load 2023-25 nflverse weekly stats and build the regression summary."""

    stats = nfl.load_player_stats(seasons=list(HISTORICAL_SEASONS))
    stats_df = stats.to_pandas()
    return build_multi_year_ppr_summary(stats_df)


def add_historical_regression_metadata(
    df: pd.DataFrame,
    multi_year_summary: pd.DataFrame,
    *,
    ratio_floor: float = RATIO_FLOOR,
    ratio_ceiling: float = RATIO_CEILING,
    blend: float = REGRESSION_BLEND,
    multiplier_floor: float = MULTIPLIER_FLOOR,
    multiplier_ceiling: float = MULTIPLIER_CEILING,
) -> pd.DataFrame:
    """Attach a bounded veteran historical-regression multiplier.

    The multiplier is neutral for rookies, players with fewer than two usable
    seasons, or players without a positive current-season PPR/G baseline.
    """

    result = df.copy()
    result["historical_regression_multiplier"] = 1.0
    result["multi_year_ppr_pg"] = pd.NA
    result["multi_year_seasons_used"] = 0
    result["historical_baseline_ratio"] = 1.0

    if multi_year_summary is None or multi_year_summary.empty or "player_id" not in result.columns:
        return result

    summary_columns = [
        column
        for column in ["player_id", "multi_year_ppr_pg", "multi_year_seasons_used"]
        if column in multi_year_summary.columns
    ]
    if len(summary_columns) < 3:
        return result

    result = result.drop(
        columns=["multi_year_ppr_pg", "multi_year_seasons_used"],
        errors="ignore",
    ).merge(
        multi_year_summary[summary_columns].drop_duplicates("player_id"),
        on="player_id",
        how="left",
        sort=False,
    )
    result["multi_year_seasons_used"] = pd.to_numeric(
        result["multi_year_seasons_used"],
        errors="coerce",
    ).fillna(0).astype(int)
    result["multi_year_ppr_pg"] = pd.to_numeric(
        result["multi_year_ppr_pg"],
        errors="coerce",
    )

    current_ppr = pd.to_numeric(
        result.get("ppr_points_per_game", pd.Series(0.0, index=result.index)),
        errors="coerce",
    ).fillna(0.0)
    rookie = (
        result.get("is_rookie", pd.Series(False, index=result.index))
        .fillna(False)
        .astype(bool)
    )
    eligible = (
        ~rookie
        & result["multi_year_seasons_used"].ge(2)
        & result["multi_year_ppr_pg"].notna()
        & current_ppr.gt(0.0)
    )

    raw_ratio = pd.Series(1.0, index=result.index, dtype=float)
    raw_ratio.loc[eligible] = (
        result.loc[eligible, "multi_year_ppr_pg"] / current_ppr.loc[eligible]
    )
    bounded_ratio = raw_ratio.clip(lower=float(ratio_floor), upper=float(ratio_ceiling))
    result["historical_baseline_ratio"] = bounded_ratio

    multiplier = 1.0 + float(blend) * (bounded_ratio - 1.0)
    multiplier = multiplier.clip(
        lower=float(multiplier_floor),
        upper=float(multiplier_ceiling),
    )
    multiplier.loc[~eligible] = 1.0
    result["historical_regression_multiplier"] = multiplier.round(4)
    return result
