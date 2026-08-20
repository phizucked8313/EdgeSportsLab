import requests
import pandas as pd

from fantasy_draft_model.rankings_snapshot import (
    DRAFT_NIGHT_CONNECT_TIMEOUT_SECONDS,
    DRAFT_NIGHT_READ_TIMEOUT_SECONDS,
)


SLEEPER_PLAYERS_URL = "https://api.sleeper.app/v1/players/nfl"
SLEEPER_CONNECT_TIMEOUT_SECONDS = DRAFT_NIGHT_CONNECT_TIMEOUT_SECONDS
SLEEPER_READ_TIMEOUT_SECONDS = DRAFT_NIGHT_READ_TIMEOUT_SECONDS

FANTASY_POSITIONS = {
    "QB",
    "RB",
    "WR",
    "TE",
}


def load_sleeper_players():
    """Download the current NFL player database from Sleeper."""

    print("\nLoading Sleeper NFL player data...")

    response = requests.get(
        SLEEPER_PLAYERS_URL,
        timeout=(
            SLEEPER_CONNECT_TIMEOUT_SECONDS,
            SLEEPER_READ_TIMEOUT_SECONDS,
        ),
    )
    response.raise_for_status()

    players = response.json()
    rows = []

    for sleeper_id, player in players.items():
        position = player.get("position")
        team = player.get("team")

        if team and position in FANTASY_POSITIONS:
            rows.append(
                {
                    "sleeper_id": sleeper_id,
                    "gsis_id": player.get("gsis_id"),
                    "player_name": player.get("full_name"),
                    "team": team,
                    "position": position,
                    "status": player.get("status"),
                    "injury_status": player.get("injury_status"),
                    "injury_body_part": player.get("injury_body_part"),
                    "injury_start_date": player.get("injury_start_date"),
                    "practice_participation": player.get("practice_participation"),
                    "depth_chart_position": player.get("depth_chart_position"),
                    "depth_chart_order": player.get("depth_chart_order"),
                    "espn_id": player.get("espn_id"),
                    "yahoo_id": player.get("yahoo_id"),
                }
            )

    df = pd.DataFrame(rows)

    print(
        f"Loaded {len(df):,} active-team "
        "QB/RB/WR/TE players."
    )

    return df


def load_current_injuries():
    """Return current fantasy-relevant players with injury data."""

    players = load_sleeper_players()

    injury_mask = (
        players["injury_status"].notna()
        | players["injury_body_part"].notna()
        | players["practice_participation"].notna()
        | players["injury_start_date"].notna()
    )

    injuries = players.loc[injury_mask].copy().reset_index(drop=True)

    print(
        f"Found {len(injuries):,} players "
        "with current injury data."
    )

    return injuries


def main():
    injuries = load_current_injuries()

    print("\nEDGEIQ — SLEEPER CURRENT INJURIES")
    print("=" * 80)

    if injuries.empty:
        print("No current injuries found.")
        return

    display_columns = [
        "player_name",
        "team",
        "position",
        "status",
        "injury_status",
        "injury_body_part",
        "practice_participation",
    ]

    print(injuries[display_columns].to_string(index=False))


if __name__ == "__main__":
    main()
