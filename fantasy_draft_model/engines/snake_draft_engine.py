"""
EdgeIQ Snake Draft Engine
Version 1

Tracks:
- Current pick
- Current round
- Current drafting team
- Snake draft order
- User's next pick
- Teams picking before user's next selection
"""


# ============================================================
# DEFAULT SETTINGS
# ============================================================

TEAM_COUNT = 12

# For now, assume Shawn drafts from slot 1.
# Later we will pull this from league settings.
USER_DRAFT_SLOT = 1


# ============================================================
# ROUND
# ============================================================

def get_round_number(
    pick_number,
    team_count=TEAM_COUNT
):
    """
    Convert overall pick number into round number.
    """

    return (
        (pick_number - 1)
        // team_count
    ) + 1


# ============================================================
# PICK WITHIN ROUND
# ============================================================

def get_pick_in_round(
    pick_number,
    team_count=TEAM_COUNT
):
    """
    Return pick number within the current round.
    """

    return (
        (pick_number - 1)
        % team_count
    ) + 1


# ============================================================
# DRAFT SLOT FOR PICK
# ============================================================

def get_draft_slot_for_pick(
    pick_number,
    team_count=TEAM_COUNT
):
    """
    Return which draft slot is currently picking.

    Odd rounds:
    1 -> 12

    Even rounds:
    12 -> 1
    """

    round_number = get_round_number(
        pick_number,
        team_count
    )

    pick_in_round = get_pick_in_round(
        pick_number,
        team_count
    )

    if round_number % 2 == 1:

        return pick_in_round

    return (
        team_count
        - pick_in_round
        + 1
    )


# ============================================================
# USER PICKS
# ============================================================

def get_user_pick_numbers(
    user_slot=USER_DRAFT_SLOT,
    rounds=15,
    team_count=TEAM_COUNT
):
    """
    Return all overall pick numbers belonging
    to the user's draft slot.
    """

    picks = []

    for round_number in range(
        1,
        rounds + 1
    ):

        if round_number % 2 == 1:

            pick_in_round = (
                user_slot
            )

        else:

            pick_in_round = (
                team_count
                - user_slot
                + 1
            )

        overall_pick = (
            (round_number - 1)
            * team_count
            + pick_in_round
        )

        picks.append(
            overall_pick
        )

    return picks


# ============================================================
# NEXT USER PICK
# ============================================================

def get_next_user_pick(
    current_pick,
    user_slot=USER_DRAFT_SLOT,
    rounds=15,
    team_count=TEAM_COUNT
):
    """
    Find user's next future pick.
    """

    user_picks = get_user_pick_numbers(
        user_slot=user_slot,
        rounds=rounds,
        team_count=team_count
    )

    for pick in user_picks:

        if pick >= current_pick:
            return pick

    return None


# ============================================================
# PICKS UNTIL USER
# ============================================================

def get_picks_until_user(
    current_pick,
    user_slot=USER_DRAFT_SLOT,
    rounds=15,
    team_count=TEAM_COUNT
):
    """
    Number of selections before user's next pick.
    """

    next_pick = get_next_user_pick(
        current_pick,
        user_slot,
        rounds,
        team_count
    )

    if next_pick is None:
        return None

    return max(
        0,
        next_pick - current_pick
    )


# ============================================================
# SLOTS PICKING BEFORE USER
# ============================================================

def get_slots_before_user(
    current_pick,
    user_slot=USER_DRAFT_SLOT,
    rounds=15,
    team_count=TEAM_COUNT
):
    """
    Return draft slots scheduled to pick
    before user's next selection.
    """

    next_pick = get_next_user_pick(
        current_pick,
        user_slot,
        rounds,
        team_count
    )

    if next_pick is None:
        return []

    slots = []

    for pick_number in range(
        current_pick,
        next_pick
    ):

        slot = get_draft_slot_for_pick(
            pick_number,
            team_count
        )

        slots.append(
            slot
        )

    return slots


# ============================================================
# DRAFT CONTEXT
# ============================================================

def get_draft_context(
    current_pick,
    user_slot=USER_DRAFT_SLOT,
    rounds=15,
    team_count=TEAM_COUNT
):
    """
    Return full live snake-draft context.
    """

    round_number = get_round_number(
        current_pick,
        team_count
    )

    pick_in_round = get_pick_in_round(
        current_pick,
        team_count
    )

    current_slot = get_draft_slot_for_pick(
        current_pick,
        team_count
    )

    next_user_pick = get_next_user_pick(
        current_pick,
        user_slot,
        rounds,
        team_count
    )

    picks_until_user = get_picks_until_user(
        current_pick,
        user_slot,
        rounds,
        team_count
    )

    slots_before_user = get_slots_before_user(
        current_pick,
        user_slot,
        rounds,
        team_count
    )

    return {

        "current_pick":
            current_pick,

        "round":
            round_number,

        "pick_in_round":
            pick_in_round,

        "current_draft_slot":
            current_slot,

        "user_slot":
            user_slot,

        "next_user_pick":
            next_user_pick,

        "picks_until_user":
            picks_until_user,

        "slots_before_user":
            slots_before_user,
    }


# ============================================================
# TEST
# ============================================================

def main():

    context = get_draft_context(
        current_pick=1
    )

    print(
        "\nEDGEIQ SNAKE DRAFT ENGINE\n"
    )

    for key, value in context.items():

        print(
            f"{key}: {value}"
        )


if __name__ == "__main__":

    main()