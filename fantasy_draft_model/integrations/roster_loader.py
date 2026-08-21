from pathlib import Path

import nflreadpy as nfl
import pandas as pd


CURRENT_SEASON = 2026
CURRENT_ROSTER_OVERRIDE_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "current_roster_overrides.csv"
)

FANTASY_POSITIONS = [
    "QB",
    "RB",
    "WR",
    "TE",
]


def apply_current_roster_overrides(df, overrides_df=None):
    """Apply verified transactions that are fresher than the roster feed."""
    result = df.copy()
    overrides = (
        pd.read_csv(CURRENT_ROSTER_OVERRIDE_PATH)
        if overrides_df is None and CURRENT_ROSTER_OVERRIDE_PATH.exists()
        else (pd.DataFrame() if overrides_df is None else overrides_df.copy())
    )
    defaults = {
        "is_unsigned_free_agent": False,
        "prior_roster_team": "",
        "roster_status_provenance": "",
        "roster_status_source": "",
        "roster_status_source_date": "",
        "roster_status_retrieved_at": "",
    }
    for column, default in defaults.items():
        if column not in result:
            result[column] = default
    if result.empty or overrides.empty:
        return result
    lookup = {
        str(row.get("gsis_id", "")).strip(): row
        for _, row in overrides.iterrows()
        if str(row.get("gsis_id", "")).strip()
    }
    for index, player in result.iterrows():
        override = lookup.get(str(player.get("gsis_id", "")).strip())
        if override is None:
            continue
        prior_team = str(override.get("prior_team") or player.get("team") or "").strip()
        status = str(override.get("status") or "Released").strip()
        result.at[index, "prior_roster_team"] = prior_team
        result.at[index, "status"] = status
        result.at[index, "roster_status_provenance"] = status
        result.at[index, "roster_status_source"] = str(override.get("source_url") or "").strip()
        result.at[index, "roster_status_source_date"] = str(override.get("source_date") or "").strip()
        result.at[index, "roster_status_retrieved_at"] = str(override.get("retrieved_at") or "").strip()
        result.at[index, "is_unsigned_free_agent"] = True
        result.at[index, "team"] = pd.NA
    result["is_unsigned_free_agent"] = result["is_unsigned_free_agent"].astype(bool)
    return result


def add_rookie_identity(df, current_season=CURRENT_SEASON):
    """
    Add EdgeIQ's canonical rookie identity flag.

    A player is a rookie only when current roster metadata says
    rookie_year equals the current NFL season. Missing historical
    statistics or zero years of experience do not define rookie status.
    """

    df = df.copy()

    if "rookie_year" not in df.columns:
        df["is_rookie"] = False
        return df

    rookie_year = pd.to_numeric(
        df["rookie_year"],
        errors="coerce",
    )

    df["is_rookie"] = rookie_year.eq(current_season)

    return df


def load_current_rosters(roster_loader=None):
    """
    Load current NFL roster information for EdgeIQ.

    This is used to attach current-season identity information
    to the historical statistics used by the projection engine.
    """

    print(
        f"\nLoading {CURRENT_SEASON} NFL rosters..."
    )

    if roster_loader is None:
        roster_loader = nfl.load_rosters

    rosters = roster_loader(
        seasons=[CURRENT_SEASON]
    )

    # nflreadpy currently returns a Polars DataFrame.
    # EdgeIQ uses pandas throughout the model.
    rosters = rosters.to_pandas()

    print(
        f"Downloaded {len(rosters):,} roster rows."
    )

    return rosters


def prepare_fantasy_rosters():
    """
    Clean the current NFL roster data and keep
    fantasy-relevant offensive players.
    """

    df = load_current_rosters()

    # Keep fantasy positions only
    df = df[
        df["position"].isin(FANTASY_POSITIONS)
    ].copy()

    # Keep the fields EdgeIQ needs
    columns = [
        "gsis_id",
        "espn_id",
        "sleeper_id",
        "full_name",
        "first_name",
        "last_name",
        "team",
        "position",
        "depth_chart_position",
        "status",
        "years_exp",
        "entry_year",
        "rookie_year",
        "draft_club",
        "draft_number",
    ]

    df = df[columns].copy()

    # EdgeIQ standard player-name field
    df["player_name_clean"] = (
        df["full_name"]
        .fillna("")
        .str.strip()
    )

    # Canonical current-season rookie identity
    df = add_rookie_identity(
        df,
        current_season=CURRENT_SEASON,
    )

    df = apply_current_roster_overrides(df)

    # Remove duplicate roster records
    df = (
        df
        .drop_duplicates(
            subset=["gsis_id", "full_name"],
            keep="first",
        )
        .reset_index(drop=True)
    )

    return df


def main():

    df = prepare_fantasy_rosters()

    print(
        "\n============================================"
    )

    print(
        "EDGEIQ 2026 FANTASY ROSTERS"
    )

    print(
        "============================================\n"
    )

    display_columns = [
        "player_name_clean",
        "position",
        "team",
        "status",
        "years_exp",
        "is_rookie",
    ]

    print(
        df[
            display_columns
        ]
        .head(50)
        .to_string(index=False)
    )

    print(
        f"\nFantasy players loaded: {len(df):,}"
    )


if __name__ == "__main__":
    main()
