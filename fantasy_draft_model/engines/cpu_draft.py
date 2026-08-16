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


    # --------------------------------------------------
    # FORCE REQUIRED LATE-ROUND ROSTER SPOTS
    # --------------------------------------------------

    picks_remaining = 15 - round_number + 1

    needs_kicker = kicker_count == 0
    needs_defense = defense_count == 0

    required_special_teams = (
        int(needs_kicker)
        + int(needs_defense)
    )

    # If remaining picks equal remaining required
    # K/DEF spots, force one of those positions.
    if (
        required_special_teams > 0
        and picks_remaining <= required_special_teams
    ):
        required_positions = []

        if needs_kicker:
            required_positions.append("K")

        if needs_defense:
            required_positions.append("DEF")

        cpu_pool = cpu_pool[
            cpu_pool["position"].isin(
                required_positions
            )
        ]


    # Avoid a second QB or TE early
    if round_number <= 8:

        if team_position_counts["QB"] >= 1:
            cpu_pool = cpu_pool[
                cpu_pool["position"] != "QB"
            ]

        if team_position_counts["TE"] >= 1:
            cpu_pool = cpu_pool[
                cpu_pool["position"] != "TE"
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