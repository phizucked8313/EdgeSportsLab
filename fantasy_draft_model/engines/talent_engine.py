import pandas as pd


CURRENT_SEASON = 2026


def calculate_rookie_talent_score(df):
    """
    Add a rookie talent score to the EdgeIQ player pool.

    Version 1 uses NFL draft capital as the primary signal.

    Higher score = stronger rookie prospect profile.
    Veterans receive a neutral score of 50.
    """

    df = df.copy()

    df["rookie_talent_score"] = 50.0

    if "is_rookie" not in df.columns:
        return df

    rookie_mask = df["is_rookie"] == True

    for index in df[rookie_mask].index:

        draft_number = df.at[index, "draft_number"]

        # Undrafted or missing draft information
        if pd.isna(draft_number) or draft_number <= 0:
            score = 35.0

        # Round 1
        elif draft_number <= 32:
            score = 95.0

        # Round 2
        elif draft_number <= 64:
            score = 85.0

        # Round 3
        elif draft_number <= 100:
            score = 75.0

        # Round 4
        elif draft_number <= 135:
            score = 65.0

        # Round 5
        elif draft_number <= 175:
            score = 55.0

        # Round 6
        elif draft_number <= 215:
            score = 45.0

        # Round 7
        else:
            score = 40.0

        df.at[index, "rookie_talent_score"] = score

    return df


def add_rookie_baseline_projection(df):
    """
    Create a simple rookie baseline fantasy projection.

    Version 1 uses:
    - rookie talent score
    - position
    - draft capital indirectly through talent score

    This is only a starter model.
    """

    df = df.copy()

    if "is_rookie" not in df.columns:
        return df

    if "rookie_talent_score" not in df.columns:
        return df

    rookie_mask = df["is_rookie"] == True

    for index in df[rookie_mask].index:

        position = df.at[index, "position"]
        talent = df.at[index, "rookie_talent_score"]

        if position == "RB":
            baseline = talent * 2.4

        elif position == "WR":
            baseline = talent * 2.1

        elif position == "TE":
            baseline = talent * 1.6

        elif position == "QB":
            baseline = talent * 2.7

        else:
            baseline = 0.0

        df.at[index, "rookie_baseline_projection"] = baseline

    df["rookie_baseline_projection"] = (
        df["rookie_baseline_projection"]
        .fillna(0.0)
    )

    return df


