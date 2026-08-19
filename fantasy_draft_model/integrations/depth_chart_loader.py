import pandas as pd
import nflreadpy as nfl


def load_depth_charts():
    """
    Load the current NFL depth charts and keep each team's latest snapshot.
    """

    print("\nLoading NFL depth charts...")

    depth = nfl.load_depth_charts()
    depth = depth.to_pandas()

    depth["dt"] = pd.to_datetime(
        depth["dt"],
        errors="coerce",
        utc=True,
    )

    latest_dt = depth.groupby("team")["dt"].transform("max")
    depth = depth[depth["dt"] == latest_dt].copy()
    depth = depth.reset_index(drop=True)

    depth = add_edgeiq_depth_roles(depth)

    print(
        f"Downloaded {len(depth):,} current depth-chart rows."
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
