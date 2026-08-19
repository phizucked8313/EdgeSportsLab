import pandas as pd


CURRENT_SEASON = 2026


POSITION_OPPORTUNITY_BASE = {
    "RB": 65.0,
    "WR": 60.0,
    "TE": 50.0,
    "QB": 45.0,
}

ACTIVE_STATUSES = {"active", "act"}
LIMITED_STATUSES = {"inactive", "ir", "pup", "reserve", "res"}

ROOKIE_POSITION_CURVE = {
    "RB": 85.0,
    "WR": 75.0,
    "QB": 65.0,
    "TE": 55.0,
}


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


def add_rookie_opportunity_score(df):
    """
    Add a conservative 2026 rookie roster-opportunity score.

    Uses current roster presence/status plus draft-capital-derived talent
    as a proxy. It intentionally does not depend on the stale 2025
    depth-chart dataset.
    """

    df = df.copy()
    df["rookie_opportunity_score"] = 50.0

    if "is_rookie" not in df.columns:
        return df

    if "rookie_talent_score" not in df.columns:
        df = calculate_rookie_talent_score(df)

    for index in df[df["is_rookie"] == True].index:
        position = str(df.at[index, "position"]).upper().strip()
        base = POSITION_OPPORTUNITY_BASE.get(position, 45.0)
        talent = float(df.at[index, "rookie_talent_score"])

        score = base + (talent - 50.0) * 0.35

        team = df.at[index, "team"] if "team" in df.columns else None
        if pd.notna(team) and str(team).strip():
            score += 5.0
        else:
            score -= 10.0

        status = df.at[index, "status"] if "status" in df.columns else None
        status_key = "" if pd.isna(status) else str(status).strip().lower()
        if status_key in ACTIVE_STATUSES:
            score += 5.0
        elif status_key in LIMITED_STATUSES:
            score -= 10.0

        df.at[index, "rookie_opportunity_score"] = round(
            max(35.0, min(90.0, score)),
            2,
        )

    return df


def add_rookie_position_curve(df):
    """Add position-specific first-year fantasy conversion scores."""

    df = df.copy()
    df["rookie_position_curve_score"] = 50.0

    if "is_rookie" not in df.columns:
        return df

    rookie_mask = df["is_rookie"] == True
    df.loc[rookie_mask, "rookie_position_curve_score"] = (
        df.loc[rookie_mask, "position"]
        .astype(str)
        .str.upper()
        .map(ROOKIE_POSITION_CURVE)
        .fillna(50.0)
    )

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
