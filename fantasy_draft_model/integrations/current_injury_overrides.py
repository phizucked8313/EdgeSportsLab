from pathlib import Path

import pandas as pd


DEFAULT_OVERRIDE_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "current_injury_overrides.csv"
)


def _identity_text(value):
    if pd.isna(value):
        return ""
    return "".join(
        character.lower()
        for character in str(value)
        if character.isalnum()
    )


def _identity_code(value):
    if pd.isna(value):
        return ""
    return str(value).strip().upper()


def _clean_text(value):
    if pd.isna(value):
        return ""
    return str(value).strip()


def _bool_value(value):
    if pd.isna(value):
        return False
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y"}
    return bool(value)


def load_current_injury_overrides(path=None):
    """Load verified current-injury timeline research maintained by EdgeIQ."""
    source_path = Path(path) if path is not None else DEFAULT_OVERRIDE_PATH
    if not source_path.exists():
        return pd.DataFrame()
    return pd.read_csv(source_path)


def attach_current_injury_overrides(players_df, overrides_df=None):
    """Attach only explicit verified injury-timeline records to matching players."""
    players = players_df.copy()

    defaults = {
        "current_injury_expected_games_missed": float("nan"),
        "current_injury_expected_return": "",
        "current_injury_season_ending": False,
        "current_injury_timeline_source": "",
        "current_injury_timeline_source_date": "",
        "current_injury_timeline_note": "",
    }
    for column, value in defaults.items():
        if column not in players.columns:
            players[column] = value

    if "is_currently_injured" not in players.columns:
        players["is_currently_injured"] = False
    if "current_injury_research_override" not in players.columns:
        players["current_injury_research_override"] = False
    if "current_injury_body_part" not in players.columns:
        players["current_injury_body_part"] = ""

    overrides = (
        load_current_injury_overrides()
        if overrides_df is None
        else overrides_df.copy()
    )
    if players.empty or overrides.empty:
        return players

    required = {
        "player_name": "",
        "team": "",
        "position": "",
        "injury_body_part": "",
        "expected_games_missed": float("nan"),
        "expected_return": "",
        "season_ending": False,
        "source_url": "",
        "source_date": "",
        "note": "",
    }
    for column, default in required.items():
        if column not in overrides.columns:
            overrides[column] = default

    lookup = {}
    for _, row in overrides.iterrows():
        key = (
            _identity_text(row["player_name"]),
            _identity_code(row["team"]),
            _identity_code(row["position"]),
        )
        if not all(key):
            continue
        lookup[key] = row

    for index, player in players.iterrows():
        key = (
            _identity_text(player.get("player_name_clean")),
            _identity_code(player.get("team")),
            _identity_code(player.get("position")),
        )
        override = lookup.get(key)
        if override is None:
            continue

        players.at[index, "is_currently_injured"] = True
        players.at[index, "current_injury_research_override"] = True

        body_part = _clean_text(override.get("injury_body_part"))
        if body_part:
            players.at[index, "current_injury_body_part"] = body_part

        expected_games = pd.to_numeric(
            override.get("expected_games_missed"),
            errors="coerce",
        )
        players.at[index, "current_injury_expected_games_missed"] = (
            float(expected_games) if pd.notna(expected_games) else float("nan")
        )
        players.at[index, "current_injury_expected_return"] = _clean_text(
            override.get("expected_return")
        )
        players.at[index, "current_injury_season_ending"] = _bool_value(
            override.get("season_ending")
        )
        players.at[index, "current_injury_timeline_source"] = _clean_text(
            override.get("source_url")
        )
        players.at[index, "current_injury_timeline_source_date"] = _clean_text(
            override.get("source_date")
        )
        players.at[index, "current_injury_timeline_note"] = _clean_text(
            override.get("note")
        )

    players["is_currently_injured"] = players[
        "is_currently_injured"
    ].astype(bool)
    players["current_injury_research_override"] = players[
        "current_injury_research_override"
    ].astype(bool)
    players["current_injury_season_ending"] = players[
        "current_injury_season_ending"
    ].astype(bool)
    return players
