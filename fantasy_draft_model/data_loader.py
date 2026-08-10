import pandas as pd
import nflreadpy as nfl


LAST_SEASON = 2025


def load_weekly_player_stats():
    """
    Download weekly NFL player statistics
    from nflverse for the previous season.
    """

    print("\nDownloading NFL player statistics...")

    stats = nfl.load_player_stats(
        seasons=[LAST_SEASON]
    )

    # nflreadpy returns a Polars DataFrame.
    # Convert it to pandas because the rest
    # of EdgeIQ currently uses pandas.
    stats_df = stats.to_pandas()

    print(
        f"Downloaded {len(stats_df):,} rows."
    )

    return stats_df


def inspect_player_stats(stats_df):
    """
    Show us exactly what columns nflverse
    returned so we know what data is available.
    """

    print("\n====================================")
    print("NFL DATASET INFORMATION")
    print("====================================")

    print(
        f"\nRows: {len(stats_df):,}"
    )

    print(
        f"Columns: {len(stats_df.columns):,}"
    )

    print("\nAVAILABLE COLUMNS:\n")

    for column in stats_df.columns:
        print(column)

    print("\nFIRST 10 ROWS:\n")

    print(
        stats_df
        .head(10)
        .to_string(
            index=False
        )
    )


def main():

    stats_df = (
        load_weekly_player_stats()
    )

    inspect_player_stats(
        stats_df
    )


if __name__ == "__main__":
    main()