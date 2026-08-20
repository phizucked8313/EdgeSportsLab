import pandas as pd

from fantasy_draft_model.ui import draft_war_room, streamlit_app


DRAFT_NIGHT_COLUMNS = [
    "draft_rank",
    "player_name_clean",
    "position",
    "team",
    "position_rank_label",
    "tier",
    "projected_points",
    "vorp",
    "edgescore",
    "draft_score",
    "pressure_score",
    "brain_score",
    "brain_recommendation",
    "injury_risk_score",
]


def _noisy_board():
    return pd.DataFrame(
        [
            {
                "player_id": "00-1",
                "player_name_clean": "Chris Olave",
                "position": "WR",
                "team": "NO",
                "games_played": 16,
                "targets": 156,
                "draft_rank": 12,
                "position_rank_label": "WR7",
                "tier": 2,
                "projected_points": 248.3,
                "vorp": 41.2,
                "edgescore": 88.4,
                "draft_score": 79.1,
                "pressure_score": 83.5,
                "brain_score": 84.7,
                "brain_recommendation": "DRAFT NOW",
                "injury_risk_score": 22.0,
            }
        ]
    )


def test_build_available_player_display_keeps_only_draft_night_columns():
    display = draft_war_room.build_available_player_display(_noisy_board())

    assert display.columns.tolist() == DRAFT_NIGHT_COLUMNS
    assert display.iloc[0]["player_name_clean"] == "Chris Olave"
    assert "player_id" not in display.columns
    assert "targets" not in display.columns


class FakeStreamlit:
    def __init__(self):
        self.metrics = []
        self.subheaders = []
        self.dataframes = []

    def metric(self, label, value):
        self.metrics.append((label, value))

    def success(self, text):
        pass

    def subheader(self, text):
        self.subheaders.append(text)

    def dataframe(self, dataframe, **kwargs):
        self.dataframes.append((dataframe, kwargs))


def test_render_war_room_snapshot_hides_indexes_and_uses_readable_available_board():
    fake_st = FakeStreamlit()
    available = _noisy_board()
    roster = pd.DataFrame(
        [{"player_name": "Ashton Jeanty", "position": None, "nfl_team": None}]
    )
    history = pd.DataFrame()
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

    available_display, available_kwargs = fake_st.dataframes[0]
    roster_display, roster_kwargs = fake_st.dataframes[1]
    history_display, history_kwargs = fake_st.dataframes[2]

    assert available_display.columns.tolist() == DRAFT_NIGHT_COLUMNS
    assert available_kwargs["hide_index"] is True
    assert roster_kwargs["hide_index"] is True
    assert history_kwargs["hide_index"] is True
