"""
EdgeIQ What If I Wait Engine
Version 1

Evaluates whether a fantasy manager should draft
a player now or risk waiting until the next pick.
"""

import pandas as pd


HARD_TIER_SCARCITY_THRESHOLD = 80.0


def estimate_survival_score(pressure_score, picks_until_next):
    """Estimate a heuristic chance of surviving until the user's next pick."""
    pressure_score = max(0, min(100, pressure_score))
    picks_until_next = max(1, picks_until_next)
    base_survival = 100 - pressure_score
    pick_penalty = picks_until_next * 3
    survival_score = base_survival - pick_penalty
    return round(max(0, min(100, survival_score)), 1)


def get_fallback_players(df: pd.DataFrame, player_row, number_of_players=3):
    """Find the next best available players at the same position."""
    position = player_row["position"]
    draft_rank = player_row["draft_rank"]
    fallback = df[
        (df["position"] == position)
        & (df["draft_rank"] > draft_rank)
    ].copy()
    return fallback.sort_values("draft_rank").head(number_of_players)


def calculate_value_drop(player_row, fallback_df):
    """Measure what is lost if the user passes on the current player."""
    if fallback_df.empty:
        return {
            "next_player": None,
            "projection_drop": 0.0,
            "vorp_drop": 0.0,
            "draft_score_drop": 0.0,
        }

    next_player = fallback_df.iloc[0]
    return {
        "next_player": next_player["player_name_clean"],
        "projection_drop": round(
            player_row["projected_points"] - next_player["projected_points"], 1
        ),
        "vorp_drop": round(player_row["vorp"] - next_player["vorp"], 1),
        "draft_score_drop": round(
            player_row["draft_score"] - next_player["draft_score"], 1
        ),
    }


def create_wait_recommendation(player_row, survival_score, value_drop):
    """Create EdgeIQ's draft recommendation."""
    pressure = float(player_row.get("pressure_score", 0))
    tier = pd.to_numeric(player_row.get("tier"), errors="coerce")
    tier_remaining = pd.to_numeric(
        player_row.get("tier_remaining"),
        errors="coerce",
    )
    tier_scarcity_score = pd.to_numeric(
        player_row.get("tier_scarcity_score", 0.0),
        errors="coerce",
    )
    if pd.isna(tier_scarcity_score):
        tier_scarcity_score = 0.0
    projection_drop = value_drop["projection_drop"]
    vorp_drop = value_drop["vorp_drop"]

    if (
        pd.notna(tier)
        and tier_remaining == 1
        and tier_scarcity_score >= HARD_TIER_SCARCITY_THRESHOLD
    ):
        position = str(player_row.get("position", "")).strip().upper()
        tier_label = str(int(tier)) if float(tier).is_integer() else str(tier)
        return "DO NOT WAIT", f"Last player remaining in {position} Tier {tier_label}."
    if pressure >= 85 and survival_score <= 25:
        return "DO NOT WAIT", "High draft pressure and low chance of surviving."
    if vorp_drop >= 40:
        return "DO NOT WAIT", "Large positional value drop behind this player."
    if projection_drop >= 35:
        return "DO NOT WAIT", "Large projected fantasy-point drop to the next option."
    if survival_score <= 45:
        return "RISKY TO WAIT", "Player may not survive until your next selection."
    return "SAFE TO WAIT", "Comparable options may still be available later."


def build_wait_report_cache(df: pd.DataFrame, picks_until_next=10):
    """Build all player wait reports in one position-batched pass."""
    picks_until_next = max(1, int(picks_until_next))
    cache = {}

    for _, position_df in df.groupby("position", dropna=False, sort=False):
        ordered = position_df.sort_values("draft_rank").reset_index(drop=True)

        for index, player_row in ordered.iterrows():
            fallback_df = ordered.iloc[index + 1:index + 4]
            value_drop = calculate_value_drop(player_row, fallback_df)
            survival_score = estimate_survival_score(
                float(player_row.get("pressure_score", 0)),
                picks_until_next,
            )
            recommendation, reason = create_wait_recommendation(
                player_row,
                survival_score,
                value_drop,
            )
            fallback_names = fallback_df["player_name_clean"].tolist()
            tier_value = player_row.get("tier", 0)
            tier = int(tier_value) if pd.notna(tier_value) else 0
            player_name = player_row["player_name_clean"]

            cache[player_name] = {
                "player": player_name,
                "position": player_row.get("position"),
                "tier": tier,
                "pressure_score": float(player_row.get("pressure_score", 0)),
                "survival_score": survival_score,
                "picks_until_next": picks_until_next,
                "fallback_players": fallback_names,
                "next_player": value_drop["next_player"],
                "projection_drop": value_drop["projection_drop"],
                "vorp_drop": value_drop["vorp_drop"],
                "draft_score_drop": value_drop["draft_score_drop"],
                "recommendation": recommendation,
                "reason": reason,
            }

    return cache


def analyze_wait(df: pd.DataFrame, player_name, picks_until_next=10):
    """Analyze whether the user should draft a player now or wait."""
    player = df[
        df["player_name_clean"].str.lower() == player_name.lower()
    ]

    if player.empty:
        return {"error": f"Player not found: {player_name}"}

    player_row = player.iloc[0]
    survival_score = estimate_survival_score(
        player_row.get("pressure_score", 0),
        picks_until_next,
    )
    fallback_df = get_fallback_players(df, player_row)
    value_drop = calculate_value_drop(player_row, fallback_df)
    recommendation, reason = create_wait_recommendation(
        player_row,
        survival_score,
        value_drop,
    )
    fallback_names = fallback_df["player_name_clean"].tolist()
    tier_value = player_row.get("tier", 0)

    return {
        "player": player_name,
        "position": player_row["position"],
        "tier": int(tier_value) if pd.notna(tier_value) else 0,
        "pressure_score": float(player_row.get("pressure_score", 0)),
        "survival_score": survival_score,
        "picks_until_next": picks_until_next,
        "fallback_players": fallback_names,
        "next_player": value_drop["next_player"],
        "projection_drop": value_drop["projection_drop"],
        "vorp_drop": value_drop["vorp_drop"],
        "draft_score_drop": value_drop["draft_score_drop"],
        "recommendation": recommendation,
        "reason": reason,
    }
