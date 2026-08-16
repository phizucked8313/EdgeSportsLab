import pandas as pd


def build_kicker_rankings():
    kickers = [
        ("Brandon Aubrey", "DAL", 1),
        ("Cameron Dicker", "LAC", 2),
        ("Ka'imi Fairbairn", "HOU", 3),
        ("Jake Bates", "DET", 4),
        ("Chris Boswell", "PIT", 5),
        ("Chase McLaughlin", "TB", 6),
        ("Tyler Bass", "BUF", 7),
        ("Evan McPherson", "CIN", 8),
        ("Jake Elliott", "PHI", 9),
        ("Harrison Butker", "KC", 10),
        ("Jason Sanders", "MIA", 11),
        ("Younghoe Koo", "ATL", 12),
    ]

    df = pd.DataFrame(
        kickers,
        columns=[
            "player_name_clean",
            "team",
            "position_rank",
        ],
    )

    df["position"] = "K"

    return df


def build_defense_rankings():
    defenses = [
        ("Philadelphia Eagles", "PHI", 1),
        ("Baltimore Ravens", "BAL", 2),
        ("Pittsburgh Steelers", "PIT", 3),
        ("Denver Broncos", "DEN", 4),
        ("Minnesota Vikings", "MIN", 5),
        ("Buffalo Bills", "BUF", 6),
        ("Kansas City Chiefs", "KC", 7),
        ("Houston Texans", "HOU", 8),
        ("Green Bay Packers", "GB", 9),
        ("San Francisco 49ers", "SF", 10),
        ("Los Angeles Chargers", "LAC", 11),
        ("Detroit Lions", "DET", 12),
    ]

    df = pd.DataFrame(
        defenses,
        columns=[
            "player_name_clean",
            "team",
            "position_rank",
        ],
    )

    df["position"] = "DEF"

    return df