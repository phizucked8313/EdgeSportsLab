def make_cpu_pick(
    available,
    team_position_counts,
    round_number,
):
    cpu_pool = available.copy()

    if round_number <= 8:

        if team_position_counts["QB"] >= 1:
            cpu_pool = cpu_pool[
                cpu_pool["position"] != "QB"
            ]

        if team_position_counts["TE"] >= 1:
            cpu_pool = cpu_pool[
                cpu_pool["position"] != "TE"
            ]

    if cpu_pool.empty:
        cpu_pool = available.copy()

    return cpu_pool.iloc[0]