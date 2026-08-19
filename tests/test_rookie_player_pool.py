import pandas as pd

from fantasy_draft_model.integrations.roster_loader import add_rookie_identity
from fantasy_draft_model.models import projections


def test_rookie_identity_comes_from_rookie_year_not_missing_stats():
    df = pd.DataFrame([
        {
            "full_name": "True Rookie",
            "rookie_year": 2026,
            "years_exp": 0,
        },
        {
            "full_name": "Veteran",
            "rookie_year": 2024,
            "years_exp": 2,
        },
        {
            "full_name": "Odd Veteran",
            "rookie_year": 2025,
            "years_exp": 0,
        },
    ])

    result = add_rookie_identity(
        df,
        current_season=2026,
    ).set_index("full_name")

    assert bool(result.loc["True Rookie", "is_rookie"]) is True
    assert bool(result.loc["Veteran", "is_rookie"]) is False
    assert bool(result.loc["Odd Veteran", "is_rookie"]) is False


def test_current_roster_presence_is_preserved_after_outer_merge():
    historical = pd.DataFrame([
        {
            "player_id": "old",
            "player_name_clean": "Old Veteran",
            "team": "AAA",
            "position": "WR",
            "games_played": 10,
        },
    ])
    roster = pd.DataFrame([
        {
            "player_id": "rook",
            "roster_player_name": "True Rookie",
            "current_team": "BBB",
            "current_position": "RB",
            "status": "Active",
            "rookie_year": 2026,
            "is_rookie": True,
        },
    ])

    helper = getattr(projections, "merge_current_roster_identity", None)
    assert helper is not None, "merge_current_roster_identity helper is not implemented yet"

    result = helper(historical, roster).set_index("player_id")

    assert bool(result.loc["rook", "on_current_roster"]) is True
    assert bool(result.loc["old", "on_current_roster"]) is False
