"""
EdgeIQ Roster Tracker Engine
Version 1

Tracks every fantasy team's drafted players
and determines remaining positional needs.
"""

import pandas as pd

from fantasy_draft_model.draft_state import (
    load_draft_state,
)


# ============================================================
# DRUNK SUNDAYS STARTING LINEUP
# ============================================================

LINEUP_REQUIREMENTS = {
    "QB": 1,
    "RB": 2,
    "WR": 2,
    "TE": 1,
    "FLEX": 2,
}


# ============================================================
# BUILD TEAM ROSTERS
# ============================================================

def build_team_rosters(
    rankings_df: pd.DataFrame
):
    """
    Convert draft history into fantasy team rosters.
    """

    state = load_draft_state()

    drafted_players = state.get(
        "drafted_players",
        []
    )

    roster_rows = []

    for pick in drafted_players:

        player_name = pick.get(
            "player_name",
            ""
        )

        drafted_by = pick.get(
            "drafted_by",
            "Unknown"
        )

        pick_number = pick.get(
            "pick_number",
            0
        )

        player_match = rankings_df[
            rankings_df[
                "player_name_clean"
            ]
            .str.lower()
            == player_name.lower()
        ]

        if player_match.empty:
            continue

        player = player_match.iloc[0]

        roster_rows.append(
            {
                "fantasy_team":
                    drafted_by,

                "player_name":
                    player_name,

                "position":
                    player["position"],

                "nfl_team":
                    player["team"],

                "pick_number":
                    pick_number,
            }
        )

    return pd.DataFrame(
        roster_rows
    )


# ============================================================
# POSITION COUNTS
# ============================================================

def get_team_position_counts(
    roster_df: pd.DataFrame,
    fantasy_team
):
    """
    Count QB/RB/WR/TE selections
    for one fantasy team.
    """

    counts = {
        "QB": 0,
        "RB": 0,
        "WR": 0,
        "TE": 0,
    }

    if roster_df.empty:
        return counts

    team_df = roster_df[
        roster_df[
            "fantasy_team"
        ]
        == fantasy_team
    ]

    for position in counts:

        counts[position] = int(
            (
                team_df[
                    "position"
                ]
                == position
            )
            .sum()
        )

    return counts


# ============================================================
# TEAM NEEDS
# ============================================================

def calculate_team_needs(
    roster_df: pd.DataFrame,
    fantasy_team
):
    """
    Determine which starting positions
    a fantasy team still needs.
    """

    counts = get_team_position_counts(
        roster_df,
        fantasy_team
    )

    needs = {}

    needs["QB"] = max(
        0,
        LINEUP_REQUIREMENTS["QB"]
        - counts["QB"]
    )

    needs["RB"] = max(
        0,
        LINEUP_REQUIREMENTS["RB"]
        - counts["RB"]
    )

    needs["WR"] = max(
        0,
        LINEUP_REQUIREMENTS["WR"]
        - counts["WR"]
    )

    needs["TE"] = max(
        0,
        LINEUP_REQUIREMENTS["TE"]
        - counts["TE"]
    )

    # FLEX can be filled by RB or WR.
    rb_wr_total = (
        counts["RB"]
        + counts["WR"]
    )

    required_rb_wr = (
        LINEUP_REQUIREMENTS["RB"]
        + LINEUP_REQUIREMENTS["WR"]
        + LINEUP_REQUIREMENTS["FLEX"]
    )

    needs["FLEX"] = max(
        0,
        required_rb_wr
        - rb_wr_total
    )

    return needs


# ============================================================
# POSITION NEED SCORE
# ============================================================

def get_position_need_score(
    roster_df,
    fantasy_team,
    position
):
    """
    0-100 urgency score for a fantasy team's
    need at a specific position.
    """

    needs = calculate_team_needs(
        roster_df,
        fantasy_team
    )

    if position == "QB":

        return (
            100
            if needs["QB"] > 0
            else 20
        )

    if position == "TE":

        return (
            100
            if needs["TE"] > 0
            else 20
        )

    if position == "RB":

        if needs["RB"] > 0:
            return 100

        if needs["FLEX"] > 0:
            return 65

        return 25

    if position == "WR":

        if needs["WR"] > 0:
            return 100

        if needs["FLEX"] > 0:
            return 65

        return 25

    return 0


# ============================================================
# DISPLAY TEAM NEEDS
# ============================================================

def display_team_needs(
    rankings_df
):
    """
    Print roster construction and needs
    for every team that has drafted a player.
    """

    roster_df = build_team_rosters(
        rankings_df
    )

    if roster_df.empty:

        print(
            "\nNo drafted rosters yet."
        )

        return

    teams = (
        roster_df[
            "fantasy_team"
        ]
        .dropna()
        .unique()
    )

    print(
        "\n========================================"
    )

    print(
        "EDGEIQ TEAM NEEDS"
    )

    print(
        "========================================"
    )

    for fantasy_team in teams:

        counts = get_team_position_counts(
            roster_df,
            fantasy_team
        )

        needs = calculate_team_needs(
            roster_df,
            fantasy_team
        )

        print(
            f"\n{fantasy_team}"
        )

        print(
            f"Roster: "
            f"QB {counts['QB']} | "
            f"RB {counts['RB']} | "
            f"WR {counts['WR']} | "
            f"TE {counts['TE']}"
        )

        print(
            f"Needs: "
            f"QB {needs['QB']} | "
            f"RB {needs['RB']} | "
            f"WR {needs['WR']} | "
            f"TE {needs['TE']} | "
            f"FLEX {needs['FLEX']}"
        )


def main():

    print(
        "EdgeIQ Roster Tracker Engine ready."
    )


if __name__ == "__main__":

    main()