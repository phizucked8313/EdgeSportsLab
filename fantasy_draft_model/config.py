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


def load_league_settings():
    """
    Load EdgeIQ fantasy league settings
    from league_settings.json.
    """

    with open(
        LEAGUE_SETTINGS_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        settings = json.load(file)

    return settings