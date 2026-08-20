"""
EdgeIQ Football Intelligence Engine
Version 1

Turns raw player metrics into explainable
football pros, cons, hidden edges, and
high-level intelligence scores.
"""

import pandas as pd


HARD_TIER_SCARCITY_THRESHOLD = 80.0
ELEVATED_TIER_SCARCITY_THRESHOLD = 60.0


# ============================================================
# HELPERS
# ============================================================


def safe_value(
    row,
    column,
    default=0
):
    """
    Safely pull one value from a pandas row.

    Handles:
    - missing columns
    - NaN values
    - accidental duplicate columns
    """

    value = row.get(
        column,
        default
    )

    # -----------------------------------------
    # HANDLE DUPLICATE COLUMN NAMES
    # -----------------------------------------

    if isinstance(
        value,
        pd.Series
    ):

        value = (
            value
            .dropna()
        )

        if value.empty:
            return default

        value = value.iloc[0]

    # -----------------------------------------
    # HANDLE NORMAL NaN VALUE
    # -----------------------------------------

    if pd.isna(value):
        return default

    return value





# ============================================================
# PRODUCTION INTELLIGENCE
# ============================================================

def production_intelligence(row):

    pros = []
    cons = []

    ppg = safe_value(
        row,
        "custom_points_per_game"
    )

    if ppg >= 20:
        pros.append(
            "Elite fantasy production"
        )

    elif ppg >= 15:
        pros.append(
            "Strong fantasy production"
        )

    elif ppg < 8:
        cons.append(
            "Limited recent fantasy production"
        )


    return pros, cons


# ============================================================
# OPPORTUNITY INTELLIGENCE
# ============================================================

def opportunity_intelligence(row):

    pros = []
    cons = []

    opportunity_score = safe_value(
        row,
        "opportunity_score"
    )

    target_share = safe_value(
        row,
        "target_share"
    )

    wopr = safe_value(
        row,
        "wopr"
    )


    if opportunity_score >= 90:
        pros.append(
            "Elite projected opportunity"
        )

    elif opportunity_score >= 75:
        pros.append(
            "Strong projected opportunity"
        )

    elif opportunity_score <= 35:
        cons.append(
            "Limited projected opportunity"
        )


    if target_share >= 0.25:
        pros.append(
            "Elite target share"
        )

    elif target_share >= 0.20:
        pros.append(
            "Strong target share"
        )


    if wopr >= 0.60:
        pros.append(
            "Elite receiving opportunity profile"
        )


    return pros, cons


# ============================================================
# RUSHING INTELLIGENCE
# ============================================================

def rushing_intelligence(row):

    pros = []
    cons = []

    position = safe_value(
        row,
        "position",
        ""
    )

    rushing_score = safe_value(
        row,
        "rushing_usage_score"
    )

    qb_contact = safe_value(
        row,
        "qb_contact_exposure"
    )


    if position == "QB":

        if rushing_score >= 85:
            pros.append(
                "Elite quarterback rushing upside"
            )

        elif rushing_score >= 65:
            pros.append(
                "Above-average quarterback rushing floor"
            )


        if qb_contact >= 80:
            cons.append(
                "Very high rushing contact exposure"
            )

        elif qb_contact >= 60:
            cons.append(
                "Elevated rushing contact exposure"
            )


    if position == "WR":

        if rushing_score >= 85:
            pros.append(
                "Hybrid rushing role adds extra fantasy upside"
            )

        elif rushing_score >= 65:
            pros.append(
                "Adds meaningful rushing production"
            )


    return pros, cons


# ============================================================
# INJURY INTELLIGENCE
# ============================================================

def injury_intelligence(row):

    pros = []
    cons = []

    durability = safe_value(
        row,
        "durability_score"
    )

    injury_risk = safe_value(
        row,
        "injury_risk_score"
    )

    soft_tissue = safe_value(
        row,
        "soft_tissue_risk"
    )

    recurrence = safe_value(
        row,
        "recurrence_risk"
    )

    major = safe_value(
        row,
        "major_injury_risk"
    )


    if durability >= 90:
        pros.append(
            "Excellent durability profile"
        )

    elif durability >= 80:
        pros.append(
            "Strong durability profile"
        )


    if injury_risk >= 70:
        cons.append(
            "High overall injury risk"
        )

    elif injury_risk >= 50:
        cons.append(
            "Elevated injury risk"
        )


    if soft_tissue >= 50:
        cons.append(
            "Significant soft-tissue injury concern"
        )

    elif soft_tissue >= 30:
        cons.append(
            "Soft-tissue injury history requires monitoring"
        )


    if recurrence >= 40:
        cons.append(
            "Recurring injury history"
        )


    if major >= 50:
        cons.append(
            "Major structural injury history"
        )


    return pros, cons


# ============================================================
# PROJECTION INTELLIGENCE
# ============================================================

def projection_intelligence(row):

    pros = []
    cons = []

    confidence = safe_value(
        row,
        "projection_confidence"
    )

    floor = safe_value(
        row,
        "floor_projection"
    )

    projection = safe_value(
        row,
        "projected_points"
    )

    ceiling = safe_value(
        row,
        "ceiling_projection"
    )


    if confidence >= 95:
        pros.append(
            "Very high projection confidence"
        )

    elif confidence >= 90:
        pros.append(
            "High projection confidence"
        )


    if projection > 0:

        floor_ratio = (
            floor
            / projection
        )

        ceiling_ratio = (
            ceiling
            / projection
        )


        if floor_ratio >= 0.85:
            pros.append(
                "Strong weekly floor"
            )


        if ceiling_ratio >= 1.15:
            pros.append(
                "High ceiling outcome"
            )


        if floor_ratio < 0.75:
            cons.append(
                "Wide downside range"
            )


    return pros, cons


# ============================================================
# TIER / DRAFT INTELLIGENCE
# ============================================================

def draft_intelligence(row):

    pros = []
    cons = []

    tier = safe_value(
        row,
        "tier"
    )

    tier_remaining = safe_value(
        row,
        "tier_remaining",
        0
    )

    tier_scarcity = safe_value(
        row,
        "tier_scarcity_score",
        0
    )

    position = str(safe_value(
        row,
        "position",
        ""
    )).strip().upper()

    vorp = safe_value(
        row,
        "vorp"
    )

    edgescore = safe_value(
        row,
        "edgescore"
    )


    if tier == 1:
        pros.append(
            "Elite positional tier"
        )


    if vorp >= 100:
        pros.append(
            "Massive value over replacement"
        )

    elif vorp >= 50:
        pros.append(
            "Strong value over replacement"
        )


    if edgescore >= 90:
        pros.append(
            "Elite EdgeIQ profile"
        )


    if (
        tier > 0
        and tier_remaining == 1
        and tier_scarcity >= HARD_TIER_SCARCITY_THRESHOLD
    ):

        pros.append(
            f"Last player remaining in {position} Tier {int(tier)}"
        )


    if (
        tier > 0
        and tier_remaining == 2
        and tier_scarcity >= ELEVATED_TIER_SCARCITY_THRESHOLD
    ):

        pros.append(
            f"Two players remaining in {position} Tier {int(tier)}"
        )


    return pros, cons


# ============================================================
# SCHEDULE INTELLIGENCE PLACEHOLDER
# ============================================================

def schedule_intelligence(row):

    pros = []
    cons = []

    schedule_score = safe_value(
        row,
        "schedule_score",
        50
    )

    playoff_score = safe_value(
        row,
        "playoff_schedule_score",
        50
    )


    if schedule_score >= 75:
        pros.append(
            "Favorable regular-season schedule"
        )

    elif schedule_score <= 30:
        cons.append(
            "Difficult regular-season schedule"
        )


    if playoff_score >= 75:
        pros.append(
            "Favorable fantasy playoff schedule"
        )

    elif playoff_score <= 30:
        cons.append(
            "Difficult fantasy playoff schedule"
        )


    return pros, cons


# ============================================================
# OFFENSIVE LINE INTELLIGENCE PLACEHOLDER
# ============================================================

def offensive_line_intelligence(row):

    pros = []
    cons = []

    oline_score = safe_value(
        row,
        "offensive_line_score",
        50
    )


    if oline_score >= 80:
        pros.append(
            "Elite offensive line environment"
        )

    elif oline_score >= 70:
        pros.append(
            "Strong offensive line"
        )

    elif oline_score <= 30:
        cons.append(
            "Poor offensive line environment"
        )


    return pros, cons


# ============================================================
# COACHING INTELLIGENCE PLACEHOLDER
# ============================================================

def coaching_intelligence(row):

    pros = []
    cons = []

    coaching_score = safe_value(
        row,
        "coaching_score",
        50
    )


    if coaching_score >= 80:
        pros.append(
            "Elite coaching and scheme environment"
        )

    elif coaching_score >= 70:
        pros.append(
            "Strong coaching environment"
        )

    elif coaching_score <= 30:
        cons.append(
            "Coaching or scheme concerns"
        )


    return pros, cons


# ============================================================
# HIDDEN EDGE
# ============================================================

def create_hidden_edge(row):

    edges = []

    position = safe_value(
        row,
        "position",
        ""
    )

    opportunity = safe_value(
        row,
        "opportunity_score"
    )

    edgescore = safe_value(
        row,
        "edgescore"
    )

    vorp = safe_value(
        row,
        "vorp"
    )

    rushing = safe_value(
        row,
        "rushing_usage_score"
    )

    injury_risk = safe_value(
        row,
        "injury_risk_score"
    )


    if opportunity >= 90:
        edges.append(
            "Opportunity profile may support more production than raw totals suggest."
        )


    if (
        position in ["QB", "WR"]
        and rushing >= 80
    ):
        edges.append(
            "Rushing usage creates additional fantasy scoring paths."
        )


    if (
        edgescore >= 90
        and injury_risk <= 20
    ):
        edges.append(
            "Elite profile combines strong upside with relatively low current risk."
        )


    if vorp >= 100:
        edges.append(
            "Positional advantage is significantly greater than replacement-level alternatives."
        )


    if not edges:

        edges.append(
            "No major hidden edge identified yet."
        )


    return edges[0]


# ============================================================
# PLAYER FOOTBALL INTELLIGENCE
# ============================================================

def build_intelligence_for_player(row):

    all_pros = []
    all_cons = []


    intelligence_functions = [

        production_intelligence,
        opportunity_intelligence,
        rushing_intelligence,
        injury_intelligence,
        projection_intelligence,
        draft_intelligence,
        schedule_intelligence,
        offensive_line_intelligence,
        coaching_intelligence,

    ]


    for function in intelligence_functions:

        pros, cons = function(
        row
        )

        all_pros.extend(
            pros
        )

        all_cons.extend(
            cons
        )


    # Remove duplicates while preserving order
    all_pros = list(
        dict.fromkeys(
            all_pros
        )
    )

    all_cons = list(
        dict.fromkeys(
            all_cons
        )
    )


    hidden_edge = create_hidden_edge(
        row
    )


    return {

        "pros": all_pros,

        "cons": all_cons,

        "hidden_edge": hidden_edge,

    }


# ============================================================
# ADD INTELLIGENCE TO FULL DATAFRAME
# ============================================================

def add_football_intelligence(
    df: pd.DataFrame
) -> pd.DataFrame:

    df = df.copy()


    reports = []


    for _, row in df.iterrows():

        report = (
            build_intelligence_for_player(
                row
            )
        )

        reports.append(
            report
        )


    intelligence_df = pd.DataFrame(
        reports,
        index=df.index
    )


    df = pd.concat(
        [
            df,
            intelligence_df
        ],
        axis=1
    )


    return df
