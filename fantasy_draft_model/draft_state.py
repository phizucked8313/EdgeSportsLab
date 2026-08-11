"""
EdgeIQ Live Draft State
Version 1

Tracks players selected during a live draft.
"""

import json
from pathlib import Path


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


# ============================================================
# DRAFT PLAYER
# ============================================================

def draft_player(
    player_name,
    drafted_by="Unknown"
):

    state = load_draft_state()

    already_drafted = any(

        player[
            "player_name"
        ].lower()
        == player_name.lower()

        for player
        in state[
            "drafted_players"
        ]
    )

    if already_drafted:

        print(
            f"\n{player_name} is already drafted."
        )

        return


    pick_number = state[
        "current_pick"
    ]


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
        }
    )


    state[
        "current_pick"
    ] += 1


    save_draft_state(
        state
    )


    print(
        f"\nPick {pick_number}: "
        f"{player_name} drafted by "
        f"{drafted_by}"
    )


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

            f"Pick "
            f"{player['pick_number']}: "

            f"{player['player_name']} "

            f"-> "
            f"{player['drafted_by']}"
        )


if __name__ == "__main__":

    show_drafted_players()