"""
EdgeIQ League Profile
Version 1
"""


LEAGUES = {
    "Drunk Sundays": {
        "name": "Drunk Sundays",
        "team_count": 12,
    
        "draft_order": [
                "Parrots",
                "Go Time",
                "Hashbrownies",
                "The Bird Is The Word",
                "Tez Swagg",
                "Diamonds Forever Inn The House",
                "NH4Life",
                "Long & Deep",
                "BLKWDW'S",
                "Door Dash At 2AM",
                "It's Geoffrey James Beeitch",
                "Hawk Tua",
            ],
},       



    "Somewhat Related": {
        "name": "Somewhat Related",
        "team_count": 12,

        

    },
}


def get_league(league_name):
    return LEAGUES.get(
    league_name
)


