from pathlib import Path
import json


BASE_DIR = Path(__file__).resolve().parent

CONFIG_DIR = BASE_DIR / "config"
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"

LEAGUE_SETTINGS_FILE = CONFIG_DIR / "league_settings.json"
KEEPERS_FILE = DATA_DIR / "keepers.csv"

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


def load_league_settings(league_key: str):
    """
    Load one explicit EdgeIQ fantasy league profile.

    A league key is always required so scoring/economics can never
    silently fall back to the wrong Yahoo league.
    """

    with open(
        LEAGUE_SETTINGS_FILE,
        "r",
        encoding="utf-8"
    ) as file:
        root = json.load(file)

    profiles = root["league_profiles"]

    if league_key not in profiles:
        valid = ", ".join(sorted(profiles))
        raise ValueError(
            f"Unknown league_key {league_key!r}. "
            f"Valid league keys: {valid}"
        )

    profile = profiles[league_key]

    return {
        "season": root["season"],
        "teams": root["teams"],
        "lineup": root["lineup"],
        "league_key": league_key,
        "league_name": profile["league_name"],
        "league_id": profile["league_id"],
        "keeper_league": profile["keeper_league"],
        "scoring": profile["scoring"],
    }
