import pandas as pd


CURRENT_SEASON = 2026


def calculate_rookie_talent_score(df):
    """
    Add a rookie talent score to the EdgeIQ player pool.

    NFL draft capital is the primary signal.
    Earlier picks receive smoothly higher scores than later picks.
    Veterans receive a neutral score of 50.
    """

    df = df.copy()

    df["rookie_talent_score"] = 50.0

    if "is_rookie" not in df.columns:
        return df

    if "draft_number" not in df.columns:
        df["draft_number"] = None

    rookie_mask = df["is_rookie"] == True

    for index in df[rookie_mask].index:
        draft_number = pd.to_numeric(
            pd.Series([df.at[index, "draft_number"]]),
            errors="coerce",
        ).iloc[0]

        if pd.isna(draft_number) or draft_number <= 0:
            score = 30.0
        else:
            capped_pick = min(float(draft_number), 257.0)
            score = 100.0 - ((capped_pick - 1.0) / 256.0) * 70.0
            score = max(30.0, min(100.0, score))

        df.at[index, "rookie_talent_score"] = round(score, 2)

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
