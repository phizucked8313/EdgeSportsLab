"""
EdgeIQ Keeper Engine
Version 1

Tracks league keepers and removes them from
the available draft pool before the draft starts.
"""

import pandas as pd
from pathlib import Path

from fantasy_draft_model.models.league_profile import get_league


KEEPER_FILE = (
    Path(__file__).parent
    / "data"
    / "keepers.csv"
)


KEEPER_COLUMNS = [
    "league_name",
    "owner_team",
    "player_name",
    "keeper_type",
    "keeper_round",
]


# ============================================================
# CREATE FILE IF NEEDED
# ============================================================

def ensure_keeper_file():

    KEEPER_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    if not KEEPER_FILE.exists():

        empty_df = pd.DataFrame(
            columns=KEEPER_COLUMNS
        )

        empty_df.to_csv(
            KEEPER_FILE,
            index=False
        )


# ============================================================
# LOAD KEEPERS
# ============================================================

def load_keepers(
    league_name=None
):

    ensure_keeper_file()

    df = pd.read_csv(
        KEEPER_FILE
    )

    if league_name is not None:

        df = df[
            df["league_name"]
            .str.lower()
            == league_name.lower()
        ].copy()

    return df


# ============================================================
# ADD KEEPER
# ============================================================

def add_keeper(
    league_name,
    owner_team,
    player_name,
    keeper_type
):

    ensure_keeper_file()

    df = load_keepers()

    league = get_league(league_name)
    if league is None:
        raise ValueError(
            f"Unknown league_name {league_name!r}"
        )

    keeper_type = (
        keeper_type
        .strip()
        .lower()
    )

    keeper_rules = league["keeper_rules"]

    if keeper_type not in keeper_rules:
        valid = ", ".join(sorted(keeper_rules))
        raise ValueError(
            f"keeper_type {keeper_type!r} is not allowed for "
            f"{league_name}. Valid keeper types: {valid}"
        )

    keeper_round = int(
        keeper_rules[keeper_type]
    )


    duplicate = (

        (
            df["league_name"]
            .str.lower()
            == league_name.lower()
        )

        &

        (
            df["player_name"]
            .str.lower()
            == player_name.lower()
        )

    ).any()


    if duplicate:

        print(
            f"\n{player_name} is already "
            f"listed as a keeper."
        )

        return


    new_keeper = pd.DataFrame(
        [
            {
                "league_name":
                    league_name,

                "owner_team":
                    owner_team,

                "player_name":
                    player_name,

                "keeper_type":
                    keeper_type,

                "keeper_round":
                    keeper_round,
            }
        ]
    )


    df = pd.concat(
        [
            df,
            new_keeper
        ],
        ignore_index=True
    )


    df.to_csv(
        KEEPER_FILE,
        index=False
    )


    print(
        f"\nAdded keeper: "
        f"{player_name}"
    )

    print(
        f"League: "
        f"{league_name}"
    )

    print(
        f"Team: "
        f"{owner_team}"
    )

    print(
        f"Type: "
        f"{keeper_type}"
    )

    print(
        f"Cost: "
        f"Round {keeper_round}"
    )


# ============================================================
# GET KEEPER PLAYER NAMES
# ============================================================

def get_keeper_player_names(
    league_name
):

    df = load_keepers(
        league_name
    )

    return (
        df["player_name"]
        .dropna()
        .tolist()
    )


# ============================================================
# SHOW KEEPERS
# ============================================================

def show_keepers(
    league_name
):

    df = load_keepers(
        league_name
    )


    print(
        "\n===================================="
    )

    print(
        f"EDGEIQ KEEPERS - "
        f"{league_name}"
    )

    print(
        "====================================\n"
    )


    if df.empty:

        print(
            "No keepers entered yet."
        )

        return


    print(
        df[
            [
                "owner_team",
                "player_name",
                "keeper_type",
                "keeper_round",
            ]
        ]
        .to_string(
            index=False
        )
    )


if __name__ == "__main__":

    show_keepers(
        "Drunk Sundays"
    )
