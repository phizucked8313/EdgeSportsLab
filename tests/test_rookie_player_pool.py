import pandas as pd

from fantasy_draft_model.integrations.roster_loader import add_rookie_identity


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
