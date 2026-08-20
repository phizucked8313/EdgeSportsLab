import pandas as pd

from fantasy_draft_model.rankings_snapshot import RankingDataStatus
from fantasy_draft_model.ui import streamlit_app


class FakeStreamlit:
    def __init__(self):
        self.messages = []
        self.rendered_text = ""
        self.button_calls = {}

    def success(self, text):
        self.messages.append(("success", text))

    def caption(self, text):
        self.rendered_text += str(text)

    def metric(self, *_args):
        return None

    def subheader(self, *_args):
        return None

    def markdown(self, text, **_kwargs):
        self.rendered_text += str(text)

    def dataframe(self, *_args, **_kwargs):
        return None

    def selectbox(self, _label, options, index=0):
        return options[index] if options else None

    def button(self, label, disabled=False):
        self.button_calls[label] = {"disabled": disabled}
        return False


def _complete_snapshot():
    available = pd.DataFrame([{"player_name_clean": "Alpha WR", "position": "WR", "team": "CLE"}])
    return {
        "context": {
            "current_pick": 181,
            "next_user_pick": None,
            "picks_until_user": None,
            "user_on_clock": False,
            "draft_complete": True,
            "accounted_picks": 180,
            "total_picks": 180,
        },
        "available": available,
        "filtered_available": available,
        "roster": pd.DataFrame(),
        "recent_history": pd.DataFrame([{"pick_number": 180, "player_name": "Alpha WR"}]),
    }


def test_completed_draft_shows_completion_copy_and_preserves_undo():
    fake_st = FakeStreamlit()
    snapshot = _complete_snapshot()

    streamlit_app.render_war_room_snapshot(fake_st, snapshot)
    streamlit_app.render_draft_actions(fake_st, snapshot)

    assert ("success", "Draft Complete — 180 of 180 slots accounted for") in fake_st.messages
    assert fake_st.button_calls["Record Pick"]["disabled"] is True
    assert fake_st.button_calls["Undo Last Pick"]["disabled"] is False


def test_rankings_status_displays_live_source_timestamp_and_age():
    fake_st = FakeStreamlit()
    status = RankingDataStatus("LIVE", "2026-08-20T00:00:00+00:00", 0.0)

    streamlit_app.render_rankings_status(fake_st, status)

    assert "LIVE" in fake_st.rendered_text
    assert status.created_at in fake_st.rendered_text
    assert "0s old" in fake_st.rendered_text


def test_rankings_status_displays_cached_age_and_failure_reason():
    fake_st = FakeStreamlit()
    status = RankingDataStatus(
        "CACHED/OFFLINE",
        "2026-08-20T00:00:00+00:00",
        90.0,
        "live refresh exceeded 15s",
    )

    streamlit_app.render_rankings_status(fake_st, status)

    assert "CACHED/OFFLINE" in fake_st.rendered_text
    assert status.created_at in fake_st.rendered_text
    assert "90s old" in fake_st.rendered_text
    assert status.failure_reason in fake_st.rendered_text
