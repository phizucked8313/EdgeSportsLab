"""
EdgeIQ League Manager
Version 1

Stores league-specific settings so every
draft engine can load the correct configuration.
"""


LEAGUES = {
    "Drunk Sundays": {
        "user_team": "BLKWDW's",
        "team_count": 12,
        "rounds": 15,
        "keeper_league": True,
        "rookie_keeper_round": 3,
        "standard_keeper_round": 15,

        "draft_order": {
            1: "Parrots",
            2: "Go Time",
            3: "Hashbrownies",
            4: "The Bird Is The Word",
            5: "Tez Swagg",
            6: "Diamonds Forever In The House",
            7: "NH4Life",
            8: "Long & Deep",
            9: "BLKWDW's",
            10: "Door Dash At 2AM",
            11: "It's Geoffrey James Beeitch",
            12: "Hawk Tua",
        },
    },

    "Somewhat Related": {
        "user_team": "Phizucked",
        "team_count": 12,
        "rounds": 15,
        "keeper_league": False,

        "draft_order": {
            1: "Stopped Short",
            2: "Winner in Mexico",
            3: "Sixty Niners",
            4: "Fat Dink",
            5: "Phizucked",
            6: "Buttnuggets",
            7: "Hashbrownies",
            8: "Retriever's",
            9: "Phinatic",
            10: "S U C K I T",
            11: "Injured Reserve",
            12: "Jabronies",
        },
    },
}


def get_league(league_name):
    """
    Return complete league configuration.
    """

    return LEAGUES.get(
        league_name
    )


def get_user_team(league_name):

    league = get_league(
        league_name
    )

    if league is None:
        return None

    return league[
        "user_team"
    ]


def get_user_draft_slot(league_name):
    """
    Automatically find the user's draft slot.
    """

    league = get_league(
        league_name
    )

    if league is None:
        return None

    user_team = league[
        "user_team"
    ]

    draft_order = league[
        "draft_order"
    ]

    for slot, team in draft_order.items():

        if team == user_team:
            return slot

    return None


def get_draft_order(league_name):

    league = get_league(
        league_name
    )

    if league is None:
        return {}

    return league[
        "draft_order"
    ]


def display_league(league_name):

    league = get_league(
        league_name
    )

    if league is None:

        print(
            f"League not found: {league_name}"
        )

        return

    print(
        "\n===================================="
    )

    print(
        f"EDGEIQ LEAGUE: {league_name}"
    )

    print(
        "===================================="
    )

    print(
        f"Your Team: "
        f"{league['user_team']}"
    )

    print(
        f"Your Draft Slot: "
        f"{get_user_draft_slot(league_name)}"
    )

    print(
        f"Teams: "
        f"{league['team_count']}"
    )

    print(
        "\nDraft Order"
    )

    for slot, team in league[
        "draft_order"
    ].items():

        marker = ""

        if team == league[
            "user_team"
        ]:

            marker = "  <-- YOU"

        print(
            f"{slot}: "
            f"{team}"
            f"{marker}"
        )


def main():

    display_league(
        "Drunk Sundays"
    )

    display_league(
        "Somewhat Related"
    )


if __name__ == "__main__":

    main()