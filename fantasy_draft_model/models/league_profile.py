"""
EdgeIQ League Profile
Version 1
"""


LEAGUES = {
    "Drunk Sundays": {
        "name": "Drunk Sundays",
        "league_key": "drunk_sundays",
        "user_team": "BLKWDW'S",
        "keeper_rules": {
            "standard": 15,
            "rookie": 3,
        },
        "team_count": 12,
        "draft_rounds": 15,
        "roster_size": 15,
        "starters": {
            "QB": 1,
            "RB": 2,
            "WR": 2,
            "TE": 1,
            "FLEX": 2,
            "K": 1,
            "DEF": 1,
        },
        "bench_size": 5,
        "draft_order": [
            "Parrots",
            "Go Time",
            "Hashbrownies",
            "The Bird Is The Word",
            "Tez Swagg",
            "Diamonds Forever Inn The House",
            "Only Here To Beat My Husband",
            "Long & Deep",
            "BLKWDW'S",
            "Door Dash At 2AM",
            "It's Geoffrey James Beeitch",
            "Hawk Tua",
        ],
    },
    "Somewhat Related": {
        "name": "Somewhat Related",
        "league_key": "somewhat_related",
        "user_team": "Phizucked",
        "keeper_rules": {
            "standard": 16,
        },
        "team_count": 12,
        "draft_rounds": 16,
        "roster_size": 16,
        "starters": {
            "QB": 1,
            "RB": 2,
            "WR": 2,
            "TE": 1,
            "FLEX": 2,
            "K": 1,
            "DEF": 1,
        },
        "bench_size": 6,
        "draft_order": [
            "Stopped Short",
            "Winner in Mexico",
            "Sixty Niners",
            "Fat Dink",
            "Phizucked",
            "Buttnuggets",
            "Hashbrownies",
            "Retriever's",
            "Phinatic",
            "S U C K I T",
            "Injured Reserve",
            "Jabronies",
        ],
    },
}


def get_league(league_name):
    return LEAGUES.get(league_name)
