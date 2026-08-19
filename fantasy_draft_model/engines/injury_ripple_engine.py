import pandas as pd


# ============================================================
# EDGEIQ INJURY RIPPLE ENGINE
# ============================================================
#
# Purpose:
# Convert injuries into fantasy-football ripple effects.
#
# Examples:
# - WR1 out -> WR2 / TE opportunity rises
# - Starting LT out -> QB / RB efficiency can fall
# - Starting CB out -> opposing WR matchup improves
#
# Version 1:
# Build simple unit-based fantasy impact adjustments.
# ============================================================


OFFENSIVE_RIPPLE_WEIGHTS = {
    "QB": {
        "OFFENSIVE_LINE": -0.20,
        "PASS_CATCHERS": -0.10,
    },
    "RB": {
        "OFFENSIVE_LINE": -0.22,
        "PASS_CATCHERS": 0.04,
    },
    "WR": {
        "PASS_CATCHERS": 0.12,
        "OFFENSIVE_LINE": -0.08,
        "QB": -0.18,
    },
    "TE": {
        "PASS_CATCHERS": 0.10,
        "OFFENSIVE_LINE": -0.06,
        "QB": -0.15,
    },
}


def calculate_offensive_ripple(
    position,
    offensive_line_impact=0.0,
    pass_catcher_impact=0.0,
    qb_impact=0.0,
):
    """
    Calculate a basic fantasy ripple adjustment.

    Positive number:
        possible fantasy opportunity boost

    Negative number:
        possible fantasy environment downgrade
    """

    position = str(position).upper().strip()

    weights = OFFENSIVE_RIPPLE_WEIGHTS.get(
        position,
        {},
    )

    adjustment = 0.0

    adjustment += (
        offensive_line_impact
        * weights.get("OFFENSIVE_LINE", 0.0)
    )

    adjustment += (
        pass_catcher_impact
        * weights.get("PASS_CATCHERS", 0.0)
    )

    adjustment += (
        qb_impact
        * weights.get("QB", 0.0)
    )

    return round(adjustment, 2)


def build_team_offensive_ripple(injury_df):
    """
    Convert player injury impacts into team-level offensive ripple inputs.

    Returns one row per team with:
    - QB injury impact
    - offensive line injury impact
    - pass catcher injury impact
    - backfield injury impact
    """

    df = injury_df.copy()

    required_columns = {
        "team",
        "injury_unit",
        "player_injury_impact",
    }

    missing = required_columns - set(df.columns)

    if missing:
        raise ValueError(
            f"Missing required columns: {sorted(missing)}"
        )

    grouped = (
        df
        .groupby(
            ["team", "injury_unit"],
            as_index=False,
        )
        .agg(
            unit_injury_impact=(
                "player_injury_impact",
                "sum",
            )
        )
    )

    pivot = (
        grouped
        .pivot(
            index="team",
            columns="injury_unit",
            values="unit_injury_impact",
        )
        .fillna(0.0)
        .reset_index()
    )

    rename_map = {
        "QB": "qb_injury_impact",
        "OFFENSIVE_LINE": "offensive_line_injury_impact",
        "PASS_CATCHERS": "pass_catcher_injury_impact",
        "BACKFIELD": "backfield_injury_impact",
    }

    pivot = pivot.rename(
        columns=rename_map
    )

    expected_columns = [
        "qb_injury_impact",
        "offensive_line_injury_impact",
        "pass_catcher_injury_impact",
        "backfield_injury_impact",
    ]

    for column in expected_columns:
        if column not in pivot.columns:
            pivot[column] = 0.0

    return pivot[
        [
            "team",
            "qb_injury_impact",
            "offensive_line_injury_impact",
            "pass_catcher_injury_impact",
            "backfield_injury_impact",
        ]
    ]

def add_fantasy_ripple_scores(team_ripple_df):
    """
    Convert team injury-unit impacts into fantasy adjustments
    for QB, RB, WR, and TE.

    Positive = opportunity boost
    Negative = fantasy environment downgrade
    """

    df = team_ripple_df.copy()

    df["qb_fantasy_ripple"] = df.apply(
        lambda row: calculate_offensive_ripple(
            position="QB",
            offensive_line_impact=row["offensive_line_injury_impact"],
            pass_catcher_impact=row["pass_catcher_injury_impact"],
            qb_impact=row["qb_injury_impact"],
        ),
        axis=1,
    )

    df["rb_fantasy_ripple"] = df.apply(
        lambda row: calculate_offensive_ripple(
            position="RB",
            offensive_line_impact=row["offensive_line_injury_impact"],
            pass_catcher_impact=row["pass_catcher_injury_impact"],
            qb_impact=row["qb_injury_impact"],
        ),
        axis=1,
    )

    df["wr_fantasy_ripple"] = df.apply(
        lambda row: calculate_offensive_ripple(
            position="WR",
            offensive_line_impact=row["offensive_line_injury_impact"],
            pass_catcher_impact=row["pass_catcher_injury_impact"],
            qb_impact=row["qb_injury_impact"],
        ),
        axis=1,
    )

    df["te_fantasy_ripple"] = df.apply(
        lambda row: calculate_offensive_ripple(
            position="TE",
            offensive_line_impact=row["offensive_line_injury_impact"],
            pass_catcher_impact=row["pass_catcher_injury_impact"],
            qb_impact=row["qb_injury_impact"],
        ),
        axis=1,
    )

    return df


    return round(adjustment, 2)


def ripple_to_projection_multiplier(ripple_score):
    """
    Convert a raw ripple score into a conservative
    projection multiplier.

    Examples:
    -5.0  -> about 0.975
     0.0  -> 1.000
    +5.0  -> about 1.025

    Hard capped so injury ripple never becomes too powerful.
    """

    ripple_score = float(ripple_score)

    adjustment = ripple_score * 0.005

    adjustment = max(
        -0.08,
        min(
            adjustment,
            0.08,
        ),
    )

    return round(
        1.0 + adjustment,
        4,
    )

def add_projection_multipliers(df):
    """
    Add conservative fantasy projection multipliers
    for each offensive position.
    """

    df = df.copy()

    df["qb_ripple_multiplier"] = (
        df["qb_fantasy_ripple"]
        .apply(ripple_to_projection_multiplier)
    )

    df["rb_ripple_multiplier"] = (
        df["rb_fantasy_ripple"]
        .apply(ripple_to_projection_multiplier)
    )

    df["wr_ripple_multiplier"] = (
        df["wr_fantasy_ripple"]
        .apply(ripple_to_projection_multiplier)
    )

    df["te_ripple_multiplier"] = (
        df["te_fantasy_ripple"]
        .apply(ripple_to_projection_multiplier)
    )

    return df


