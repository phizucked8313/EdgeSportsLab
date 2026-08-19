from fantasy_draft_model.engines.manager_tendency_engine import (
    get_manager_tendencies,
)


def make_cpu_pick(
    available,
    team_position_counts,
    round_number,
    team_name,
):
    cpu_pool = available.copy()

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

    # --------------------------------------------------
    # KICKER / DEFENSE DRAFT STRATEGY
    # --------------------------------------------------

    kicker_count = team_position_counts.get("K", 0)
    defense_count = team_position_counts.get("DEF", 0)

    # Never allow more than one K or DEF
    if kicker_count >= 1:
        cpu_pool = cpu_pool[cpu_pool["position"] != "K"]

    if defense_count >= 1:
        cpu_pool = cpu_pool[cpu_pool["position"] != "DEF"]

    # Rounds 1-9: no K or DEF
    if round_number <= 9:
        cpu_pool = cpu_pool[
            ~cpu_pool["position"].isin(["K", "DEF"])
        ]

    # Rounds 10-11: DEF can appear, but no kickers yet
    elif round_number <= 11:
        cpu_pool = cpu_pool[
            cpu_pool["position"] != "K"
        ]

    # Rounds 12-13:
    # DEF is fully available.
    # K is still held back.
    elif round_number <= 13:
        cpu_pool = cpu_pool[
            cpu_pool["position"] != "K"
        ]

    # Round 14+: both K and DEF are available


    
    # --------------------------------------------
    # FORCE REQUIRED LATE-ROUND ROSTER SPOTS
    # --------------------------------------------

    picks_remaining = 15 - round_number + 1

    qb_count = team_position_counts.get("QB", 0)
    rb_count = team_position_counts.get("RB", 0)
    wr_count = team_position_counts.get("WR", 0)
    te_count = team_position_counts.get("TE", 0)

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

    # If remaining picks equal the number of required roster spots,
    # CPU must draft only positions that can complete the legal roster.
    if required_picks > 0 and picks_remaining <= required_picks:

        required_positions = []

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

    # Safety fallback
    if cpu_pool.empty:
        cpu_pool = available.copy()

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