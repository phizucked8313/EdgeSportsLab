
from fantasy_draft_model.models.league_manager import (
    get_draft_order,
)


"""
EdgeIQ Draft Order Engine
Version 1

Maps fantasy managers to draft slots
for each league.
"""


# ============================================================
# GET MANAGER
# ============================================================

def get_manager_for_slot(
    draft_slot,
    league_name="Drunk Sundays",
    draft_order=None
):

    if draft_order is None:

        draft_order = get_draft_order(
            league_name
        )


    return draft_order.get(
        draft_slot,
        f"Slot {draft_slot}"
    )


# ============================================================
# GET MANAGERS BEFORE USER
# ============================================================

def get_managers_before_user(
    slots_before_user,
    league_name="Drunk Sundays",
    draft_order=None
):

    if draft_order is None:

        draft_order = get_draft_order(
            league_name
        )

    managers = []

    for slot in slots_before_user:

        managers.append(
            {
                "draft_slot":
                    slot,

                "manager":
                    get_manager_for_slot(
                        slot,
                        league_name,
                        draft_order
                    ),
            }
        )

    return managers


# ============================================================
# DISPLAY DRAFT ORDER
# ============================================================

def display_draft_order(
league_name="Drunk Sundays",
    draft_order=None
):

    if draft_order is None:

        draft_order = get_draft_order(
            league_name
        )

    print(
        "\n===================================="
    )

    print(
        "EDGEIQ DRAFT ORDER"
    )

    print(
        "===================================="
    )

    for slot in sorted(
        draft_order
    ):

        print(
            f"Slot {slot}: "
            f"{draft_order[slot]}"
        )


def main():

    display_draft_order()


if __name__ == "__main__":

    main()