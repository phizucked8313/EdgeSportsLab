"""
EdgeIQ Keeper Adjustment Engine
Version 1

Recalculates rankings after keepers are removed.
"""

import pandas as pd

from fantasy_draft_model.keepers import (
    get_keeper_player_names,
)

from fantasy_draft_model.engines.vorp_engine import (
    calculate_vorp,
)

from fantasy_draft_model.engines.tier_engine import (
    calculate_tiers,
)


def remove_keepers(
    df: pd.DataFrame,
    league_name: str,
) -> pd.DataFrame:
    """
    Remove all keepers for a league
    from the available draft pool.
    """

    keeper_names = (
        get_keeper_player_names(
            league_name
        )
    )

    keeper_names_lower = {
        name.lower()
        for name in keeper_names
    }

    available = df[
        ~df[
            "player_name_clean"
        ]
        .str.lower()
        .isin(
            keeper_names_lower
        )
    ].copy()

    return available


def recalculate_after_keepers(
    df: pd.DataFrame,
    league_name: str,
) -> pd.DataFrame:
    """
    Remove keepers and recalculate:
    - VORP
    - position ranks
    - tiers
    - tier scarcity
    """

    df = remove_keepers(
        df,
        league_name
    )

    df = calculate_vorp(
        df
    )

    df = calculate_tiers(
        df
    )

    return df


def main():

    print(
        "EdgeIQ Keeper Adjustment Engine ready."
    )


if __name__ == "__main__":
    main()