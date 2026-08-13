"""
EdgeIQ Pick Value Engine
Version 1

Determines whether a fantasy draft pick
is a steal, fair value, or reach.
"""


def evaluate_pick_value(
    actual_pick,
    expected_pick,
):

    pick_difference = (
        actual_pick
        - expected_pick
    )

    if pick_difference >= 20:

        label = "HUGE STEAL"
        grade = "A+"

    elif pick_difference >= 10:

        label = "STEAL"
        grade = "A"

    elif pick_difference >= 5:

        label = "GOOD VALUE"
        grade = "A-"

    elif pick_difference >= -4:

        label = "FAIR VALUE"
        grade = "B"

    elif pick_difference >= -10:

        label = "SMALL REACH"
        grade = "C+"

    elif pick_difference >= -20:

        label = "REACH"
        grade = "C"

    else:

        label = "MAJOR REACH"
        grade = "D"

    return {
        "actual_pick":
            actual_pick,

        "expected_pick":
            expected_pick,

        "pick_difference":
            pick_difference,

        "value_label":
            label,

        "draft_grade":
            grade,
    }