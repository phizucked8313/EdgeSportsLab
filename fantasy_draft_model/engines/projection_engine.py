import numpy as np
import pandas as pd

from fantasy_draft_model.config import load_league_settings
from fantasy_draft_model.models.player_profiles import build_player_profiles
from fantasy_draft_model.engines.edgescore_engine import calculate_edgescore
from fantasy_draft_model.engines.vorp_engine import calculate_vorp
from fantasy_draft_model.engines.rushing_usage_engine import (
    add_rushing_usage_scores,
    add_qb_contact_exposure,
)
from fantasy_draft_model.engines.injury_risk import (
    add_injury_scores,
    injury_risk_label,
)
from fantasy_draft_model.engines.tier_engine import calculate_tiers
from fantasy_draft_model.integrations.current_injury_normalizer import (
    load_normalized_current_injuries,
    attach_current_injury_state,
)
from fantasy_draft_model.integrations.current_injury_overrides import (
    attach_current_injury_overrides,
)
from fantasy_draft_model.models.team_injury_impact_engine import (
    add_team_injury_impact,
)
from fantasy_draft_model.engines.injury_ripple_engine import (
    build_team_offensive_ripple,
    add_fantasy_ripple_scores,
    add_projection_multipliers,
    add_player_opportunity_ripple,
)
from fantasy_draft_model.engines.talent_engine import (
    add_rookie_projection_components,
    add_rookie_baseline_projection,
)


# ============================================================
# EDGEIQ 2026 PROJECTION ENGINE
# ============================================================

PROJECTED_GAMES = 17
CURRENT_INJURY_PROJECTION_PENALTY_CAP = 0.12

MANUAL_PLAYER_ADJUSTMENTS = {
    # "Player Name": 1.05,
}

TARGET_REGRESSION = {
    # "Ja'Marr Chase": 1.05,
}


def percentile_score(df, column, position):
    """Convert a stat into a 0-100 within-position percentile score."""
    mask = df["position"] == position
    scores = pd.Series(0.0, index=df.index)

    if column not in df.columns:
        return scores

    scores.loc[mask] = (
        df.loc[mask, column]
        .fillna(0)
        .rank(pct=True)
        * 100
    )
    return scores


def add_per_game_metrics(df):
    df = df.copy()
    games = df["games_played"].replace(0, np.nan)

    df["targets_per_game"] = (df["targets"] / games).fillna(0)
    df["carries_per_game"] = (df["carries"] / games).fillna(0)
    df["pass_attempts_per_game"] = (df["attempts"] / games).fillna(0)
    return df


def calculate_opportunity_score(df):
    """Create a position-specific opportunity score."""
    df = df.copy()
    df["opportunity_score"] = 0.0

    qb_pass = percentile_score(df, "pass_attempts_per_game", "QB")
    qb_rush = percentile_score(df, "carries_per_game", "QB")
    qb_mask = df["position"] == "QB"
    df.loc[qb_mask, "opportunity_score"] = (
        qb_pass[qb_mask] * 0.70
        + qb_rush[qb_mask] * 0.30
    )

    rb_carries = percentile_score(df, "carries_per_game", "RB")
    rb_targets = percentile_score(df, "targets_per_game", "RB")
    rb_share = percentile_score(df, "target_share", "RB")
    rb_mask = df["position"] == "RB"
    df.loc[rb_mask, "opportunity_score"] = (
        rb_carries[rb_mask] * 0.60
        + rb_targets[rb_mask] * 0.25
        + rb_share[rb_mask] * 0.15
    )

    wr_targets = percentile_score(df, "targets_per_game", "WR")
    wr_share = percentile_score(df, "target_share", "WR")
    wr_air_share = percentile_score(df, "air_yards_share", "WR")
    wr_wopr = percentile_score(df, "wopr", "WR")
    wr_mask = df["position"] == "WR"
    df.loc[wr_mask, "opportunity_score"] = (
        wr_targets[wr_mask] * 0.30
        + wr_share[wr_mask] * 0.30
        + wr_air_share[wr_mask] * 0.20
        + wr_wopr[wr_mask] * 0.20
    )

    te_targets = percentile_score(df, "targets_per_game", "TE")
    te_share = percentile_score(df, "target_share", "TE")
    te_air_share = percentile_score(df, "air_yards_share", "TE")
    te_wopr = percentile_score(df, "wopr", "TE")
    te_mask = df["position"] == "TE"
    df.loc[te_mask, "opportunity_score"] = (
        te_targets[te_mask] * 0.35
        + te_share[te_mask] * 0.30
        + te_air_share[te_mask] * 0.15
        + te_wopr[te_mask] * 0.20
    )

    return df


def add_target_regression(df):
    df = df.copy()
    df["target_regression_factor"] = 1.00

    for player_name, factor in TARGET_REGRESSION.items():
        mask = (
            (df["player_name_clean"] == player_name)
            & (df["position"] == "WR")
        )
        df.loc[mask, "target_regression_factor"] = factor

    return df


def add_manual_adjustments(df):
    df = df.copy()
    df["manual_adjustment"] = 1.00

    for player_name, factor in MANUAL_PLAYER_ADJUSTMENTS.items():
        df.loc[
            df["player_name_clean"] == player_name,
            "manual_adjustment",
        ] = factor

    return df


def neutralize_positive_ripple_for_current_injuries(df):
    """Prevent currently injured players from benefiting from positive team ripple."""
    result = df.copy()

    if (
        "is_currently_injured" not in result.columns
        or "injury_ripple_multiplier" not in result.columns
    ):
        return result

    injured = result["is_currently_injured"].fillna(False).astype(bool)
    positive_ripple = pd.to_numeric(
        result["injury_ripple_multiplier"],
        errors="coerce",
    ).fillna(1.0) > 1.0

    result.loc[
        injured & positive_ripple,
        "injury_ripple_multiplier",
    ] = 1.0

    return result


def apply_current_injury_projection_penalty(df):
    """Apply status severity plus verified missed-time availability penalties."""
    result = df.copy()
    result["pre_current_injury_projected_points"] = pd.to_numeric(
        result["projected_points"],
        errors="coerce",
    )
    result["current_injury_projection_penalty"] = 0.0
    result["current_injury_timeline_penalty"] = 0.0
    result["current_injury_projection_multiplier"] = 1.0

    injured = (
        result["is_currently_injured"].fillna(False).astype(bool)
        if "is_currently_injured" in result.columns
        else pd.Series(False, index=result.index)
    )
    stale = (
        result["current_injury_is_stale"].fillna(False).astype(bool)
        if "current_injury_is_stale" in result.columns
        else pd.Series(False, index=result.index)
    )
    research_override = (
        result["current_injury_research_override"].fillna(False).astype(bool)
        if "current_injury_research_override" in result.columns
        else pd.Series(False, index=result.index)
    )
    severity = (
        pd.to_numeric(
            result["current_injury_severity"],
            errors="coerce",
        ).fillna(0.0).clip(lower=0.0)
        if "current_injury_severity" in result.columns
        else pd.Series(0.0, index=result.index)
    )
    expected_games_missed = (
        pd.to_numeric(
            result["current_injury_expected_games_missed"],
            errors="coerce",
        ).fillna(0.0).clip(lower=0.0, upper=PROJECTED_GAMES)
        if "current_injury_expected_games_missed" in result.columns
        else pd.Series(0.0, index=result.index)
    )
    season_ending = (
        result["current_injury_season_ending"].fillna(False).astype(bool)
        if "current_injury_season_ending" in result.columns
        else pd.Series(False, index=result.index)
    )

    eligible = injured & (~stale | research_override)
    severity_penalty = (
        severity * CURRENT_INJURY_PROJECTION_PENALTY_CAP
    ).clip(lower=0.0, upper=CURRENT_INJURY_PROJECTION_PENALTY_CAP)
    timeline_penalty = (
        expected_games_missed / float(PROJECTED_GAMES)
    ).clip(lower=0.0, upper=1.0)
    timeline_penalty = timeline_penalty.mask(season_ending, 1.0)
    result["current_injury_timeline_penalty"] = timeline_penalty

    final_penalty = pd.concat(
        [severity_penalty.where(eligible, 0.0), timeline_penalty],
        axis=1,
    ).max(axis=1)
    result["current_injury_projection_penalty"] = final_penalty
    result["current_injury_projection_multiplier"] = (
        1.0 - result["current_injury_projection_penalty"]
    )
    result["projected_points"] = (
        result["pre_current_injury_projected_points"]
        * result["current_injury_projection_multiplier"]
    )

    return result


def calculate_projection(df):
    df = df.copy()

    df["baseline_projection"] = (
        df["custom_points_per_game"] * PROJECTED_GAMES
    )

    if (
        "is_rookie" in df.columns
        and "rookie_baseline_projection" in df.columns
    ):
        rookie_mask = df["is_rookie"] == True
        df.loc[rookie_mask, "baseline_projection"] = df.loc[
            rookie_mask,
            "rookie_baseline_projection",
        ]

    df["opportunity_multiplier"] = (
        0.90 + (df["opportunity_score"] / 100) * 0.20
    )

    df["target_multiplier"] = 1.00
    wr_mask = df["position"] == "WR"
    df.loc[wr_mask, "target_multiplier"] = (
        1
        + (
            df.loc[wr_mask, "target_regression_factor"] - 1
        ) * 0.40
    )

    df["injury_multiplier"] = (
        1 - (df["injury_risk_score"] / 100) * 0.10
    )

    df["projected_points"] = (
        df["baseline_projection"]
        * df["opportunity_multiplier"]
        * df["target_multiplier"]
        * df["injury_multiplier"]
        * df["manual_adjustment"]
    )

    return df


def calculate_floor_ceiling(df):
    """Calculate projection floor and ceiling with an injury-risk spread."""
    df = df.copy()
    risk_range = df["injury_risk_score"] / 100 * 0.10

    df["floor_projection"] = (
        df["projected_points"] * (0.85 - risk_range)
    )
    df["ceiling_projection"] = (
        df["projected_points"] * (1.15 + risk_range)
    )
    return df


def calculate_projection_confidence(df):
    df = df.copy()

    injury_penalty = df["injury_risk_score"] * 0.35
    sample_penalty = np.where(
        df["games_played"] >= 15,
        0,
        np.where(df["games_played"] >= 10, 7, 15),
    )

    df["projection_confidence"] = (
        100 - injury_penalty - sample_penalty
    ).clip(lower=25, upper=99)

    return df


def build_2026_projections(league_key):
    """Build EdgeIQ projections for one explicitly selected league."""
    print("\nBuilding EdgeIQ 2026 projections...")

    league_settings = load_league_settings(league_key)
    df = build_player_profiles(league_key)

    if "is_fantasy_draftable" in df.columns:
        df = df[
            df["is_fantasy_draftable"] == True
        ].copy()

    df = add_rookie_projection_components(df)
    df = add_rookie_baseline_projection(df)
    df = add_per_game_metrics(df)
    df = add_rushing_usage_scores(df)
    df = add_qb_contact_exposure(df)
    df = add_injury_scores(df)
    df["injury_risk_label"] = df["injury_risk_score"].apply(
        injury_risk_label
    )
    df = calculate_opportunity_score(df)
    df = add_target_regression(df)
    df = add_manual_adjustments(df)
    df = calculate_projection(df)

    current_injuries = load_normalized_current_injuries()
    df = attach_current_injury_state(df, current_injuries)
    df = attach_current_injury_overrides(df)
    current_injuries = add_team_injury_impact(current_injuries)
    df = add_player_opportunity_ripple(df, current_injuries)

    team_ripple = build_team_offensive_ripple(current_injuries)
    team_ripple = add_fantasy_ripple_scores(team_ripple)
    team_ripple = add_projection_multipliers(team_ripple)

    ripple_columns = [
        "team",
        "qb_ripple_multiplier",
        "rb_ripple_multiplier",
        "wr_ripple_multiplier",
        "te_ripple_multiplier",
    ]

    df = df.merge(
        team_ripple[ripple_columns],
        on="team",
        how="left",
    )

    df["pre_injury_projected_points"] = df["projected_points"]
    df["injury_ripple_multiplier"] = 1.0

    position_multiplier_map = {
        "QB": "qb_ripple_multiplier",
        "RB": "rb_ripple_multiplier",
        "WR": "wr_ripple_multiplier",
        "TE": "te_ripple_multiplier",
    }

    for position, multiplier_column in position_multiplier_map.items():
        mask = df["position"] == position
        df.loc[mask, "injury_ripple_multiplier"] = (
            df.loc[mask, multiplier_column].fillna(1.0)
        )

    df = neutralize_positive_ripple_for_current_injuries(df)

    df["projected_points"] = (
        df["projected_points"]
        * df["injury_ripple_multiplier"]
        * df["injury_opportunity_multiplier"]
    )
    df = apply_current_injury_projection_penalty(df)
    df["injury_projection_change"] = (
        df["projected_points"]
        - df["pre_injury_projected_points"]
    )

    df = calculate_floor_ceiling(df)
    df = calculate_projection_confidence(df)
    df = calculate_edgescore(df)
    df = calculate_vorp(df, league_settings)
    df = calculate_tiers(df)
    df = (
        df.sort_values("projected_points", ascending=False)
        .reset_index(drop=True)
    )
    return df


def main():
    df = build_2026_projections("drunk_sundays")

    columns = [
        "overall_rank",
        "player_name_clean",
        "position",
        "position_rank",
        "tier",
        "tier_size",
        "tier_remaining",
        "tier_scarcity_score",
        "tier_next_projection_drop",
        "tier_next_vorp_drop",
        "team",
        "games_played",
        "custom_points_per_game",
        "opportunity_score",
        "edgescore",
        "vorp",
        "durability_score",
        "injury_risk_score",
        "baseline_projection",
        "floor_projection",
        "projected_points",
        "ceiling_projection",
        "projection_confidence",
        "rushing_usage_score",
        "qb_contact_exposure",
    ]

    print("\n============================================")
    print("EDGEIQ 2026 PROJECTION ENGINE")
    print("============================================\n")
    print(
        df[columns]
        .head(50)
        .round(2)
        .to_string(index=False)
    )
    print(f"\nProjected players: {len(df):,}")


if __name__ == "__main__":
    main()
