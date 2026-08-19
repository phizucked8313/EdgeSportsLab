"""
EdgeIQ Mock Draft Engine
Version 1

Simulates fantasy football drafts using:
- League settings
- Draft order
- Keepers
- EdgeIQ rankings
- Manager tendencies
"""

from fantasy_draft_model.models.league_profile import get_league
from fantasy_draft_model.keepers import load_keepers
from fantasy_draft_model.rankings import (
    build_draft_rankings,
)
from fantasy_draft_model.models.schedule import get_bye_week
from fantasy_draft_model.ui.draft_board import build_draft_board
from fantasy_draft_model.ui.player_selection import select_player
from fantasy_draft_model.engines.cpu_draft import make_cpu_pick


def normalize_team_name(name):
    return (
        str(name)
        .strip()
        .lower()
        .replace("’", "'")
    )





def load_mock_league(league_name):
    league = get_league(
        league_name
    )

    return league

def load_mock_keepers(league_name):
    keepers = load_keepers(
        league_name
    )

    return keepers


# ============================================================
# BUILD KEEPER MAP
# ============================================================


def build_keeper_map(league_name):

    keepers = load_mock_keepers(
        league_name
    )

    keeper_map = {}

    for _, keeper in keepers.iterrows():

        key = (
            keeper["owner_team"],
            int(keeper["keeper_round"])
        )

        keeper_map[key] = keeper["player_name"]

    return keeper_map



# ============================================================
# GET KEEPER FOR PICK
# ============================================================

def get_keeper_for_pick(
    keeper_map,
    team_name,
    round_number
):

    key = (
        team_name,
        round_number
    )

    return keeper_map.get(key)


# ============================================================
# CALCULATE SNAKE PICK
# ============================================================

def calculate_snake_pick(
    round_number,
    draft_slot,
    team_count
):

    if round_number % 2 == 1:
        pick_in_round = draft_slot

    else:
        pick_in_round = (
            team_count - draft_slot + 1
        )

    overall_pick = (
        (round_number - 1) * team_count
        + pick_in_round
    )

    return overall_pick


# ============================================================
# BUILD KEEPER PICK RESERVATIONS
# ============================================================


def build_keeper_reservations(
    league_name,
    draft_slots,
    team_count
):

    keepers = load_mock_keepers(
        league_name
    )

    reservations = {}

    for _, keeper in keepers.iterrows():

        team_name = keeper["owner_team"]
        round_number = int(
            keeper["keeper_round"]
        )

        draft_slot = draft_slots.get(
            team_name
        )

        if draft_slot is None:
            raise ValueError(
                f"Keeper team {team_name!r} is not in the {league_name} draft order"
            )

        overall_pick = calculate_snake_pick(
            round_number,
            draft_slot,
            team_count
        )

        reservations[overall_pick] = {
            "team": team_name,
            "player": keeper["player_name"],
            "round": round_number,
            "keeper_type": keeper["keeper_type"],
        }

    return reservations


# ============================================================
# BUILD DRAFT SLOT MAP
# ============================================================

def build_draft_slot_map(league_name):

    league = load_mock_league(
        league_name
    )

    draft_order = league["draft_order"]

    draft_slots = {}

    for index, team_name in enumerate(
        draft_order,
        start=1
    ):

        draft_slots[team_name] = index

    return draft_slots



# ============================================================
# BUILD LEAGUE KEEPER RESERVATIONS
# ============================================================

def build_league_keeper_reservations(league_name):

    league = load_mock_league(
        league_name
    )

    draft_slots = build_draft_slot_map(
        league_name
    )

    reservations = build_keeper_reservations(
        league_name,
        draft_slots,
        league["team_count"]
    )

    return reservations



# ============================================================
# RUN MOCK DRAFT SKELETON
# ============================================================

def get_team_position_counts(
    draft_results,
    team_name
):

    counts = {
        "QB": 0,
        "RB": 0,
        "WR": 0,
        "TE": 0,
        "K": 0,
        "DEF": 0,
    }

    for pick in draft_results:

        if pick["fantasy_team"] == team_name:

            position = pick["position"]

            if position in counts:
                counts[position] += 1

    return counts

def get_bye_week_counts(
    draft_results,
    team_name
):

    bye_counts = {}

    for pick in draft_results:

        if pick["fantasy_team"] != team_name:
            continue

        bye_week = pick.get("bye_week")

        if bye_week is None:
            continue

        bye_counts[bye_week] = (
            bye_counts.get(
                bye_week,
                0
            )
            + 1
        )

    return bye_counts

def run_mock_draft(
    league_name,
    user_team,
    rounds=None
):

    league = load_mock_league(
        league_name
    )

    if rounds is None:
        rounds = int(league["draft_rounds"])

    cpu_draft_rounds = int(
        league.get("draft_rounds", rounds)
    )

    rankings = build_draft_rankings(
        league["league_key"]
    )


    keeper_reservations = (
        build_league_keeper_reservations(
            league_name
    )
)


    team_count = league[
        "team_count"
    ]

    draft_order = league[
        "draft_order"
    ]

    keeper_reservations = (
        build_league_keeper_reservations(
            league_name
        )
    )


    keeper_names = {
        keeper["player"].lower()
        for keeper in keeper_reservations.values()
    }

    available = rankings[
        ~rankings[
            "player_name_clean"
        ]
        .str.lower()
        .isin(
            keeper_names
        )
    ].copy()

    available = (
        available
        .sort_values(
            "draft_rank"
        )
        .reset_index(
            drop=True
        )
    )

    print("\nDEBUG AVAILABLE ROOKIES")
    print(
        available[
            available["is_rookie"].fillna(False) == True
        ][
            [
                "player_name_clean",
                "position",
                "draft_rank",
                "projected_points",
            ]
        ]
        .head(25)
        .to_string(index=False)
    )




    available["bye_week"] = available["team"].map(get_bye_week)


    total_picks = (
        rounds * team_count
    )

    draft_results = []

    print(
        f"\nEDGEIQ MOCK DRAFT"
    )

    print(
        f"League: {league_name}"
    )

    print(
        f"Teams: {team_count}"
    )

    print(
        f"Rounds: {rounds}"
    )

    print(
        "\n"
        "========================================"
    )

    for overall_pick in range(
        1,
        total_picks + 1
    ):

        round_number = (
            (overall_pick - 1)
            // team_count
        ) + 1

        pick_in_round = (
            (overall_pick - 1)
            % team_count
        ) + 1

        if round_number % 2 == 1:

            draft_slot = (
                pick_in_round
            )

        else:

            draft_slot = (
                team_count
                - pick_in_round
                + 1
            )

        team_name = draft_order[
            draft_slot - 1
        ]

        team_position_counts = get_team_position_counts(
            draft_results,
            team_name
        )


        print(
            f"\nPick {overall_pick} | "
            f"Round {round_number} | "
            f"Slot {draft_slot}"
        )

        print(
            f"Team: {team_name}"
        )

        if overall_pick in keeper_reservations:

            keeper = (
                keeper_reservations[
                    overall_pick
                ]
            )

            keeper_player = rankings[
                rankings["player_name_clean"]
                .str.lower()
                == keeper["player"].lower()
            ]

            if not keeper_player.empty:

                keeper_position = keeper_player.iloc[0][
                    "position"
                ]

                keeper_nfl_team = keeper_player.iloc[0][
                    "team"
                ]

            else:

                keeper_position = None
                keeper_nfl_team = None

            draft_results.append(
                {
                    "overall_pick": overall_pick,
                    "round": round_number,
                    "draft_slot": draft_slot,
                    "fantasy_team": team_name,
                    "player": keeper["player"],
                    "position": keeper_position,
                    "nfl_team": keeper_nfl_team,
                    "bye_week": get_bye_week(
                        keeper_nfl_team
                    ),
                    "keeper": True,
                }
            )



            print(
                f"KEEPER: "
                f"{keeper['player']}"
            )

        

        else:    

            if normalize_team_name(team_name) == normalize_team_name(user_team):
                   
                bye_counts = get_bye_week_counts(
                    draft_results,
                    team_name
                )

                print(
                    "\nBYE WEEK OVERVIEW"
                )

                if bye_counts:

                    for bye_week in sorted(bye_counts):

                        player_count = bye_counts[bye_week]

                        warning = ""

                        if player_count >= 3:
                            warning = "  !!! HIGH CONFLICT !!!"

                        elif player_count == 2:
                            warning = "  ⚠ CONFLICT RISK"

                        print(
                            f"Week {bye_week}: "
                            f"{player_count} player(s)"
                            f"{warning}"
                        )

                else:

                    print(
                        "No bye-week conflicts yet."
                    )        



                print(
                    "\n"
                    "========================================"
                )

                print(
                    f"{user_team} IS ON THE CLOCK"
                )

                print(
                "========================================"
                )
                
                print(
                    f"Pick {overall_pick} | "
                    f"Round {round_number}"
                )

                print(
                    "\nBEST AVAILABLE"
                )
                             
            if team_name == user_team:

                selected_player = None

                while selected_player is None:

                    top_available = build_draft_board(
                        available
                    )

                    selected_player = select_player(
                        top_available,
                        bye_counts,
                    )
            else:
                selected_player = make_cpu_pick(
                    available,
                    team_position_counts,
                    round_number,
                    team_name,
                    draft_rounds=cpu_draft_rounds,
                )

                
            # --------------------------------------------------
            # RECORD PICK - RUNS FOR USER AND CPU
            # --------------------------------------------------

            player_name = selected_player[
                "player_name_clean"
            ]

            position = selected_player[
                "position"
            ]

            nfl_team = selected_player[
                "team"
            ]

            draft_results.append(
                {
                    "overall_pick": overall_pick,
                    "round": round_number,
                    "draft_slot": draft_slot,
                    "fantasy_team": team_name,
                    "player": player_name,
                    "position": position,
                    "nfl_team": nfl_team,
                    "bye_week": int(
                        selected_player["bye_week"]
                    ),
                    "keeper": False,
                }
            )

            print(
                f"\nSELECTED: "
                f"{player_name}"
            )

            print(
                f"{position} | "
                f"{nfl_team}"
            )

            # Remove drafted player from available pool
            available = available[
                available[
                    "player_name_clean"
                ]
                .str.lower()
                != player_name.lower()
            ].copy()

            available = (
                available
                .reset_index(
                    drop=True
                )
            )

    return draft_results















