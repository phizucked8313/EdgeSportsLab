import pandas as pd

from fantasy_draft_model.engines import vorp_engine


def test_replacement_ranks_allocate_flex_to_best_remaining_rb_wr():
    df = pd.DataFrame(
        {
            "player_name_clean": [
                "QB1", "QB2",
                "RB1", "RB2", "RB3", "RB4",
                "WR1", "WR2", "WR3", "WR4",
                "TE1", "TE2",
            ],
            "position": [
                "QB", "QB",
                "RB", "RB", "RB", "RB",
                "WR", "WR", "WR", "WR",
                "TE", "TE",
            ],
            "projected_points": [
                300, 290,
                250, 240, 230, 180,
                245, 235, 220, 210,
                190, 180,
            ],
        }
    )

    settings = {
        "teams": 2,
        "lineup": {
            "QB": 1,
            "RB": 1,
            "WR": 1,
            "TE": 1,
            "FLEX": 1,
        },
    }

    helper = getattr(vorp_engine, "calculate_replacement_ranks", None)
    assert helper is not None, "calculate_replacement_ranks helper is not implemented yet"

    result = helper(df, settings)

    assert result == {
        "QB": 2,
        "RB": 3,
        "WR": 3,
        "TE": 2,
    }
