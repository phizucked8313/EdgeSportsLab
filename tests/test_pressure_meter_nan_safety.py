import math

import pandas as pd

from fantasy_draft_model.engines.pressure_meter_engine import add_pressure_meter


def test_pressure_meter_handles_special_team_rows_missing_value_metrics():
    board = pd.DataFrame(
        [
            {
                "player_name_clean": "Scored RB",
                "position": "RB",
                "draft_rank": 1,
                "tier_status": "DEPTH AVAILABLE",
                "vorp": 50.0,
                "draft_score": 80.0,
            },
            {
                "player_name_clean": "Test Kicker",
                "position": "K",
                "draft_rank": 600,
                "tier_status": pd.NA,
                "vorp": float("nan"),
                "draft_score": float("nan"),
            },
            {
                "player_name_clean": "Test Defense",
                "position": "DEF",
                "draft_rank": 601,
                "tier_status": pd.NA,
                "vorp": float("nan"),
                "draft_score": float("nan"),
            },
        ]
    )

    result = add_pressure_meter(board)
    special = result[result["position"].isin(["K", "DEF"])]

    assert len(special) == 2
    assert special["pressure_score"].apply(math.isfinite).all()
    assert special["pressure_score"].between(0, 100).all()
    assert special["pressure_label"].notna().all()
    assert special["pressure_bar"].notna().all()
