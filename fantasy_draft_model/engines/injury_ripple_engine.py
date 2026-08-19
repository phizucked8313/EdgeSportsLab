import pandas as pd


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


OPPORTUNITY_TRANSFER_POSITIONS = {"RB", "WR", "TE"}
MAX_OPPORTUNITY_BOOST = 0.06
OPPORTUNITY_BOOST_PER_IMPACT_POINT = 0.01


def calculate_offensive_ripple(
    position,
    offensive_line_impact=0.0,
    pass_catcher_impact=0.0,
    qb_impact=0.0,
):
    position = str(position).upper().strip()
    weights = OFFENSIVE_RIPPLE_WEIGHTS.get(position, {})

    adjustment = 0.0
    adjustment += (
        offensive_line_impact
        * weights.get("OFFENSIVE_LINE", 0.0)
    )
    adjustment += (
        pass_catcher_impact
        * weights.get("PASS_CATCHERS", 0.0)
    )
    adjustment += qb_impact * weights.get("QB", 0.0)

    return round(adjustment, 2)


def build_team_offensive_ripple(injury_df):
    df = injury_df.copy()

    required_columns = {
        "team",
        "injury_unit",
        "player_injury_impact",
    }
    missing = required_columns - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    grouped = (
        df.groupby(["team", "injury_unit"], as_index=False)
        .agg(unit_injury_impact=("player_injury_impact", "sum"))
    )

    pivot = (
        grouped.pivot(
            index="team",
            columns="injury_unit",
            values="unit_injury_impact",
        )
        .fillna(0.0)
        .reset_index()
    )

    pivot = pivot.rename(
        columns={
            "QB": "qb_injury_impact",
            "OFFENSIVE_LINE": "offensive_line_injury_impact",
            "PASS_CATCHERS": "pass_catcher_injury_impact",
            "BACKFIELD": "backfield_injury_impact",
        }
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


def ripple_to_projection_multiplier(ripple_score):
    ripple_score = float(ripple_score)
    adjustment = ripple_score * 0.005
    adjustment = max(-0.08, min(adjustment, 0.08))
    return round(1.0 + adjustment, 4)


def add_projection_multipliers(df):
    df = df.copy()

    df["qb_ripple_multiplier"] = df["qb_fantasy_ripple"].apply(
        ripple_to_projection_multiplier
    )
    df["rb_ripple_multiplier"] = df["rb_fantasy_ripple"].apply(
        ripple_to_projection_multiplier
    )
    df["wr_ripple_multiplier"] = df["wr_fantasy_ripple"].apply(
        ripple_to_projection_multiplier
    )
    df["te_ripple_multiplier"] = df["te_fantasy_ripple"].apply(
        ripple_to_projection_multiplier
    )

    return df


def _normalize_player_name(value):
    if pd.isna(value):
        return ""
    return "".join(
        character.lower()
        for character in str(value)
        if character.isalnum()
    )


def add_player_opportunity_ripple(player_df, injury_df):
    """
    Add a conservative opportunity boost to healthy fantasy teammates
    when an RB, WR, or TE on the same team/position is injured.

    The injured player never receives their own opportunity boost.
    """

    players = player_df.copy()
    players["injury_opportunity_multiplier"] = 1.0

    if players.empty or injury_df.empty:
        return players

    player_required = {"player_name_clean", "team", "position"}
    injury_required = {
        "player_name",
        "team",
        "position",
        "player_injury_impact",
    }

    missing_players = player_required - set(players.columns)
    missing_injuries = injury_required - set(injury_df.columns)
    if missing_players:
        raise ValueError(
            f"Missing player columns: {sorted(missing_players)}"
        )
    if missing_injuries:
        raise ValueError(
            f"Missing injury columns: {sorted(missing_injuries)}"
        )

    injuries = injury_df.copy()
    injuries["position"] = injuries["position"].astype(str).str.upper().str.strip()
    injuries["team"] = injuries["team"].astype(str).str.upper().str.strip()
    injuries["_injured_name"] = injuries["player_name"].apply(
        _normalize_player_name
    )
    injuries["player_injury_impact"] = pd.to_numeric(
        injuries["player_injury_impact"],
        errors="coerce",
    ).fillna(0.0)
    injuries = injuries[
        injuries["position"].isin(OPPORTUNITY_TRANSFER_POSITIONS)
        & (injuries["player_injury_impact"] > 0)
    ].copy()

    players["_team_key"] = players["team"].astype(str).str.upper().str.strip()
    players["_position_key"] = (
        players["position"].astype(str).str.upper().str.strip()
    )
    players["_player_name_key"] = players["player_name_clean"].apply(
        _normalize_player_name
    )

    for (team, position), group in injuries.groupby(["team", "position"]):
        total_impact = group["player_injury_impact"].sum()
        boost = min(
            MAX_OPPORTUNITY_BOOST,
            max(0.0, total_impact * OPPORTUNITY_BOOST_PER_IMPACT_POINT),
        )
        if boost <= 0:
            continue

        injured_names = set(group["_injured_name"])
        eligible = (
            (players["_team_key"] == team)
            & (players["_position_key"] == position)
            & (~players["_player_name_key"].isin(injured_names))
        )
        players.loc[
            eligible,
            "injury_opportunity_multiplier",
        ] = 1.0 + boost

    return players.drop(
        columns=["_team_key", "_position_key", "_player_name_key"]
    )
