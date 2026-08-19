def _normalize_manager_name(name):
    return " ".join(
        str(name)
        .strip()
        .lower()
        .replace("’", "'")
        .split()
    )


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
        "tendency_source": "neutral_default",
        "tendency_confidence": 0.0,
        "tendency_sample_size": 0,
        "is_provisional": False,
    }

    manager_profiles = {
        "parrots": {
            "rb_aggression": 1.10,
            "wr_aggression": 0.95,
        },
        "go time": {
            "wr_aggression": 1.10,
            "rb_aggression": 0.95,
        },
        "hashbrownies": {
            "qb_aggression": 1.10,
            "te_aggression": 1.05,
        },
    }

    normalized_name = _normalize_manager_name(
        team_name
    )

    profile = manager_profiles.get(
        normalized_name,
        {},
    )

    if profile:
        tendencies.update(
            {
                "tendency_source": "manual_provisional",
                "tendency_confidence": 0.20,
                "tendency_sample_size": 0,
                "is_provisional": True,
            }
        )

    tendencies.update(
        profile
    )

    return tendencies
