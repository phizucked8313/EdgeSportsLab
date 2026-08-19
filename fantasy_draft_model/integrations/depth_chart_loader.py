import pandas as pd
import nflreadpy as nfl


DEPTH_CHART_SEASON = 2025


def load_depth_charts():
    """
    Load NFL weekly depth charts.

    We are using the latest season currently supported
    by the nflverse depth-chart dataset on this machine.
    """

    print("\nLoading NFL depth charts...")

    depth = nfl.load_depth_charts(
        seasons=[DEPTH_CHART_SEASON]
    )

    depth = depth.to_pandas()

    depth = add_edgeiq_depth_roles(depth)

    

    print(
        f"Downloaded {len(depth):,} depth-chart rows."
    )

    return depth


def inspect_depth_charts():
    """
    Inspect available depth-chart columns and sample rows.
    """

    depth = load_depth_charts()

    print("\n======================================")
    print("EDGEIQ NFL DEPTH CHART DATA")
    print("======================================\n")

    print("COLUMNS:")
    print(depth.columns.tolist())

    print("\nSAMPLE:")
    columns = [
    "team",
    "player_name",
    "pos_name",
    "pos_abb",
    "pos_rank",
    "edgeiq_role",
]

    print(
        depth[columns]
        .head(100)
        .to_string(index=False)
    )



def add_edgeiq_depth_roles(depth):
    """
    Convert NFL depth-chart rank into EdgeIQ role classifications.
    """

    df = depth.copy()

    df["pos_rank"] = pd.to_numeric(
        df["pos_rank"],
        errors="coerce"
    )

    def classify_role(rank):
        if pd.isna(rank):
            return "UNKNOWN"

        if rank == 1:
            return "STARTER"

        if rank == 2:
            return "BACKUP"

        if rank == 3:
            return "DEPTH"

        return "DEEP_DEPTH"

    df["edgeiq_role"] = (
        df["pos_rank"]
        .apply(classify_role)
    )

    return df




def main():
    inspect_depth_charts()


if __name__ == "__main__":
    main()







