import numpy as np
import pandas as pd

from fantasy_draft_model.config import load_league_settings
from fantasy_draft_model.models.player_profiles import build_player_profiles
from fantasy_draft_model.models.projections import add_custom_fantasy_scoring
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
from fantasy_draft_model.final_snapshot import audit_depth_chart
from fantasy_draft_model.integrations.depth_chart_loader import load_depth_charts


# ============================================================
# EDGEIQ 2026 PROJECTION ENGINE
# ============================================================

PROJECTED_GAMES = 17
CURRENT_INJURY_PROJECTION_PENALTY_CAP = 0.12
VETERAN_ROLE_PRIOR_GAMES = 17.0

TEAM_ALIASES = {
    "ARZ": "ARI",
    "AZ": "ARI",
    "JAC": "JAX",
    "LA": "LAR",
    "OAK": "LV",
    "SD": "LAC",
    "STL": "LAR",
}

MANUAL_PLAYER_ADJUSTMENTS = {
    # "Player Name": 1.05,
}

TARGET_REGRESSION = {
    # "Ja'Marr Chase": 1.05,
}


def attach_current_depth_roles(df, *, depth=None):
    """Attach canonical current depth evidence before projections are built."""
    current_depth = load_depth_charts() if depth is None else depth
    _, enriched = audit_depth_chart(df, current_depth)
    return enriched


def exclude_verified_fullbacks_from_fantasy_pool(df):
    """Exclude players whose verified current depth position is fullback.

    The roster source may label a fullback as RB or TE, but EdgeIQ's
    draftable positions intentionally exclude FB. A verified FB designation
    is authoritative only for that incompatibility; KR/PR and other
    special-teams labels do not affect eligibility.
    """
    result = df.copy()
    if "is_fantasy_draftable" not in result.columns:
        return result
    source_position = result.get(
        "depth_source_position", pd.Series("", index=result.index)
    ).fillna("").astype(str).str.strip().str.upper()
    match_method = result.get(
        "depth_match_method", pd.Series("", index=result.index)
    ).fillna("").astype(str).str.strip()
    position_mismatch = result.get(
        "depth_position_mismatch", pd.Series(False, index=result.index)
    ).fillna(False).astype(bool)
    verified_fullback = source_position.eq("FB") & (
        match_method.ne("") | position_mismatch
    )
    result["verified_fullback_excluded"] = verified_fullback
    result.loc[verified_fullback, "is_fantasy_draftable"] = False
    return result


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


def _normalized_team(series):
    values = series.fillna("").astype(str).str.strip().str.upper()
    return values.replace(TEAM_ALIASES)


def add_veteran_transition_baseline(df):
    """Regress verified team changers toward stable current-role peers.

    Prior production remains the player-specific signal. The current-role
    median supplies an empirical prior only when historical and current team
    evidence establishes a real transition and the depth match is verified.
    """
    result = df.copy()
    result["is_team_transition"] = False
    result["is_same_team_role_change"] = False
    result["transition_role_adjustment_applied"] = False
    result["role_baseline_ppg"] = np.nan
    historical_ppg = (
        result["custom_points_per_game"]
        if "custom_points_per_game" in result.columns
        else pd.Series(0.0, index=result.index)
    )
    result["transition_baseline_ppg"] = pd.to_numeric(
        historical_ppg,
        errors="coerce",
    ).fillna(0.0)
    result["transition_baseline_multiplier"] = 1.0

    required = {
        "position",
        "team",
        "prior_roster_team",
        "is_rookie",
        "games_played",
        "custom_points_per_game",
        "depth_role",
        "depth_match_method",
    }
    if not required.issubset(result.columns):
        return result

    current_team = _normalized_team(result["team"])
    prior_team = _normalized_team(result["prior_roster_team"])
    rookie = result["is_rookie"].fillna(False).astype(bool)
    games = pd.to_numeric(result["games_played"], errors="coerce").fillna(0.0)
    ppg = pd.to_numeric(
        result["custom_points_per_game"],
        errors="coerce",
    ).fillna(0.0)
    verified_depth = result["depth_match_method"].fillna("").astype(str).str.strip().ne("")
    valid_team_evidence = current_team.ne("") & prior_team.ne("")
    transition = valid_team_evidence & current_team.ne(prior_team)
    same_team_role_change = (
        result.get("depth_role_changed", pd.Series(False, index=result.index))
        .fillna(False)
        .astype(bool)
        & valid_team_evidence
        & current_team.eq(prior_team)
    )
    stable_reference = (
        ~rookie
        & verified_depth
        & valid_team_evidence
        & ~transition
        & ~same_team_role_change
        & games.gt(0)
    )

    role_medians = (
        result.loc[stable_reference]
        .assign(_ppg=ppg.loc[stable_reference])
        .groupby(["position", "depth_role"])["_ppg"]
        .median()
    )
    role_keys = pd.MultiIndex.from_arrays(
        [result["position"], result["depth_role"]],
    )
    result["role_baseline_ppg"] = role_medians.reindex(role_keys).to_numpy()

    eligible_role_evidence = (
        ~rookie
        & verified_depth
        & (transition | same_team_role_change)
        & games.gt(0)
        & result["role_baseline_ppg"].notna()
    )
    starter_role = result["depth_role"].eq("STARTER")
    transition_direction_supported = (
        (starter_role & result["role_baseline_ppg"].gt(ppg))
        | (~starter_role & result["role_baseline_ppg"].lt(ppg))
    )
    role_change_direction = result.get(
        "depth_role_change_direction",
        pd.Series("", index=result.index),
    ).fillna("").astype(str).str.upper()
    same_team_direction_supported = (
        (role_change_direction.eq("PROMOTED") & result["role_baseline_ppg"].gt(ppg))
        | (role_change_direction.eq("DEMOTED") & result["role_baseline_ppg"].lt(ppg))
    )
    direction_supported = (
        (transition & transition_direction_supported)
        | (same_team_role_change & same_team_direction_supported)
    )
    eligible = eligible_role_evidence & direction_supported
    history_weight = games / (games + VETERAN_ROLE_PRIOR_GAMES)
    transition_ppg = (
        ppg * history_weight
        + result["role_baseline_ppg"] * (1.0 - history_weight)
    )
    result.loc[eligible_role_evidence & transition, "is_team_transition"] = True
    result.loc[eligible_role_evidence & same_team_role_change, "is_same_team_role_change"] = True
    result.loc[eligible, "transition_role_adjustment_applied"] = True
    result.loc[eligible, "transition_baseline_ppg"] = transition_ppg.loc[eligible]
    nonzero = eligible & ppg.gt(0)
    result.loc[nonzero, "transition_baseline_multiplier"] = (
        result.loc[nonzero, "transition_baseline_ppg"] / ppg.loc[nonzero]
    )
    return result


def add_veteran_rb_workload_projection(df, league_settings):
    """Translate verified veteran RB role changes into explicit workload.

    Workload comes from a conservative blend of the player's demonstrated
    rates and stable veterans currently occupying the same verified role.
    Stable players are reference observations only and are never adjusted.
    """

    result = df.copy()
    projected_columns = [
        "projected_games", "projected_carries_per_game",
        "projected_targets_per_game", "projected_carries",
        "projected_targets", "projected_receptions",
        "projected_rushing_yards", "projected_receiving_yards",
        "projected_rushing_tds", "projected_receiving_tds",
        "projected_touches_per_game", "projected_workload_fantasy_points",
        "projected_workload_scoring_check", "rb_role_cohort_size",
        "rb_role_carries_pg_median", "rb_role_carries_pg_p25",
        "rb_role_carries_pg_p75", "rb_role_targets_pg_median",
        "rb_role_targets_pg_p25", "rb_role_targets_pg_p75",
        "rb_role_touches_pg_median", "rb_role_touches_pg_p25",
        "rb_role_touches_pg_p75",
    ]
    result["rb_workload_translation_applied"] = False
    for column in projected_columns:
        result[column] = np.nan

    required = {
        "position", "team", "prior_roster_team", "is_rookie",
        "games_played", "depth_role", "depth_match_method", "carries",
        "targets", "receptions", "rushing_yards", "receiving_yards",
        "rushing_tds", "receiving_tds",
        "transition_role_adjustment_applied",
    }
    if not required.issubset(result.columns):
        return result

    games = pd.to_numeric(result["games_played"], errors="coerce").fillna(0.0)
    current_team = _normalized_team(result["team"])
    prior_team = _normalized_team(result["prior_roster_team"])
    verified = result["depth_match_method"].fillna("").astype(str).str.strip().ne("")
    rookie = result["is_rookie"].fillna(False).astype(bool)
    transitioned = current_team.ne(prior_team) | result.get(
        "is_same_team_role_change", pd.Series(False, index=result.index)
    ).fillna(False).astype(bool)
    eligible = (
        result["position"].eq("RB") & ~rookie & verified & games.gt(0)
        & transitioned
        & result["transition_role_adjustment_applied"].fillna(False).astype(bool)
    )

    stable = (
        result["position"].eq("RB") & ~rookie & verified & games.gt(0)
        & current_team.eq(prior_team)
        & ~result.get("is_same_team_role_change", pd.Series(False, index=result.index))
        .fillna(False).astype(bool)
    )

    numeric = lambda column: pd.to_numeric(
        result.get(column, pd.Series(0.0, index=result.index)), errors="coerce"
    ).fillna(0.0)
    carries = numeric("carries")
    targets = numeric("targets")
    receptions = numeric("receptions")
    rush_yards = numeric("rushing_yards")
    rec_yards = numeric("receiving_yards")
    rush_tds = numeric("rushing_tds")
    rec_tds = numeric("receiving_tds")

    rate_frame = pd.DataFrame(index=result.index)
    rate_frame["carries_pg"] = carries / games.replace(0.0, np.nan)
    rate_frame["targets_pg"] = targets / games.replace(0.0, np.nan)
    rate_frame["touches_pg"] = (carries + receptions) / games.replace(0.0, np.nan)
    rate_frame["catch_rate"] = receptions / targets.replace(0.0, np.nan)
    rate_frame["yards_per_carry"] = rush_yards / carries.replace(0.0, np.nan)
    rate_frame["yards_per_reception"] = rec_yards / receptions.replace(0.0, np.nan)
    rate_frame["rush_td_rate"] = rush_tds / carries.replace(0.0, np.nan)
    rate_frame["rec_td_rate"] = rec_tds / targets.replace(0.0, np.nan)

    event_columns = [
        "fumbles_lost", "two_point_conversions", "return_tds",
        "offensive_fumble_return_tds", "games_100_rush",
        "games_200_rush", "games_300_rush", "games_100_receive",
        "games_200_receive", "games_300_receive", "plays_40_rush",
        "plays_40_rush_td", "plays_40_reception",
        "plays_40_reception_td",
    ]
    for column in event_columns:
        rate_frame[f"{column}_pg"] = numeric(column) / games.replace(0.0, np.nan)

    def blended_rate(index, cohort, column, lower_q=0.25, upper_q=0.75):
        values = rate_frame.loc[cohort, column].replace([np.inf, -np.inf], np.nan).dropna()
        if values.empty:
            return np.nan
        prior = float(values.median())
        player = rate_frame.at[index, column]
        if not np.isfinite(player):
            player = prior
        history_weight = float(games.at[index] / (games.at[index] + VETERAN_ROLE_PRIOR_GAMES))
        blended = float(player) * history_weight + prior * (1.0 - history_weight)
        return float(np.clip(blended, values.quantile(lower_q), values.quantile(upper_q)))

    for index in result.index[eligible]:
        role = result.at[index, "depth_role"]
        cohort = stable & result["depth_role"].eq(role)
        cohort_size = int(cohort.sum())
        if cohort_size < 4:
            continue

        projected_games = float(PROJECTED_GAMES)
        carries_pg = blended_rate(index, cohort, "carries_pg")
        targets_pg = blended_rate(index, cohort, "targets_pg")
        catch_rate = blended_rate(index, cohort, "catch_rate", 0.10, 0.90)
        ypc = blended_rate(index, cohort, "yards_per_carry", 0.10, 0.90)
        ypr = blended_rate(index, cohort, "yards_per_reception", 0.10, 0.90)
        rush_td_rate = blended_rate(index, cohort, "rush_td_rate", 0.10, 0.90)
        rec_td_rate = blended_rate(index, cohort, "rec_td_rate", 0.10, 0.90)
        rates = [carries_pg, targets_pg, catch_rate, ypc, ypr, rush_td_rate, rec_td_rate]
        if not all(np.isfinite(value) for value in rates):
            continue

        projected_carries = carries_pg * projected_games
        projected_targets = targets_pg * projected_games
        projected_receptions = projected_targets * catch_rate
        projected_stats = pd.DataFrame([{
            "games_played": projected_games,
            "carries": projected_carries,
            "targets": projected_targets,
            "receptions": projected_receptions,
            "rushing_yards": projected_carries * ypc,
            "receiving_yards": projected_receptions * ypr,
            "rushing_tds": projected_carries * rush_td_rate,
            "receiving_tds": projected_targets * rec_td_rate,
        }])
        for column in event_columns:
            projected_stats[column] = blended_rate(
                index, cohort, f"{column}_pg", 0.10, 0.90
            ) * projected_games
        scored = add_custom_fantasy_scoring(projected_stats, league_settings)
        workload_points = float(scored.at[0, "custom_fantasy_points"])

        cohort_carries = rate_frame.loc[cohort, "carries_pg"].dropna()
        cohort_targets = rate_frame.loc[cohort, "targets_pg"].dropna()
        cohort_touches = rate_frame.loc[cohort, "touches_pg"].dropna()
        values = {
            "projected_games": projected_games,
            "projected_carries_per_game": carries_pg,
            "projected_targets_per_game": targets_pg,
            "projected_carries": projected_carries,
            "projected_targets": projected_targets,
            "projected_receptions": projected_receptions,
            "projected_rushing_yards": float(projected_stats.at[0, "rushing_yards"]),
            "projected_receiving_yards": float(projected_stats.at[0, "receiving_yards"]),
            "projected_rushing_tds": float(projected_stats.at[0, "rushing_tds"]),
            "projected_receiving_tds": float(projected_stats.at[0, "receiving_tds"]),
            "projected_touches_per_game": carries_pg + projected_receptions / projected_games,
            "projected_workload_fantasy_points": workload_points,
            "projected_workload_scoring_check": workload_points,
            "rb_role_cohort_size": cohort_size,
            "rb_role_carries_pg_median": float(cohort_carries.median()),
            "rb_role_carries_pg_p25": float(cohort_carries.quantile(0.25)),
            "rb_role_carries_pg_p75": float(cohort_carries.quantile(0.75)),
            "rb_role_targets_pg_median": float(cohort_targets.median()),
            "rb_role_targets_pg_p25": float(cohort_targets.quantile(0.25)),
            "rb_role_targets_pg_p75": float(cohort_targets.quantile(0.75)),
            "rb_role_touches_pg_median": float(cohort_touches.median()),
            "rb_role_touches_pg_p25": float(cohort_touches.quantile(0.25)),
            "rb_role_touches_pg_p75": float(cohort_touches.quantile(0.75)),
        }
        result.at[index, "rb_workload_translation_applied"] = True
        for column, value in values.items():
            result.at[index, column] = value

    return result


def add_role_workload_consistency(df):
    """Apply verified-depth workload ceilings without creating opportunity.

    Historical rates remain the player signal.  This only prevents a verified
    lower-depth role from retaining a workload far above comparable current
    roles; starters and unverified depth records are deliberately untouched.
    """
    result = df.copy()
    result["role_workload_multiplier"] = 1.0
    result["role_workload_cap"] = np.nan
    required = {"position", "depth_role", "depth_match_method", "projected_points"}
    if not required.issubset(result.columns):
        return result
    verified = result["depth_match_method"].fillna("").astype(str).str.strip().ne("")
    roles = result["depth_role"].fillna("").astype(str).str.upper()
    games = pd.to_numeric(result.get("games_played", pd.Series(1.0, index=result.index)), errors="coerce").replace(0, np.nan)
    carries_pg = pd.to_numeric(result.get("carries_per_game", pd.Series(0.0, index=result.index)), errors="coerce").fillna(0)
    targets_pg = pd.to_numeric(result.get("targets_per_game", pd.Series(0.0, index=result.index)), errors="coerce").fillna(0)
    workload = targets_pg.copy()
    rb = result["position"].eq("RB")
    workload.loc[rb] = carries_pg.loc[rb] + targets_pg.loc[rb]
    result["role_workload_metric"] = workload
    rookie = result.get(
        "is_rookie", pd.Series(False, index=result.index)
    ).fillna(False).astype(bool)
    current_rank = pd.to_numeric(
        result.get("depth_pos_rank", pd.Series(np.nan, index=result.index)),
        errors="coerce",
    )
    prior_rank = pd.to_numeric(
        result.get("prior_depth_pos_rank", pd.Series(np.nan, index=result.index)),
        errors="coerce",
    )
    direction = result.get(
        "depth_role_change_direction", pd.Series("", index=result.index)
    ).fillna("").astype(str).str.upper()
    demoted = direction.eq("DEMOTED") & current_rank.gt(prior_rank)
    for position in ("RB", "WR", "TE"):
        for role in ("BACKUP", "DEPTH", "DEEP_DEPTH"):
            peer = verified & result["position"].eq(position) & roles.eq(role) & games.notna()
            values = workload.loc[peer]
            if len(values) < 2:
                continue
            cap = float(values.quantile(0.90))
            affected = (
                verified
                & ~rookie
                & games.notna()
                & demoted
                & result["position"].eq(position)
                & roles.eq(role)
                & workload.gt(cap)
            )
            result.loc[affected, "role_workload_cap"] = cap
            result.loc[affected, "role_workload_multiplier"] = cap / workload.loc[affected]
    result["projected_points"] = (
        pd.to_numeric(result["projected_points"], errors="coerce").fillna(0)
        * result["role_workload_multiplier"]
    )
    return result


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
        df["custom_points_per_game"]
        * PROJECTED_GAMES
        * df.get("transition_baseline_multiplier", 1.0)
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

    workload_mask = df.get(
        "rb_workload_translation_applied",
        pd.Series(False, index=df.index),
    ).fillna(False).astype(bool)
    if workload_mask.any():
        df.loc[workload_mask, "baseline_projection"] = df.loc[
            workload_mask, "projected_workload_fantasy_points"
        ]
        df.loc[workload_mask, "projected_points"] = (
            df.loc[workload_mask, "projected_workload_fantasy_points"]
            * df.loc[workload_mask, "injury_multiplier"]
            * df.loc[workload_mask, "manual_adjustment"]
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

    df = attach_current_depth_roles(df)
    df = exclude_verified_fullbacks_from_fantasy_pool(df)

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
    df = add_veteran_transition_baseline(df)
    df = add_veteran_rb_workload_projection(df, league_settings)
    df = add_target_regression(df)
    df = add_manual_adjustments(df)
    df = calculate_projection(df)
    df = add_role_workload_consistency(df)

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
