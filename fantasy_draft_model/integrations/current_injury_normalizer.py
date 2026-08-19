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


def _identity_text(value):
    if pd.isna(value):
        return ""
    return "".join(
        character.lower()
        for character in str(value)
        if character.isalnum()
    )


def _identity_code(value):
    return _clean(value).upper()


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


def attach_current_injury_state(players_df, current_injuries_df):
    """Attach current injury state without altering historical risk metrics."""
    players = players_df.copy()

    players["is_currently_injured"] = False
    players["current_injury_status"] = ""
    players["current_injury_body_part"] = ""
    players["current_injury_data_quality"] = ""
    players["current_injury_source"] = ""

    if players.empty or current_injuries_df.empty:
        return players

    injuries = current_injuries_df.copy()
    for column in [
        "gsis_id",
        "player_name",
        "team",
        "position",
        "report_status",
        "edgeiq_injury_body_part",
        "injury_data_quality",
        "injury_source",
    ]:
        if column not in injuries.columns:
            injuries[column] = None

    gsis_lookup = {}
    fallback_lookup = {}

    for _, injury in injuries.iterrows():
        record = {
            "current_injury_status": _clean(injury["report_status"]),
            "current_injury_body_part": _clean(
                injury["edgeiq_injury_body_part"]
            ),
            "current_injury_data_quality": _clean(
                injury["injury_data_quality"]
            ),
            "current_injury_source": _clean(injury["injury_source"]),
        }

        gsis_id = _clean(injury["gsis_id"])
        if gsis_id and gsis_id not in gsis_lookup:
            gsis_lookup[gsis_id] = record

        fallback_key = (
            _identity_text(injury["player_name"]),
            _identity_code(injury["team"]),
            _identity_code(injury["position"]),
        )
        if all(fallback_key) and fallback_key not in fallback_lookup:
            fallback_lookup[fallback_key] = record

    for index, player in players.iterrows():
        match = None

        player_id = _clean(player.get("player_id"))
        if player_id:
            match = gsis_lookup.get(player_id)

        if match is None:
            fallback_key = (
                _identity_text(player.get("player_name_clean")),
                _identity_code(player.get("team")),
                _identity_code(player.get("position")),
            )
            if all(fallback_key):
                match = fallback_lookup.get(fallback_key)

        if match is None:
            continue

        players.at[index, "is_currently_injured"] = True
        for column, value in match.items():
            players.at[index, column] = value

    players["is_currently_injured"] = players[
        "is_currently_injured"
    ].astype(bool)

    return players


def load_normalized_current_injuries():
    return normalize_current_injuries(load_sleeper_players())
