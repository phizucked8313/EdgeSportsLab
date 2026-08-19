import pandas as pd

from fantasy_draft_model.integrations.depth_chart_loader import load_depth_charts


POSITION_IMPACT = {
    "QB": 10.0,
    "RB": 6.0,
    "WR": 5.0,
    "TE": 4.5,
    "LT": 8.5,
    "RT": 7.5,
    "LG": 5.5,
    "RG": 5.5,
    "C": 7.0,
    "G": 5.5,
    "T": 7.0,
    "OL": 6.0,
    "FB": 2.0,
    "DE": 6.0,
    "EDGE": 7.0,
    "DT": 5.0,
    "NT": 4.5,
    "DL": 5.0,
    "LB": 4.5,
    "ILB": 4.5,
    "OLB": 5.0,
    "CB": 6.0,
    "S": 4.5,
    "DB": 5.0,
    "K": 1.5,
    "P": 1.0,
}


STATUS_MULTIPLIER = {
    "Out": 1.00,
    "IR": 1.00,
    "PUP": 1.00,
    "DNR": 1.00,
    "Doubtful": 0.85,
    "Questionable": 0.45,
    "Probable": 0.20,
    "Active": 0.00,
    "Full Participation in Practice": 0.05,
    "Limited Participation in Practice": 0.35,
    "Did Not Participate in Practice": 0.70,
}


ROLE_MULTIPLIER = {
    "STARTER": 1.00,
    "ROTATION": 0.65,
    "BACKUP": 0.35,
    "DEPTH": 0.15,
    "DEEP_DEPTH": 0.05,
    "UNKNOWN": 0.25,
}


def normalize_status(value):
    if pd.isna(value):
        return ""
    return str(value).strip()


def _normalize_name(value):
    if pd.isna(value):
        return ""
    return "".join(
        character.lower()
        for character in str(value)
        if character.isalnum()
    )


def _identity_key(team, player_name, position):
    return (
        str(team).upper().strip(),
        _normalize_name(player_name),
        str(position).upper().strip(),
    )


def get_position_impact(position):
    position = str(position).upper().strip()
    return POSITION_IMPACT.get(position, 3.0)


def get_status_multiplier(report_status=None, practice_status=None):
    report_status = normalize_status(report_status)
    practice_status = normalize_status(practice_status)

    if report_status in STATUS_MULTIPLIER:
        return STATUS_MULTIPLIER[report_status]
    if practice_status in STATUS_MULTIPLIER:
        return STATUS_MULTIPLIER[practice_status]
    return 0.25


def calculate_player_injury_impact(
    position,
    report_status=None,
    practice_status=None,
    role="STARTER",
):
    base_impact = get_position_impact(position)
    status_multiplier = get_status_multiplier(
        report_status,
        practice_status,
    )
    role_multiplier = ROLE_MULTIPLIER.get(
        str(role).upper(),
        0.50,
    )

    return round(
        base_impact * status_multiplier * role_multiplier,
        2,
    )


def classify_unit(position):
    position = str(position).upper().strip()

    if position == "QB":
        return "QB"
    if position in {"RB", "FB"}:
        return "BACKFIELD"
    if position in {"WR", "TE"}:
        return "PASS_CATCHERS"
    if position in {"LT", "RT", "LG", "RG", "C", "G", "T", "OL"}:
        return "OFFENSIVE_LINE"
    if position in {"DE", "EDGE", "DT", "NT", "DL"}:
        return "DEFENSIVE_FRONT"
    if position in {"LB", "ILB", "OLB"}:
        return "LINEBACKERS"
    if position in {"CB", "S", "DB"}:
        return "SECONDARY"
    if position in {"K", "P"}:
        return "SPECIAL_TEAMS"
    return "OTHER"


def _attach_depth_roles(df, depth_df):
    result = df.copy()
    result["edgeiq_role"] = "UNKNOWN"

    if "gsis_id" in result.columns and "gsis_id" in depth_df.columns:
        gsis_lookup = (
            depth_df[["gsis_id", "edgeiq_role"]]
            .dropna(subset=["gsis_id"])
            .drop_duplicates(subset=["gsis_id"])
            .set_index("gsis_id")["edgeiq_role"]
            .to_dict()
        )
        matched = result["gsis_id"].map(gsis_lookup)
        result.loc[matched.notna(), "edgeiq_role"] = matched[matched.notna()]

    depth_position_column = None
    if "pos_abb" in depth_df.columns:
        depth_position_column = "pos_abb"
    elif "position" in depth_df.columns:
        depth_position_column = "position"

    can_fallback = (
        depth_position_column is not None
        and {"team", "player_name", "position"}.issubset(result.columns)
        and {"team", "player_name", "edgeiq_role"}.issubset(depth_df.columns)
    )

    if can_fallback:
        fallback_lookup = {}
        for row in depth_df.itertuples(index=False):
            key = _identity_key(
                getattr(row, "team"),
                getattr(row, "player_name"),
                getattr(row, depth_position_column),
            )
            fallback_lookup.setdefault(key, getattr(row, "edgeiq_role"))

        unknown_mask = result["edgeiq_role"] == "UNKNOWN"
        fallback_roles = result.loc[unknown_mask].apply(
            lambda row: fallback_lookup.get(
                _identity_key(
                    row["team"],
                    row["player_name"],
                    row["position"],
                ),
                "UNKNOWN",
            ),
            axis=1,
        )
        result.loc[unknown_mask, "edgeiq_role"] = fallback_roles

    return result


def add_team_injury_impact(injuries_df, role_column=None):
    df = injuries_df.copy()

    if "position" not in df.columns:
        df["position"] = "UNKNOWN"
    if "report_status" not in df.columns:
        df["report_status"] = ""
    if "practice_status" not in df.columns:
        df["practice_status"] = ""

    if role_column and role_column in df.columns:
        df["edgeiq_role"] = (
            df[role_column]
            .fillna("UNKNOWN")
            .astype(str)
            .str.upper()
        )
    else:
        df = _attach_depth_roles(df, load_depth_charts())

    df["injury_unit"] = df["position"].apply(classify_unit)
    df["player_injury_impact"] = df.apply(
        lambda row: calculate_player_injury_impact(
            position=row["position"],
            report_status=row["report_status"],
            practice_status=row["practice_status"],
            role=row["edgeiq_role"],
        ),
        axis=1,
    )

    return df


def build_team_injury_summary(injuries_df):
    df = add_team_injury_impact(injuries_df)

    if "team" not in df.columns:
        raise ValueError("injuries_df must contain a 'team' column.")

    summary = (
        df.groupby(["team", "injury_unit"], as_index=False)
        .agg(
            injured_players=("player_injury_impact", "count"),
            unit_injury_impact=("player_injury_impact", "sum"),
        )
    )
    summary["unit_injury_impact"] = summary["unit_injury_impact"].round(2)
    return summary


def build_team_total_impact(injuries_df):
    unit_summary = build_team_injury_summary(injuries_df)

    team_summary = (
        unit_summary.groupby("team", as_index=False)
        .agg(total_injury_impact=("unit_injury_impact", "sum"))
        .sort_values("total_injury_impact", ascending=False)
        .reset_index(drop=True)
    )
    team_summary["total_injury_impact"] = team_summary[
        "total_injury_impact"
    ].round(2)
    return team_summary
