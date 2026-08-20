"""Diagnostics for live EdgeIQ ranking components."""

import pandas as pd

from fantasy_draft_model.draft_assistant import build_draft_assistant_from_rankings
from fantasy_draft_model.live_war_room import load_war_room_state
from fantasy_draft_model.rankings import build_draft_rankings
from fantasy_draft_model.ui.draft_war_room import build_live_draft_context


PLAYERS = [
    "Chris Olave",
    "Ja'Marr Chase",
    "Amon-Ra St. Brown",
    "Drake London",
    "George Pickens",
]

COLUMNS = [
    "player_name_clean",
    "position",
    "team",
    "draft_rank",
    "position_rank_label",
    "tier",
    "tier_status",
    "projected_points",
    "replacement_points",
    "vorp",
    "vorp_score",
    "projection_score",
    "edgescore",
    "projection_confidence",
    "injury_risk_score",
    "draft_score",
    "pressure_score",
    "brain_score",
    "brain_recommendation",
    "brain_reasons",
    "brain_warnings",
]

BRAIN_SCARCITY_BY_TIER_STATUS = {
    "ELITE SOLO TIER": 100.0,
    "SMALL TIER": 85.0,
    "LIMITED TIER": 60.0,
    "DEPTH AVAILABLE": 25.0,
}


def _numeric_column(df, column):
    if column not in df.columns:
        return pd.Series(0.0, index=df.index, dtype=float)
    return pd.to_numeric(df[column], errors="coerce").fillna(0.0)


def build_te_ranking_audit(board):
    """Expose how TE VORP and scarcity flow into Brain through multiple paths.

    This is diagnostic only. It does not change any rankings or weights.
    """
    if "position" not in board.columns:
        return board.iloc[0:0].copy()

    audit = board.loc[
        board["position"].astype(str).str.strip().str.upper() == "TE"
    ].copy()

    if audit.empty:
        return audit

    vorp_score = _numeric_column(audit, "vorp_score")
    vorp_pressure = _numeric_column(audit, "vorp_pressure")
    tier_scarcity_score = _numeric_column(audit, "tier_scarcity_score")
    tier_pressure = _numeric_column(audit, "tier_pressure")

    direct_scarcity = (
        audit.get("tier_status", pd.Series("", index=audit.index))
        .map(BRAIN_SCARCITY_BY_TIER_STATUS)
        .fillna(25.0)
        .astype(float)
    )

    # Draft Brain direct VORP path: normalized VORP * 10%.
    audit["brain_vorp_direct"] = vorp_score * 0.10
    # Draft Score is 35% VORP, then Draft Brain is 20% Draft Score.
    audit["brain_vorp_via_draft_score"] = vorp_score * 0.35 * 0.20
    # Pressure is 20% VORP pressure, then Draft Brain is 20% Pressure.
    audit["brain_vorp_via_pressure"] = vorp_pressure * 0.20 * 0.20
    audit["brain_vorp_total"] = (
        audit["brain_vorp_direct"]
        + audit["brain_vorp_via_draft_score"]
        + audit["brain_vorp_via_pressure"]
    )

    # Draft Brain direct scarcity path: tier scarcity * 15%.
    audit["brain_scarcity_direct"] = direct_scarcity * 0.15
    # Draft Score is 10% tier scarcity, then Draft Brain is 20% Draft Score.
    audit["brain_scarcity_via_draft_score"] = tier_scarcity_score * 0.10 * 0.20
    # Pressure is 30% tier pressure, then Draft Brain is 20% Pressure.
    audit["brain_scarcity_via_pressure"] = tier_pressure * 0.30 * 0.20
    audit["brain_scarcity_total"] = (
        audit["brain_scarcity_direct"]
        + audit["brain_scarcity_via_draft_score"]
        + audit["brain_scarcity_via_pressure"]
    )

    audit["brain_vorp_and_scarcity_total"] = (
        audit["brain_vorp_total"] + audit["brain_scarcity_total"]
    )

    contribution_columns = [
        "brain_vorp_direct",
        "brain_vorp_via_draft_score",
        "brain_vorp_via_pressure",
        "brain_vorp_total",
        "brain_scarcity_direct",
        "brain_scarcity_via_draft_score",
        "brain_scarcity_via_pressure",
        "brain_scarcity_total",
        "brain_vorp_and_scarcity_total",
    ]
    audit[contribution_columns] = audit[contribution_columns].round(2)

    if "brain_score" in audit.columns:
        audit = audit.sort_values("brain_score", ascending=False)

    return audit.reset_index(drop=True)


def main():
    state = load_war_room_state()
    context = build_live_draft_context(state)
    rankings = build_draft_rankings(state["league_key"])
    board = build_draft_assistant_from_rankings(rankings, draft_context=context)

    mask = board["player_name_clean"].isin(PLAYERS)
    audit = board.loc[mask].copy()
    columns = [column for column in COLUMNS if column in audit.columns]

    print("\n============================================")
    print("EDGEIQ LIVE WAR ROOM RANKING AUDIT")
    print("============================================")
    print(f"Current pick: {context.get('current_pick')}")
    print(f"Picks until BLKWDW'S: {context.get('picks_until_user')}")
    print("\nPlayers sorted by LIVE brain_score:\n")

    if audit.empty:
        print("No requested players were found in the current board.")
    else:
        audit = audit.sort_values("brain_score", ascending=False)
        print(audit[columns].round(2).to_string(index=False))

    te_audit = build_te_ranking_audit(board)
    te_columns = [
        "player_name_clean",
        "position_rank_label",
        "draft_rank",
        "projected_points",
        "replacement_points",
        "vorp",
        "vorp_score",
        "tier_status",
        "tier_scarcity_score",
        "brain_vorp_total",
        "brain_scarcity_total",
        "brain_vorp_and_scarcity_total",
        "draft_score",
        "pressure_score",
        "brain_score",
        "brain_recommendation",
    ]
    te_columns = [column for column in te_columns if column in te_audit.columns]

    print("\n============================================")
    print("EDGEIQ TE MULTIPATH VALUE AUDIT")
    print("============================================\n")

    if te_audit.empty:
        print("No tight ends were found in the current board.")
    else:
        print(te_audit[te_columns].head(12).round(2).to_string(index=False))


if __name__ == "__main__":
    main()
