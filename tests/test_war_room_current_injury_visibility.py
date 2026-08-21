import pandas as pd

from fantasy_draft_model.ui.draft_war_room import (
    build_available_player_display,
    build_player_ranking_explanation,
)


def _row(**overrides):
    row = {
        "draft_rank": 10,
        "player_name_clean": "Test Player",
        "position": "WR",
        "team": "CLE",
        "position_rank_label": "WR5",
        "tier": 2,
        "tier_remaining": 3,
        "tier_scarcity_score": 72.0,
        "projected_points": 94.6,
        "pre_current_injury_projected_points": 100.0,
        "current_injury_projection_penalty": 0.054,
        "current_injury_projection_multiplier": 0.946,
        "vorp": 50.0,
        "edgescore": 80.0,
        "draft_score": 75.0,
        "pressure_score": 70.0,
        "brain_score": 76.0,
        "brain_recommendation": "STRONG TARGET",
        "projection_confidence": 90.0,
        "injury_risk_score": 8.0,
        "is_currently_injured": True,
        "current_injury_status": "Questionable",
        "current_injury_body_part": "Ankle",
        "current_injury_practice_status": "Limited",
        "current_injury_source_timestamp": "2026-08-20T10:00:00+00:00",
        "current_injury_age_hours": 18.0,
        "current_injury_is_stale": False,
        "current_injury_source_quality": "A",
        "current_injury_research_override": False,
        "current_injury_is_ambiguous": False,
        "brain_reasons": ["Strong projection"],
        "brain_warnings": [],
    }
    row.update(overrides)
    return row


def test_available_board_includes_compact_current_injury_summary():
    display = build_available_player_display(pd.DataFrame([_row()]))

    assert "current_injury" in display.columns
    assert display.loc[0, "current_injury"] == "Q | Ankle | LIMITED | -5.4% | 18h"


def test_available_board_leaves_healthy_players_blank():
    display = build_available_player_display(
        pd.DataFrame([
            _row(
                is_currently_injured=False,
                current_injury_status="",
                current_injury_body_part="",
                current_injury_practice_status="",
                current_injury_projection_penalty=0.0,
                current_injury_age_hours=float("nan"),
            )
        ])
    )

    assert display.loc[0, "current_injury"] == ""


def test_available_board_marks_stale_injury_data():
    display = build_available_player_display(
        pd.DataFrame([
            _row(
                current_injury_is_stale=True,
                current_injury_projection_penalty=0.0,
                projected_points=100.0,
            )
        ])
    )

    assert "STALE" in display.loc[0, "current_injury"]
    assert "-0.0%" not in display.loc[0, "current_injury"]


def test_player_explanation_includes_current_injury_projection_impact_and_freshness():
    explanation = build_player_ranking_explanation(pd.DataFrame([_row()]), "Test Player")

    injury = explanation["current_injury"]
    assert injury["status"] == "Questionable"
    assert injury["body_part"] == "Ankle"
    assert injury["practice_status"] == "Limited"
    assert injury["source_timestamp"] == "2026-08-20T10:00:00+00:00"
    assert injury["age_hours"] == 18.0
    assert injury["source_quality"] == "A"
    assert injury["is_stale"] is False
    assert injury["research_override"] is False
    assert injury["pre_injury_projected_points"] == 100.0
    assert injury["post_injury_projected_points"] == 94.6
    assert injury["projection_penalty_pct"] == 5.4
    assert injury["projection_points_lost"] == 5.4


def test_player_explanation_states_stale_injury_was_not_auto_penalized():
    explanation = build_player_ranking_explanation(
        pd.DataFrame([
            _row(
                current_injury_is_stale=True,
                current_injury_projection_penalty=0.0,
                projected_points=100.0,
            )
        ]),
        "Test Player",
    )

    injury = explanation["current_injury"]
    assert injury["is_stale"] is True
    assert injury["projection_penalty_pct"] == 0.0
    assert injury["message"] == "Stale injury report — no automatic projection penalty applied."


def test_player_explanation_reports_research_override_on_stale_record():
    explanation = build_player_ranking_explanation(
        pd.DataFrame([
            _row(
                current_injury_is_stale=True,
                current_injury_research_override=True,
            )
        ]),
        "Test Player",
    )

    injury = explanation["current_injury"]
    assert injury["is_stale"] is True
    assert injury["research_override"] is True
    assert injury["projection_penalty_pct"] == 5.4
