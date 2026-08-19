import pandas as pd

from fantasy_draft_model.models.team_injury_impact_engine import (
    add_team_injury_impact,
    get_status_multiplier,
)


def test_ir_and_pup_are_not_treated_as_generic_unknown_statuses():
    assert get_status_multiplier("IR") == 1.00
    assert get_status_multiplier("PUP") == 1.00
    assert get_status_multiplier("DNR") == 1.00


def test_supplied_role_column_does_not_require_depth_chart_lookup():
    injuries = pd.DataFrame([
        {
            "team": "AAA",
            "position": "WR",
            "report_status": "Questionable",
            "practice_status": "",
            "test_role": "STARTER",
        }
    ])

    result = add_team_injury_impact(injuries, role_column="test_role")

    assert result.loc[0, "edgeiq_role"] == "STARTER"
    assert result.loc[0, "injury_unit"] == "PASS_CATCHERS"
    assert result.loc[0, "player_injury_impact"] > 0
