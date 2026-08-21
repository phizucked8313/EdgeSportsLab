import pandas as pd

from fantasy_draft_model.ui import draft_war_room, streamlit_app


def _available_board():
    return pd.DataFrame(
        [
            {
                "draft_rank": 1,
                "player_name_clean": "Amon-Ra St. Brown",
                "position": "WR",
                "team": "DET",
                "brain_score": 88.4,
                "brain_recommendation": "DRAFT NOW",
            },
            {
                "draft_rank": 2,
                "player_name_clean": "Ja'Marr Chase",
                "position": "WR",
                "team": "CIN",
                "brain_score": 87.9,
                "brain_recommendation": "DRAFT NOW",
            },
        ]
    )


def test_build_static_available_board_html_is_scrollable_and_index_free():
    html = draft_war_room.build_static_available_board_html(_available_board())

    assert 'class="edgeiq-board-scroll"' in html
    assert "overflow" in html
    assert "<table" in html
    assert "Amon-Ra St. Brown" in html
    assert "<th>0</th>" not in html


class FakeStreamlit:
    def __init__(self):
        self.metrics = []
        self.subheaders = []
        self.markdowns = []
        self.dataframes = []

    def metric(self, label, value):
        self.metrics.append((label, value))

    def success(self, text):
        pass

    def subheader(self, text):
        self.subheaders.append(text)

    def markdown(self, body, **kwargs):
        self.markdowns.append((body, kwargs))

    def dataframe(self, dataframe, **kwargs):
        self.dataframes.append((dataframe, kwargs))


def test_render_war_room_snapshot_uses_sortable_dataframe_for_available_players():
    fake_st = FakeStreamlit()
    available = _available_board()
    roster = pd.DataFrame(
        [{"player_name": "Ashton Jeanty", "position": "RB", "nfl_team": "LV"}]
    )
    history = pd.DataFrame(
        [{"pick_number": 1, "player_name": "Test Pick", "fantasy_team": "Parrots"}]
    )
    snapshot = {
        "context": {
            "current_pick": 2,
            "next_user_pick": 9,
            "picks_until_user": 7,
            "user_on_clock": False,
        },
        "filtered_available": available,
        "roster": roster,
        "recent_history": history,
    }

    streamlit_app.render_war_room_snapshot(fake_st, snapshot)

    assert fake_st.markdowns == []
    assert len(fake_st.dataframes) == 3

    available_display, available_kwargs = fake_st.dataframes[0]
    assert available_display["player_name_clean"].tolist() == [
        "Amon-Ra St. Brown",
        "Ja'Marr Chase",
    ]
    assert available_kwargs["hide_index"] is True
    assert available_kwargs["use_container_width"] is True

    assert fake_st.dataframes[1][0] is roster
    assert fake_st.dataframes[2][0] is history
