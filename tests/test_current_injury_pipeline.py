from pathlib import Path

import pandas as pd

from fantasy_draft_model.models.team_injury_impact_engine import (
    add_team_injury_impact,
    get_status_multiplier,
)
from fantasy_draft_model.integrations.current_injury_normalizer import (
    normalize_current_injuries,
)
from fantasy_draft_model.engines.injury_ripple_engine import (
    build_team_offensive_ripple,
    add_fantasy_ripple_scores,
    add_projection_multipliers,
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


def test_normalized_current_injury_flows_into_ripple_multiplier():
    sleeper_rows = pd.DataFrame([
        {
            "sleeper_id": "10",
            "player_name": "Starting WR",
            "team": "AAA",
            "position": "WR",
            "status": "Active",
            "injury_status": "Out",
            "injury_body_part": "Hamstring",
            "practice_participation": "Did Not Participate in Practice",
            "injury_start_date": "2026-08-18",
        }
    ])

    normalized = normalize_current_injuries(sleeper_rows)
    normalized["test_role"] = "STARTER"
    impacted = add_team_injury_impact(normalized, role_column="test_role")
    ripple = build_team_offensive_ripple(impacted)
    ripple = add_fantasy_ripple_scores(ripple)
    ripple = add_projection_multipliers(ripple)

    assert ripple.loc[0, "team"] == "AAA"
    assert ripple.loc[0, "pass_catcher_injury_impact"] > 0
    assert ripple.loc[0, "wr_ripple_multiplier"] > 1.0


def test_projection_engine_uses_normalized_current_injury_loader():
    source = Path(
        "fantasy_draft_model/engines/projection_engine.py"
    ).read_text(encoding="utf-8")

    assert "current_injury_normalizer" in source
    assert "load_normalized_current_injuries" in source
    assert "integrations.injury_history_loader" not in source
