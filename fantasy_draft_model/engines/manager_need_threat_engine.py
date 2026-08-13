"""
EdgeIQ Manager Need Threat Engine
Version 1

Measures positional threat from managers
drafting before the user's next pick.
"""

import pandas as pd

from fantasy_draft_model.engines.draft_order_engine import (
    get_managers_before_user,
)

from fantasy_draft_model.engines.roster_tracker_engine import (
    build_team_rosters,
    get_position_need_score,
)


POSITIONS = [
    "QB",
    "RB",
    "WR",
    "TE",
]


def calculate_manager_need_threat(
    rankings_df: pd.DataFrame,
    slots_before_user,
    league_name="Drunk Sundays",
):
    """
    Calculate position threat created by managers
    drafting before the user's next pick.
    """

    roster_df = build_team_rosters(
        rankings_df
    )

    managers_before = get_managers_before_user(
        slots_before_user,
        league_name=league_name
    )

    results = []

    for position in POSITIONS:

        total_score = 0
        needy_managers = 0

        manager_details = []

        for manager_info in managers_before:

            manager_name = manager_info[
                "manager"
            ]

            need_score = get_position_need_score(
                roster_df,
                manager_name,
                position
            )

            if need_score >= 65:
                needy_managers += 1

            total_score += need_score

            manager_details.append(
                {
                    "manager":
                        manager_name,

                    "need_score":
                        need_score,
                }
            )

        manager_count = len(
            managers_before
        )

        if manager_count > 0:

            threat_score = (
                total_score
                / manager_count
            )

        else:

            threat_score = 0

        if threat_score >= 80:

            threat_label = (
                "VERY HIGH"
            )

        elif threat_score >= 60:

            threat_label = (
                "HIGH"
            )

        elif threat_score >= 40:

            threat_label = (
                "MODERATE"
            )

        elif threat_score >= 20:

            threat_label = (
                "LOW"
            )

        else:

            threat_label = (
                "VERY LOW"
            )

        results.append(
            {
                "position":
                    position,

                "threat_score":
                    round(
                        threat_score,
                        1
                    ),

                "threat_label":
                    threat_label,

                "needy_managers":
                    needy_managers,

                "manager_count":
                    manager_count,

                "manager_details":
                    manager_details,
            }
        )

    return pd.DataFrame(
        results
    )


def get_position_threat(
    rankings_df,
    slots_before_user,
    position,
    league_name="Drunk Sundays",
):
    """
    Return threat information for one position.
    """

    threat_df = calculate_manager_need_threat(
        rankings_df,
        slots_before_user,
        league_name=league_name
    )

    match = threat_df[
        threat_df["position"]
        == position
    ]

    if match.empty:

        return {
            "position":
                position,

            "threat_score":
                0,

            "threat_label":
                "VERY LOW",

            "needy_managers":
                0,

            "manager_count":
                0,
        }

    return match.iloc[0].to_dict()


def main():

    print(
        "EdgeIQ Manager Need Threat Engine ready."
    )


if __name__ == "__main__":

    main()