import pandas as pd

from fantasy_draft_model.ui import draft_war_room, streamlit_app


def _board():
    return pd.DataFrame(
        [
            {
                "player_name_clean": "Ja'Marr Chase",
                "position": "WR",
                "team": "CIN",
                "draft_rank": 7,
                "position_rank_label": "WR3",
                "tier": 3,
                "tier_status": "ELITE SOLO TIER",
                "projected_points": 385.22,
                "vorp": 180.08,
                "vorp_score": 70.48,
                "edgescore": 88.12,
                "projection_confidence": 96.85,
                "injury_risk_score": 9.0,
                "brain_score": 87.8,
                "brain_recommendation": "DRAFT NOW",
                "brain_reasons": [
                    "Last player remaining in current tier",
                    "Strong positional value over replacement",
                    "Low chance of surviving until next pick",
                    "WR run is run active",
                ],
                "brain_warnings": [],
            },
            {
                "player_name_clean": "Amon-Ra St. Brown",
                "position": "WR",
                "team": "DET",
                "draft_rank": 10,
                "position_rank_label": "WR4",
                "tier": 4,
                "tier_status": "ELITE SOLO TIER",
                "projected_points": 364.00,
                "vorp": 158.86,
                "vorp_score": 62.18,
                "edgescore": 86.62,
                "projection_confidence": 96.85,
                "injury_risk_score": 9.0,
                "brain_score": 84.7,
                "brain_recommendation": "DRAFT NOW",
                "brain_reasons": [
                    "Last player remaining in current tier",
                    "Strong positional value over replacement",
                    "Low chance of surviving until next pick",
                ],
                "brain_warnings": [],
            },
            {
                "player_name_clean": "Chris Olave",
                "position": "WR",
                "team": "NO",
                "draft_rank": 15,
                "position_rank_label": "WR6",
                "tier": 6,
                "tier_status": "LIMITED TIER",
                "projected_points": 327.80,
                "vorp": 122.66,
                "vorp_score": 48.01,
                "edgescore": 83.60,
                "projection_confidence": 96.85,
                "injury_risk_score": 9.0,
                "brain_score": 70.0,
                "brain_recommendation": "STRONG TARGET",
                "brain_reasons": ["Strong positional value over replacement"],
                "brain_warnings": [],
            },
        ]
    )


def test_build_player_ranking_explanation_surfaces_reasons_and_key_numbers():
    board = _board()

    explanation = draft_war_room.build_player_ranking_explanation(
        board,
        "Ja'Marr Chase",
    )

    assert explanation["player_name"] == "Ja'Marr Chase"
    assert explanation["draft_rank"] == 7
    assert explanation["brain_score"] == 87.8
    assert explanation["recommendation"] == "DRAFT NOW"
    assert explanation["key_numbers"] == {
        "projected_points": 385.22,
        "vorp": 180.08,
        "edgescore": 88.12,
        "projection_confidence": 96.85,
        "injury_risk_score": 9.0,
    }
    assert "Last player remaining in current tier" in explanation["drivers"]
    assert board.loc[0, "brain_score"] == 87.8


def test_build_player_ranking_explanation_compares_to_next_lower_live_player():
    explanation = draft_war_room.build_player_ranking_explanation(
        _board(),
        "Ja'Marr Chase",
    )

    comparison = explanation["comparison"]
    assert comparison["player_name"] == "Amon-Ra St. Brown"
    assert comparison["brain_score_delta"] == 3.1
    assert comparison["projected_points_delta"] == 21.22
    assert comparison["vorp_delta"] == 21.22
    assert comparison["edgescore_delta"] == 1.5


class _ExplanationStreamlit:
    def __init__(self):
        self.selectboxes = []
        self.subheaders = []
        self.markdowns = []

    def selectbox(self, label, options, index=0, **kwargs):
        self.selectboxes.append((label, list(options)))
        return options[index]

    def subheader(self, text):
        self.subheaders.append(text)

    def markdown(self, body, **kwargs):
        self.markdowns.append(str(body))


def test_render_player_explanation_adds_why_edgeiq_panel_to_war_room():
    fake_st = _ExplanationStreamlit()
    board = _board()
    snapshot = {
        "available": board,
        "filtered_available": board,
    }

    streamlit_app.render_player_explanation(fake_st, snapshot)

    assert fake_st.selectboxes[0][0] == "Explain player"
    assert fake_st.selectboxes[0][1] == [
        "Ja'Marr Chase",
        "Amon-Ra St. Brown",
        "Chris Olave",
    ]
    assert any("Why EdgeIQ ranks Ja'Marr Chase" in text for text in fake_st.subheaders)
    rendered = "\n".join(fake_st.markdowns)
    assert "385.22" in rendered
    assert "180.08" in rendered
    assert "Amon-Ra St. Brown" in rendered
    assert "+21.22" in rendered
