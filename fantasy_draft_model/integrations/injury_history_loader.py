import pandas as pd
import nflreadpy as nfl


CURRENT_SEASON = 2026


def load_current_injuries():
    """
    Load current-season NFL injury reports.

    Includes ALL positions:
    offense, offensive line, defense, and special teams.
    """

    print("\nLoading current NFL injuries...")

    injuries = nfl.load_injuries(
        seasons=[CURRENT_SEASON]
    )

    injuries = injuries.to_pandas()

    print(
        f"Downloaded {len(injuries):,} injury rows."
    )

    # Keep only the latest injury record for each player.
    # NFL injury data contains repeated weekly/practice reports.

    sort_columns = [
        column
        for column in ["season", "week"]
        if column in injuries.columns
    ]

    if sort_columns:
        injuries = injuries.sort_values(
            sort_columns,
            ascending=True,
        )

    if "gsis_id" in injuries.columns:
        injuries = (
            injuries
            .dropna(subset=["gsis_id"])
            .drop_duplicates(
                subset=["gsis_id"],
                keep="last",
            )
            .reset_index(drop=True)
        )


    return injuries


def inspect_current_injuries():
    """
    Display the injury dataset structure so EdgeIQ
    knows exactly which fields are available.
    """

    injuries = load_current_injuries()

    print("\n======================================")
    print("EDGEIQ CURRENT INJURY DATA")
    print("======================================\n")

    print("Columns:")
    print(injuries.columns.tolist())

    print("\nSample:")
    print(
        injuries
        .head(50)
        .to_string(index=False)
    )


def main():
    inspect_current_injuries()


if __name__ == "__main__":
    main()