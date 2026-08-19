from datetime import datetime, timezone

import pandas as pd

from fantasy_draft_model.integrations.sleeper_api import load_sleeper_players


NON_SPECIFIC_BODY_PARTS = {
    "",
    "nan",
    "none",
    "unknown",
    "undisclosed",
    "lower body",
    "upper body",
}


def _clean(value):
    if pd.isna(value):
        return ""
    return str(value).strip()


def _is_non_specific_body_part(value):
    return _clean(value).lower() in NON_SPECIFIC_BODY_PARTS


def normalize_current_injuries(players_df):
    df = players_df.copy()

    required = [
        "sleeper_id", "gsis_id", "espn_id", "yahoo_id", "player_name",
        "team", "position", "status", "injury_status",
        "injury_body_part", "injury_start_date",
        "practice_participation",
    ]
    for column in required:
        if column not in df.columns:
            df[column] = None

    injury_mask = (
        df["injury_status"].notna()
        | df["injury_body_part"].notna()
        | df["practice_participation"].notna()
        | df["injury_start_date"].notna()
    )
    df = df.loc[injury_mask].copy().reset_index(drop=True)

    df["report_status"] = df["injury_status"].apply(_clean)
    df["practice_status"] = df["practice_participation"].apply(_clean)
    df["source_injury_body_part"] = df["injury_body_part"].apply(_clean)
    df["edgeiq_injury_body_part"] = df["source_injury_body_part"]

    df["needs_research"] = df["source_injury_body_part"].apply(
        _is_non_specific_body_part
    )
    df["injury_data_quality"] = df["needs_research"].map(
        {True: "F", False: "D"}
    )
    df["injury_source"] = "Sleeper"
    df["injury_source_timestamp"] = datetime.now(timezone.utc).isoformat()

    return df[
        [
            "sleeper_id", "gsis_id", "espn_id", "yahoo_id", "player_name",
            "team", "position", "status", "report_status",
            "practice_status", "source_injury_body_part",
            "edgeiq_injury_body_part", "injury_start_date",
            "needs_research", "injury_data_quality",
            "injury_source", "injury_source_timestamp",
        ]
    ]


def load_normalized_current_injuries():
    return normalize_current_injuries(load_sleeper_players())
