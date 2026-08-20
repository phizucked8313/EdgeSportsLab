"""Diagnostics for live EdgeIQ ranking components."""

import pandas as pd

from fantasy_draft_model.config import load_league_settings
from fantasy_draft_model.draft_assistant import build_draft_assistant_from_rankings
from fantasy_draft_model.engines.vorp_engine import calculate_replacement_ranks
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

PROJECTION_AUDIT_PLAYERS = [
    "Trey McBride",
    "Brock Bowers",
    "Christian McCaffrey",
    "Bijan Robinson",
    "Jahmyr Gibbs",
    "Jonathan Taylor",
    "De'Von Achane",
    "Derrick Henry",
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

PROJECTION_AUDIT_COLUMNS = [
    "player_name_clean",
    "position",
    "draft_rank",
    "position_rank_label",
    "custom_points_per_game",
    "baseline_projection",
    "targets_per_game",
    "target_share",
    "opportunity_score",
    "opportunity_multiplier",
    "injury_multiplier",
    "projected_points",
    "projection_change_from_baseline",
    "tier",
    "tier_size",
    "tier_drop",
    "tier_status",
    "late_singleton_tier",
    "brain_score",
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


def build_projection_component_audit(board, player_names):
    """Show projection inputs and flag singleton tiers below Tier 1.

    This is diagnostic only and never mutates the supplied board.
    """
    if "player_name_clean" not in board.columns:
        return pd.DataFrame(columns=PROJECTION_AUDIT_COLUMNS)

    requested_names = [str(name) for name in player_names]
    requested_order = {name: index for index, name in enumerate(requested_names)}

    audit = board.loc[
        board["player_name_clean"].astype(str).isin(requested_names)
    ].copy()

    if audit.empty:
        return pd.DataFrame(columns=PROJECTION_AUDIT_COLUMNS)

    for column in PROJECTION_AUDIT_COLUMNS:
        if column not in audit.columns and column not in {
            "projection_change_from_baseline",
            "late_singleton_tier",
        }:
            audit[column] = pd.NA

    baseline = pd.to_numeric(audit["baseline_projection"], errors="coerce")
    projected = pd.to_numeric(audit["projected_points"], errors="coerce")
    audit["projection_change_from_baseline"] = (projected - baseline).round(2)

    tier = pd.to_numeric(audit["tier"], errors="coerce")
    tier_size = pd.to_numeric(audit["tier_size"], errors="coerce")
    audit["late_singleton_tier"] = (tier_size == 1) & (tier > 1)

    audit["_requested_order"] = (
        audit["player_name_clean"].astype(str).map(requested_order)
    )
    audit = audit.sort_values("_requested_order", kind="stable")

    return audit[PROJECTION_AUDIT_COLUMNS].reset_index(drop=True)


def _add_multipath_value_columns(audit):
    """Add the VORP/scarcity contribution paths that feed Draft Brain."""
    audit = audit.copy()

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
    return audit


def build_position_value_audit(board, position, replacement_rank):
    """Audit one position with lineup-demand context and multipath value."""
    if "position" not in board.columns:
        return board.iloc[0:0].copy()

    position_clean = str(position).strip().upper()
    audit = board.loc[
        board["position"].astype(str).str.strip().str.upper() == position_clean
    ].copy()

    if audit.empty:
        return audit

    replacement_rank = int(replacement_rank)
    audit = _add_multipath_value_columns(audit)
    audit["position_replacement_rank"] = replacement_rank

    if "position_rank" in audit.columns:
        position_ranks = pd.to_numeric(audit["position_rank"], errors="coerce")
        players_at_or_above_replacement = int(
            (position_ranks <= replacement_rank).fillna(False).sum()
        )
    else:
        players_at_or_above_replacement = min(len(audit), replacement_rank)

    audit["players_at_or_above_replacement"] = players_at_or_above_replacement

    if "brain_score" in audit.columns:
        audit = audit.sort_values("brain_score", ascending=False)
    elif "draft_rank" in audit.columns:
        audit = audit.sort_values("draft_rank", ascending=True)

    return audit.reset_index(drop=True)


def build_rb_te_value_comparison(board, replacement_ranks, top_n=12):
    """Place the strongest RB and TE rows side by side under the same audit math."""
    audits = []

    for position in ("RB", "TE"):
        replacement_rank = int(replacement_ranks.get(position, 0))
        if replacement_rank <= 0:
            continue

        position_audit = build_position_value_audit(
            board,
            position,
            replacement_rank=replacement_rank,
        )
        if not position_audit.empty:
            audits.append(position_audit.head(int(top_n)))

    if not audits:
        return board.iloc[0:0].copy()

    comparison = pd.concat(audits, ignore_index=True, sort=False)
    if "brain_score" in comparison.columns:
        comparison = comparison.sort_values("brain_score", ascending=False)
    elif "draft_rank" in comparison.columns:
        comparison = comparison.sort_values("draft_rank", ascending=True)

    return comparison.reset_index(drop=True)


def build_te_ranking_audit(board):
    """Expose how TE VORP and scarcity flow into Brain through multiple paths.

    This is diagnostic only. It does not change any rankings or weights.
    """
    if "position" not in board.columns:
        return board.iloc[0:0].copy()

    audit = board.loc[
        board["position"].astype(str).str.strip().str.upper() == "TE"
    ].copy()

    audit = _add_multipath_value_columns(audit)

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

    league_settings = load_league_settings(state["league_key"])
    replacement_ranks = calculate_replacement_ranks(rankings, league_settings)
    rb_te_comparison = build_rb_te_value_comparison(
        board,
        replacement_ranks=replacement_ranks,
        top_n=12,
    )
    comparison_columns = [
        "position",
        "player_name_clean",
        "position_rank_label",
        "draft_rank",
        "projected_points",
        "replacement_points",
        "vorp",
        "vorp_score",
        "tier_status",
        "tier_scarcity_score",
        "position_replacement_rank",
        "players_at_or_above_replacement",
        "brain_vorp_total",
        "brain_scarcity_total",
        "brain_vorp_and_scarcity_total",
        "draft_score",
        "pressure_score",
        "brain_score",
        "brain_recommendation",
    ]
    comparison_columns = [
        column for column in comparison_columns if column in rb_te_comparison.columns
    ]

    print("\n============================================")
    print("EDGEIQ RB vs TE VALUE AUDIT")
    print("============================================")
    print(
        f"Replacement ranks: RB={replacement_ranks.get('RB')} | "
        f"TE={replacement_ranks.get('TE')}"
    )
    print("============================================\n")

    if rb_te_comparison.empty:
        print("No RB/TE players were found in the current board.")
    else:
        print(
            rb_te_comparison[comparison_columns]
            .round(2)
            .to_string(index=False)
        )

    projection_audit = build_projection_component_audit(
        board,
        PROJECTION_AUDIT_PLAYERS,
    )

    print("\n============================================")
    print("EDGEIQ PROJECTION + SINGLETON TIER AUDIT")
    print("============================================\n")

    if projection_audit.empty:
        print("No requested projection-audit players were found in the current board.")
    else:
        print(projection_audit.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
