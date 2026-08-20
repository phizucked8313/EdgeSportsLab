"""
EdgeIQ Draft Brain Engine
Version 1

Combines multiple EdgeIQ draft signals into
one recommendation and confidence score.
"""

import pandas as pd

from fantasy_draft_model.engines.run_detector_engine import (
    build_position_run_cache,
    get_position_run,
)
from fantasy_draft_model.engines.what_if_i_wait_engine import (
    analyze_wait,
    build_wait_report_cache,
)


def clamp(value, low=0, high=100):
    if pd.isna(value):
        return low

    try:
        value = float(value)
    except (TypeError, ValueError):
        return low

    return max(low, min(high, value))


def build_draft_brain_for_player(
    df: pd.DataFrame,
    player_row,
    draft_context,
    wait_report=None,
    position_run=None,
):
    """Build one final EdgeIQ draft recommendation for an available player."""
    pressure = float(player_row.get("pressure_score", 0))
    draft_score = float(player_row.get("draft_score", 0))
    edgescore = float(player_row.get("edgescore", 0))
    vorp = float(player_row.get("vorp", 0))
    confidence = float(player_row.get("projection_confidence", 0))
    injury_risk = float(player_row.get("injury_risk_score", 0))
    position = player_row.get("position", "")
    player_name = player_row.get("player_name_clean", "")

    picks_until_raw = draft_context.get("picks_until_user", 1)
    picks_until_next = 1 if picks_until_raw is None else max(1, int(picks_until_raw))

    if wait_report is None:
        wait_report = analyze_wait(
            df,
            player_name,
            picks_until_next=picks_until_next,
        )

    survival_score = float(wait_report.get("survival_score", 50))

    if position_run is None:
        position_run = get_position_run(
            df,
            position,
            recent_picks=8,
        )

    run_score = float(position_run.get("run_score", 0))
    run_label = position_run.get("run_label", "NORMAL")

    scarcity_score = clamp(player_row.get("tier_scarcity_score", 0.0))

    vorp_score = clamp(player_row.get("vorp_score", vorp))
    safety_score = clamp(100 - injury_risk)

    brain_score = (
        pressure * 0.20
        + draft_score * 0.20
        + edgescore * 0.15
        + confidence * 0.10
        + scarcity_score * 0.15
        + run_score * 0.05
        + vorp_score * 0.10
        + safety_score * 0.05
    )
    brain_score = round(clamp(brain_score), 1)

    reasons = []
    warnings = []

    if pressure >= 85:
        reasons.append("Very high draft pressure")

    tier = pd.to_numeric(player_row.get("tier"), errors="coerce")
    tier_remaining = pd.to_numeric(player_row.get("tier_remaining"), errors="coerce")
    if pd.notna(tier) and pd.notna(tier_remaining):
        tier_label = str(int(tier)) if float(tier).is_integer() else str(tier)
        if tier_remaining <= 1:
            reasons.append(
                f"Last player remaining in {position} Tier {tier_label}"
            )
        elif tier_remaining <= 2:
            reasons.append(
                f"Only {int(tier_remaining)} players remaining in "
                f"{position} Tier {tier_label}"
            )

    if vorp >= 75:
        reasons.append("Strong positional value over replacement")
    if edgescore >= 90:
        reasons.append("Elite EdgeIQ profile")
    if survival_score <= 25:
        reasons.append("Low chance of surviving until next pick")
    if run_label in ["RUN STARTING", "RUN ACTIVE"]:
        reasons.append(f"{position} run is {run_label.lower()}")

    if injury_risk >= 60:
        warnings.append("Elevated injury risk")
    elif injury_risk >= 40:
        warnings.append("Moderate injury concern")

    if wait_report.get("projection_drop", 0) >= 25:
        reasons.append("Large projection drop to next same-position option")

    if brain_score >= 90:
        recommendation = "SMASH PICK"
    elif brain_score >= 80:
        recommendation = "DRAFT NOW"
    elif brain_score >= 70:
        recommendation = "STRONG TARGET"
    elif brain_score >= 60:
        recommendation = "GOOD VALUE"
    elif brain_score >= 50:
        recommendation = "CONSIDER"
    else:
        recommendation = "WAIT"

    return {
        "player_name": player_name,
        "position": position,
        "brain_score": brain_score,
        "recommendation": recommendation,
        "pressure_score": pressure,
        "survival_score": survival_score,
        "run_label": run_label,
        "reasons": reasons,
        "warnings": warnings,
    }


def add_draft_brain(df: pd.DataFrame, draft_context):
    """Add Draft Brain output using one wait cache and one live run cache per rerun."""
    df = df.copy()
    picks_until_raw = draft_context.get("picks_until_user", 1)
    picks_until_next = 1 if picks_until_raw is None else max(1, int(picks_until_raw))

    wait_cache = build_wait_report_cache(
        df,
        picks_until_next=picks_until_next,
    )
    run_cache = build_position_run_cache(
        df,
        draft_context.get("drafted_picks", []),
        recent_picks=8,
    )

    reports = []
    for _, row in df.iterrows():
        player_name = row.get("player_name_clean", "")
        position = row.get("position", "")
        report = build_draft_brain_for_player(
            df,
            row,
            draft_context,
            wait_report=wait_cache.get(player_name, {}),
            position_run=run_cache.get(
                position,
                {
                    "position": position,
                    "position_picks": 0,
                    "run_score": 0,
                    "run_label": "NORMAL",
                },
            ),
        )
        reports.append(report)

    report_df = pd.DataFrame(reports, index=df.index)
    df["brain_score"] = report_df["brain_score"]
    df["brain_recommendation"] = report_df["recommendation"]
    df["brain_reasons"] = report_df["reasons"]
    df["brain_warnings"] = report_df["warnings"]
    return df


def main():
    print("EdgeIQ Draft Brain Engine ready.")


if __name__ == "__main__":
    main()
