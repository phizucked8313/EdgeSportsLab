def get_manager_tendencies(
    team_name,
):
    tendencies = {
        "qb_aggression": 1.00,
        "rb_aggression": 1.00,
        "wr_aggression": 1.00,
        "te_aggression": 1.00,
        "rookie_aggression": 1.00,
        "risk_tolerance": 1.00,
    }

    manager_profiles = {
        "Parrots": {
            "rb_aggression": 1.10,
            "wr_aggression": 0.95,
        },

        "Go Time": {
            "wr_aggression": 1.10,
            "rb_aggression": 0.95,
        },

        "Hashbrownies": {
            "qb_aggression": 1.10,
            "te_aggression": 1.05,
        },
    }

    profile = manager_profiles.get(
        team_name,
        {}
    )

    tendencies.update(
        profile
    )

    return tendencies