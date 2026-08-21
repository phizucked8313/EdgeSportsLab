from datetime import datetime, timezone

import pandas as pd

from fantasy_draft_model.integrations.sleeper_api import load_sleeper_players
from fantasy_draft_model.models.team_injury_impact_engine import (
    get_status_multiplier,
)


CURRENT_INJURY_STALE_HOURS = 168.0

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


def _practice_status(value):
    cleaned = _clean(value)
    return cleaned if cleaned else "UNKNOWN"


def _bool_value(value, default=False):
    if pd.isna(value):
        return default
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y"}:
            return True
        if normalized in {"false", "0", "no", "n", ""}:
            return False
    return bool(value)


def _parse_timestamp(value):
    cleaned = _clean(value)
    if not cleaned:
        return None
    try:
        parsed = pd.Timestamp(cleaned)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.tz_localize("UTC")
    else:
        parsed = parsed.tz_convert("UTC")
    return parsed


def _calculate_age_hours(source_timestamp, as_of_timestamp):
    source = _parse_timestamp(source_timestamp)
    as_of = _parse_timestamp(as_of_timestamp)
    if source is None or as_of is None:
        return float("nan")
    return max(0.0, (as_of - source).total_seconds() / 3600.0)


def normalize_current_injuries(players_df):
    df = players_df.copy()

    required = [
        "sleeper_id", "gsis_id", "espn_id", "yahoo_id", "player_name",
        "team", "position", "status", "injury_status",
        "injury_body_part", "injury_start_date",
        "practice_participation", "injury_source",
        "injury_source_timestamp", "injury_source_quality",
        "injury_research_override", "injury_is_ambiguous",
        "normalization_as_of",
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
    df["practice_status"] = df["practice_participation"].apply(
        _practice_status
    )
    df["source_injury_body_part"] = df["injury_body_part"].apply(_clean)
    df["edgeiq_injury_body_part"] = df["source_injury_body_part"]

    df["needs_research"] = df["source_injury_body_part"].apply(
        _is_non_specific_body_part
    )
    df["injury_data_quality"] = df["needs_research"].map(
        {True: "F", False: "D"}
    )

    now_iso = datetime.now(timezone.utc).isoformat()
    df["injury_source"] = df["injury_source"].apply(_clean)
    df.loc[df["injury_source"] == "", "injury_source"] = "Sleeper"

    df["injury_source_timestamp"] = df["injury_source_timestamp"].apply(
        _clean
    )
    df["injury_freshness_known"] = df["injury_source_timestamp"].ne("")

    df["injury_source_quality"] = df["injury_source_quality"].apply(_clean)
    missing_quality = df["injury_source_quality"] == ""
    df.loc[missing_quality, "injury_source_quality"] = df.loc[
        missing_quality, "injury_data_quality"
    ]

    df["injury_research_override"] = df[
        "injury_research_override"
    ].apply(_bool_value)
    df["injury_is_ambiguous"] = df["injury_is_ambiguous"].apply(
        _bool_value
    )

    as_of_values = df["normalization_as_of"].apply(_clean)
    as_of_values = as_of_values.where(as_of_values != "", now_iso)
    df["injury_age_hours"] = [
        _calculate_age_hours(source_timestamp, as_of_timestamp)
        for source_timestamp, as_of_timestamp in zip(
            df["injury_source_timestamp"],
            as_of_values,
        )
    ]
    df["injury_is_stale"] = df["injury_age_hours"].apply(
        lambda age: bool(pd.notna(age) and age > CURRENT_INJURY_STALE_HOURS)
    )

    df["injury_severity"] = df.apply(
        lambda row: get_status_multiplier(
            report_status=row["report_status"],
            practice_status=row["practice_status"],
        ),
        axis=1,
    )
    df["current_injury_multiplier"] = df["injury_severity"]

    return df[
        [
            "sleeper_id", "gsis_id", "espn_id", "yahoo_id", "player_name",
            "team", "position", "status", "report_status",
            "practice_status", "source_injury_body_part",
            "edgeiq_injury_body_part", "injury_start_date",
            "needs_research", "injury_data_quality",
            "injury_source", "injury_source_timestamp",
            "injury_age_hours", "injury_is_stale", "injury_freshness_known",
            "injury_source_quality", "injury_research_override",
            "injury_is_ambiguous", "injury_severity",
            "current_injury_multiplier",
        ]
    ]


def attach_current_injury_state(players_df, current_injuries_df):
    """Attach current injury state without altering historical risk metrics."""
    players = players_df.copy()

    defaults = {
        "is_currently_injured": False,
        "current_injury_status": "",
        "current_injury_body_part": "",
        "current_injury_severity": 0.0,
        "current_injury_practice_status": "",
        "current_injury_multiplier": 0.0,
        "current_injury_source_timestamp": "",
        "current_injury_age_hours": float("nan"),
        "current_injury_is_stale": False,
        "current_injury_freshness_known": False,
        "current_injury_source_quality": "",
        "current_injury_research_override": False,
        "current_injury_is_ambiguous": False,
        "current_injury_data_quality": "",
        "current_injury_source": "",
    }
    for column, value in defaults.items():
        players[column] = value

    if players.empty or current_injuries_df.empty:
        return players

    injuries = current_injuries_df.copy()
    injury_columns = [
        "gsis_id",
        "player_name",
        "team",
        "position",
        "report_status",
        "edgeiq_injury_body_part",
        "injury_severity",
        "practice_status",
        "current_injury_multiplier",
        "injury_source_timestamp",
        "injury_age_hours",
        "injury_is_stale",
        "injury_freshness_known",
        "injury_source_quality",
        "injury_research_override",
        "injury_is_ambiguous",
        "injury_data_quality",
        "injury_source",
    ]
    for column in injury_columns:
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
            "current_injury_severity": injury["injury_severity"],
            "current_injury_practice_status": _clean(
                injury["practice_status"]
            ),
            "current_injury_multiplier": injury[
                "current_injury_multiplier"
            ],
            "current_injury_source_timestamp": _clean(
                injury["injury_source_timestamp"]
            ),
            "current_injury_age_hours": injury["injury_age_hours"],
            "current_injury_is_stale": _bool_value(
                injury["injury_is_stale"]
            ),
            "current_injury_freshness_known": _bool_value(
                injury["injury_freshness_known"]
            ),
            "current_injury_source_quality": _clean(
                injury["injury_source_quality"]
            ),
            "current_injury_research_override": _bool_value(
                injury["injury_research_override"]
            ),
            "current_injury_is_ambiguous": _bool_value(
                injury["injury_is_ambiguous"]
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

    boolean_columns = [
        "is_currently_injured",
        "current_injury_is_stale",
        "current_injury_freshness_known",
        "current_injury_research_override",
        "current_injury_is_ambiguous",
    ]
    for column in boolean_columns:
        players[column] = players[column].astype(bool)

    return players


def load_normalized_current_injuries():
    return normalize_current_injuries(load_sleeper_players())
