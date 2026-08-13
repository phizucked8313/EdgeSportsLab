"""
EdgeIQ Live Draft State
Version 1

Tracks players selected during a live draft.
"""

import json
from pathlib import Path

from fantasy_draft_model.engines.snake_draft_engine import (
    get_draft_slot_for_pick,
)

from fantasy_draft_model.models.league_manager import (
    get_draft_order,
)

from fantasy_draft_model.engines.pick_value_engine import (
    evaluate_pick_value,
)

from fantasy_draft_model.rankings import (
    build_draft_rankings,
)





STATE_FILE = (
    Path(__file__).parent
    / "data"
    / "draft_state.json"
)


# ============================================================
# DEFAULT STATE
# ============================================================

def default_state():

    return {
        "drafted_players": [],
        "current_pick": 1,
    }


# ============================================================
# LOAD STATE
# ============================================================

def load_draft_state():

    if not STATE_FILE.exists():

        save_draft_state(
            default_state()
        )

    with open(
        STATE_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(
            file
        )


# ============================================================
# SAVE STATE
# ============================================================

def save_draft_state(state):

    STATE_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        STATE_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            state,
            file,
            indent=4
        )

def announce_pick(
    player_name,
    drafted_by,
    pick_number,
    round_number,
    draft_slot,
):

    print(
        "\n"
        "========================================"
    )

    print(
        f"WITH THE {pick_number} PICK"
    )

    print()

    print(
        drafted_by
    )

    print()

    print(
        "selects"
    )

    print()

    print(
        player_name.upper()
    )

    print()

    print(
        f"Round {round_number} | "
        f"Slot {draft_slot}"
    )

    print(
        "========================================"
    )


# ============================================================
# DRAFT PLAYER
# ============================================================

def draft_player(
    player_name,
    drafted_by=None,
    league_name="Drunk Sundays"
):

    state = load_draft_state()

    for drafted_player in state.get(
    "drafted_players",
    []
):

        if (
            drafted_player.get(
                "player_name",
                ""
            ).lower()
            == player_name.lower()
        ):

            drafted_by = drafted_player.get(
                "drafted_by",
                "Unknown"
            )

            pick_number = drafted_player.get(
                "pick_number",
                "Unknown"
            )

            round_number = drafted_player.get(
                "round",
                "Unknown"
            )

            draft_slot = drafted_player.get(
                "draft_slot",
                "Unknown"
            )

            print(
                f"\n{player_name} was already drafted."
            )

            print(
                f"Drafted By: {drafted_by}"
            )

            print(
                f"Pick: {pick_number}"
            )

            print(
                f"Round: {round_number}"
            )

            print(
                f"Draft Slot: {draft_slot}"
            )

            return

    
    pick_number = state[
        "current_pick"
    ]

    if drafted_by is None:

        draft_order = get_draft_order(
            league_name
        )

        draft_slot = get_draft_slot_for_pick(
            pick_number,
            team_count=len(
                draft_order
            )
        )

        drafted_by = draft_order.get(
            draft_slot,
            f"Slot {draft_slot}"
        )

    round_number = (
        (pick_number - 1)
        // len(draft_order)
    ) + 1    


    state[
        "drafted_players"
    ].append(

        {
            "player_name":
                player_name,

            "drafted_by":
                drafted_by,

            "pick_number":
                pick_number,

            "round":
                round_number,

            "draft_slot":
                draft_slot,        
        }
    )


    state[
        "current_pick"
    ] += 1


    save_draft_state(
        state
    )

    announce_pick(
        player_name,
        drafted_by,
        pick_number,
        round_number,
        draft_slot
    )


def ordinal(number):

    if 10 <= number % 100 <= 20:
        suffix = "TH"

    else:
        suffix = {
            1: "ST",
            2: "ND",
            3: "RD",
        }.get(
            number % 10,
            "TH"
        )

    return f"{number}{suffix}"


# =========================================
# GRADE PICK
# =========================================


def grade_pick(player_name):

    grades = {
        "Christian McCaffrey": "A+",
        "Ja'Marr Chase": "A+",
        "Justin Jefferson": "A+",
        "Malik Nabers": "A+",
        "Ashton Jeanty": "A",
        "TreVeyon Henderson": "A",
        "Patrick Mahomes": "A",
        "Josh Allen": "A",
        "Lamar Jackson": "A",
    }

    return grades.get(player_name, "B")


# =========================================
# EDGE SCORE
# =========================================

def edge_score(player_name):

    scores = {
        "Christian McCaffrey": 96.3,
        "Puka Nacua": 95.6,
        "Bijan Robinson": 93.0,
        "Jaxon Smith-Njigba": 93.8,
        "Jahmyr Gibbs": 90.7,
    }

    return scores.get(
        player_name,
        80.0
    )


# ============================================
# EXPECTED PICK
# ============================================

DRAFT_RANKINGS_CACHE = None

def get_expected_pick(player_name):

    global DRAFT_RANKINGS_CACHE

    if DRAFT_RANKINGS_CACHE is None:
        DRAFT_RANKINGS_CACHE = build_draft_rankings()

    df = DRAFT_RANKINGS_CACHE
    

    player = df[
        df["player_name_clean"]
        .str.lower()
        == player_name.lower()
    ]

    if player.empty:
        return None

    return int(
        player.iloc[0][
            "draft_rank"
        ]
    )

# ============================================
# ANNOUNCE PICK
# ============================================

def announce_pick(
    player_name,
    drafted_by,
    pick_number,
    round_number,
    draft_slot,
):

    grade = grade_pick(player_name)
    score = edge_score(player_name)
    expected_pick = get_expected_pick(
        player_name
)

    if expected_pick is not None:

        pick_value = evaluate_pick_value(
            actual_pick=pick_number,
            expected_pick=expected_pick,
    )

    else:

        pick_value = None


        print("\n========================================")

        print(
            f"WITH THE {ordinal(pick_number)} PICK"
        )

        print()
        print(drafted_by)
        print()
        print("selects")
        print()
        print(player_name.upper())

        print()

        print(
            f"EdgeScore: {score:.1f}"
        )

        print(
            f"Draft Grade: {grade}"
        )

    if pick_value is not None:

        print()

        print(
            f"Expected Pick: "
            f"{pick_value['expected_pick']}"
        )

        print(
            f"Pick Value: "
            f"{pick_value['value_label']}"
        )

        difference = (
            pick_value[
                "pick_difference"
            ]
        )

    if difference >= 20:

        print()
        print("🔥🔥 EDGEIQ HUGE STEAL 🔥🔥")
        print()

        print(
            f"Selected {difference} picks "
            f"later than expected."
        )

        print(
            "EdgeIQ strongly approves."
        )

    elif difference >= 10:

        print()
        print("🔥 EDGEIQ STEAL")
        print()

        print(
            f"Selected {difference} picks "
            f"later than expected."
        )

    elif difference >= 5:

        print()
        print("✅ GOOD VALUE")
        print()

        print(
            f"Selected {difference} picks "
            f"later than expected."
        )

    elif difference <= -20:

        print()
        print("⚠️⚠️ EDGEIQ MAJOR REACH ALERT ⚠️⚠️")
        print()

        print(
            f"Selected {abs(difference)} picks "
            f"earlier than expected."
        )

        print(
            "EdgeIQ strongly disagrees with this selection."
        )

    elif difference <= -10:

        print()
        print("⚠️ EDGEIQ REACH ALERT")
        print()

        print(
            f"Selected {abs(difference)} picks "
            f"earlier than expected."
        )

    elif difference <= -5:

        print()
        print("⚠️ SMALL REACH")
        print()

        print(
            f"Selected {abs(difference)} picks "
            f"earlier than expected."
        )

    else:

        print()
        print("✅ FAIR VALUE")


        if difference >= 5:

            print(
                f"Value Gained: "
                f"+{difference} picks"
            )

        elif difference <= -5:

            print(
                f"Reached: "
                f"{abs(difference)} picks early"
            )

        print()
        print(f"Round {round_number} | Slot {draft_slot}")
        print("========================================")
        


# ============================================================
# GET DRAFTED PLAYER NAMES
# ============================================================

def get_drafted_player_names():

    state = load_draft_state()

    return [

        player[
            "player_name"
        ]

        for player
        in state[
            "drafted_players"
        ]
    ]


# ============================================================
# UNDO LAST PICK
# ============================================================

def undo_last_pick():

    state = load_draft_state()

    if not state[
        "drafted_players"
    ]:

        print(
            "\nNo picks to undo."
        )

        return


    removed = (
        state[
            "drafted_players"
        ].pop()
    )


    state[
        "current_pick"
    ] = max(
        1,
        state[
            "current_pick"
        ] - 1
    )


    save_draft_state(
        state
    )


    print(
        f"\nUndo: "
        f"{removed['player_name']}"
    )


# ============================================================
# RESET DRAFT
# ============================================================

def reset_draft():

    save_draft_state(
        default_state()
    )

    print(
        "\nDraft state reset."
    )


# ============================================================
# SHOW PICKS
# ============================================================

def show_drafted_players():

    state = load_draft_state()

    print(
        "\n===================================="
    )

    print(
        "EDGEIQ DRAFT HISTORY"
    )

    print(
        "====================================\n"
    )


    if not state[
        "drafted_players"
    ]:

        print(
            "No players drafted yet."
        )

        return


    for player in state[
        "drafted_players"
    ]:


        print(
            f"Round {player.get('round', 'Unknown')} | "
            f"Pick {player.get('pick_number', 'Unknown')} | "
            f"Slot {player.get('draft_slot', 'Unknown')}"
)

        print(
            f"{player.get('drafted_by', 'Unknown')} "
            f"selects "
            f"{player.get('player_name', 'Unknown')}"
        )

        print(
            "-" * 40
        )
     


if __name__ == "__main__":

    show_drafted_players()