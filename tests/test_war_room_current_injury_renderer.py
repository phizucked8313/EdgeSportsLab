import pandas as pd

from fantasy_draft_model.ui import streamlit_app


class _FakeStreamlit:
    def __init__(self):
        self.subheaders = []
        self.markdowns = []

    def selectbox(self, label, options, index=0, **kwargs):
        return options[index]

    def subheader(self, text):
        self.subheaders.append(str(text))

    def markdown(self, body, **kwargs):
        self.markdowns.append(str(body))


def _injured_board():
    return pd.DataFrame(
        [
            {
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
                "vorp": 50.0,
                "edgescore": 80.0,
                "projection_confidence": 90.0,
                "injury_risk_score": 8.0,
                "brain_score": 76.0,
                "brain_recommendation": "STRONG TARGET",
                "brain_reasons": ["Strong projection"],
                "brain_warnings": [],
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
            }
        ]
    )


def test_render_player_explanation_surfaces_current_injury_impact():
    fake_st = _FakeStreamlit()
    board = _injured_board()
    snapshot = {
        "context": {"draft_complete": False},
        "available": board,
        "filtered_available": board,
    }

    streamlit_app.render_player_explanation(fake_st, snapshot)

    rendered = "\n".join(fake_st.markdowns)
    assert "Current injury" in rendered
    assert "Questionable" in rendered
    assert "Ankle" in rendered
    assert "Limited" in rendered
    assert "5.4%" in rendered
    assert "100.00" in rendered
    assert "94.60" in rendered
    assert "5.40 pts" in rendered
    assert "18h" in rendered
    assert "source quality A" in rendered
