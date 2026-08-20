import pandas as pd

from fantasy_draft_model.draft_assistant import show_top_recommendations
from fantasy_draft_model.ui import streamlit_app
from fantasy_draft_model.ui.draft_war_room import (
    build_available_player_display,
    build_player_ranking_explanation,
    format_position_tier,
)


def test_position_tier_label_is_numeric_and_position_local():
    assert format_position_tier("RB", 1) == "RB Tier 1"
    assert format_position_tier("TE", 3) == "TE Tier 3"


def test_available_board_replaces_old_status_with_numeric_tier_label():
    board = pd.DataFrame(
        [{
            "draft_rank": 1,
            "player_name_clean": "RB A",
            "position": "RB",
            "team": "CLE",
            "position_rank_label": "RB1",
            "tier": 2,
            "tier_remaining": 1,
            "tier_scarcity_score": 85.0,
            "projected_points": 300.0,
            "vorp": 120.0,
            "edgescore": 90.0,
            "draft_score": 85.0,
            "pressure_score": 80.0,
            "brain_score": 84.0,
            "brain_recommendation": "DRAFT NOW",
            "injury_risk_score": 10.0,
        }]
    )

    display = build_available_player_display(board)

    assert display.iloc[0]["tier_label"] == "RB Tier 2"
    assert display.iloc[0]["tier_remaining"] == 1
    assert display.iloc[0]["tier_scarcity_score"] == 85.0
    assert "tier_status" not in display.columns


def test_draft_assistant_diagnostic_displays_numeric_tier_signals(capsys):
    board = pd.DataFrame([{
        "player_name_clean": "RB A",
        "position": "RB",
        "tier": 2,
        "tier_remaining": 1,
        "tier_scarcity_score": 85.0,
        "tier_next_projection_drop": 17.5,
        "tier_next_vorp_drop": 12.0,
        "brain_score": 84.0,
    }])

    show_top_recommendations(board, limit=1)

    output = capsys.readouterr().out
    assert "tier_remaining" in output
    assert "tier_scarcity_score" in output
    assert "tier_next_projection_drop" in output
    assert "tier_next_vorp_drop" in output


def test_explanation_uses_same_numeric_tier_fields_as_scoring():
    board = pd.DataFrame(
        [{
            "draft_rank": 1,
            "player_name_clean": "RB A",
            "position": "RB",
            "position_rank_label": "RB1",
            "tier": 2,
            "tier_remaining": 1,
            "tier_scarcity_score": 85.0,
            "brain_score": 84.0,
            "brain_recommendation": "DRAFT NOW",
            "brain_reasons": [],
            "brain_warnings": [],
            "projected_points": 300.0,
            "vorp": 120.0,
            "edgescore": 90.0,
            "projection_confidence": 95.0,
            "injury_risk_score": 10.0,
        }]
    )

    explanation = build_player_ranking_explanation(board, "RB A")

    assert explanation["tier_label"] == "RB Tier 2"
    assert explanation["tier_remaining"] == 1
    assert explanation["tier_scarcity_score"] == 85.0


def test_tierless_kicker_display_is_blank_without_changing_scarcity_values():
    board = pd.DataFrame(
        [{
            "draft_rank": 150,
            "player_name_clean": "K A",
            "position": "K",
            "team": "CLE",
            "position_rank_label": "K1",
            "tier": pd.NA,
            "tier_remaining": 0,
            "tier_scarcity_score": 0.0,
        }]
    )

    display = build_available_player_display(board)
    explanation = build_player_ranking_explanation(board, "K A")

    assert display.iloc[0]["tier_label"] == ""
    assert explanation["tier_label"] == ""
    assert explanation["tier_remaining"] == 0
    assert explanation["tier_scarcity_score"] == 0.0


class _ExplanationStreamlit:
    def __init__(self):
        self.markdowns = []

    def selectbox(self, label, options, index=0, **kwargs):
        return options[index]

    def subheader(self, text):
        pass

    def markdown(self, body, **kwargs):
        self.markdowns.append(str(body))


def test_streamlit_explanation_surfaces_numeric_tier_and_scarcity():
    board = pd.DataFrame(
        [{
            "draft_rank": 1,
            "player_name_clean": "RB A",
            "position": "RB",
            "position_rank_label": "RB1",
            "tier": 2,
            "tier_remaining": 1,
            "tier_scarcity_score": 85.0,
            "brain_score": 84.0,
            "brain_recommendation": "DRAFT NOW",
            "brain_reasons": [],
            "brain_warnings": [],
            "projected_points": 300.0,
            "vorp": 120.0,
            "edgescore": 90.0,
            "projection_confidence": 95.0,
            "injury_risk_score": 10.0,
        }]
    )
    fake_st = _ExplanationStreamlit()

    streamlit_app.render_player_explanation(
        fake_st,
        {"available": board, "filtered_available": board},
    )

    rendered = "\n".join(fake_st.markdowns)
    assert "RB Tier 2" in rendered
    assert "1 remaining" in rendered
    assert "85.00 scarcity" in rendered
