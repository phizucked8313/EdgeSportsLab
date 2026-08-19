from fantasy_draft_model.engines.manager_tendency_engine import (
    get_manager_tendencies,
)


def make_cpu_pick(
    available,
    team_position_counts,
    round_number,
    team_name,
    draft_rounds=15,
):
    tendencies = get_manager_tendencies(
        team_name
    )

    position_weight_map = {
        "QB": tendencies["qb_aggression"],
        "RB": tendencies["rb_aggression"],
        "WR": tendencies["wr_aggression"],
        "TE": tendencies["te_aggression"],
        "K": 1.00,
        "DEF": 1.00,
    }

    kicker_count = team_position_counts.get("K", 0)
    defense_count = team_position_counts.get("DEF", 0)
    qb_count = team_position_counts.get("QB", 0)
    rb_count = team_position_counts.get("RB", 0)
    wr_count = team_position_counts.get("WR", 0)
    te_count = team_position_counts.get("TE", 0)

    # --------------------------------------------
    # HARD ROSTER LIMITS
    # --------------------------------------------

    # These limits must survive every fallback path.
    legal_pool = available.copy()

    if kicker_count >= 1:
        legal_pool = legal_pool[legal_pool["position"] != "K"]

    if defense_count >= 1:
        legal_pool = legal_pool[legal_pool["position"] != "DEF"]

    # Keep the first QB available naturally. Once a starter is rostered,
    # block a backup through Round 10. Starting in Round 11 a second QB
    # can be selected on value, but a third QB is never allowed.
    block_qb = (
        qb_count >= 2
        or (qb_count >= 1 and round_number <= 10)
    )

    if block_qb:
        legal_pool = legal_pool[
            legal_pool["position"] != "QB"
        ]

    cpu_pool = legal_pool.copy()

    # --------------------------------------------------
    # KICKER / DEFENSE DRAFT STRATEGY
    # --------------------------------------------------

    # Rounds 1-9: no K or DEF
    if round_number <= 9:
        cpu_pool = cpu_pool[
            ~cpu_pool["position"].isin(["K", "DEF"])
        ]

    # Rounds 10-13: DEF can appear, but no kickers yet
    elif round_number <= 13:
        cpu_pool = cpu_pool[
            cpu_pool["position"] != "K"
        ]

    # Round 14+: both K and DEF are available

    # --------------------------------------------
    # FORCE REQUIRED LATE-ROUND ROSTER SPOTS
    # --------------------------------------------

    picks_remaining = int(draft_rounds) - round_number + 1

    needs_qb = max(0, 1 - qb_count)
    needs_rb = max(0, 2 - rb_count)
    needs_wr = max(0, 2 - wr_count)
    needs_te = max(0, 1 - te_count)

    # Two FLEX spots can be filled by RB or WR.
    rb_wr_count = rb_count + wr_count
    needs_flex = max(0, 6 - rb_wr_count)

    needs_kicker = int(kicker_count == 0)
    needs_defense = int(defense_count == 0)

    required_picks = (
        needs_qb
        + needs_rb
        + needs_wr
        + needs_te
        + needs_flex
        + needs_kicker
        + needs_defense
    )

    required_positions = []
    force_required_position = (
        required_picks > 0
        and picks_remaining <= required_picks
    )

    if force_required_position:
        if needs_qb:
            required_positions.append("QB")

        if needs_rb:
            required_positions.append("RB")

        if needs_wr:
            required_positions.append("WR")

        if needs_te:
            required_positions.append("TE")

        if needs_flex:
            required_positions.extend(["RB", "WR"])

        if needs_kicker:
            required_positions.append("K")

        if needs_defense:
            required_positions.append("DEF")

        cpu_pool = cpu_pool[
            cpu_pool["position"].isin(required_positions)
        ]

    # --------------------------------------------------
    # SAFE FALLBACK
    # --------------------------------------------------

    # If soft K/DEF timing made the pool empty, relax only the soft timing.
    # Hard roster caps remain in legal_pool, and forced completion still
    # restricts the fallback to positions that can complete the roster.
    if cpu_pool.empty:
        cpu_pool = legal_pool.copy()

        if force_required_position:
            cpu_pool = cpu_pool[
                cpu_pool["position"].isin(required_positions)
            ]

    if cpu_pool.empty:
        raise ValueError(
            f"No legal CPU pick for {team_name} in round {round_number}"
        )

    # Apply manager personality
    cpu_pool = cpu_pool.copy()

    cpu_pool["manager_score"] = (
        cpu_pool["draft_rank"]
        / cpu_pool["position"].map(
            position_weight_map
        ).fillna(1.00)
    )

    cpu_pool = cpu_pool.sort_values(
        "manager_score"
    )

    # CPU makes its selection
    return cpu_pool.iloc[0]
