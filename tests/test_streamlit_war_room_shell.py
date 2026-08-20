import pandas as pd
import pytest

from fantasy_draft_model.ui import streamlit_app


def _state():
    return {
        "league_name": "Drunk Sundays",
        "league_key": "drunk_sundays",
        "user_team": "BLKWDW'S",
        "team_count": 12,
        "draft_rounds": 15,
        "current_pick": 10,
        "manual_picks": [],
        "keeper_reservations": [],
    }


def test_build_live_view_uses_state_context_and_assistant_board(monkeypatch):
    state = _state()
    board = pd.DataFrame(
        [
            {
                "player_name_clean": "Beta RB",
                "position": "RB",
                "team": "DET",
                "draft_rank": 2,
            }
        ]
    )
    calls = {}

    monkeypatch.setattr(
        streamlit_app,
        "load_war_room_state",
        lambda: state,
        raising=False,
    )

    def fake_build_draft_assistant(league_key, draft_context=None):
        calls["league_key"] = league_key
        calls["draft_context"] = draft_context
        return board

    monkeypatch.setattr(
        streamlit_app,
        "build_draft_assistant",
        fake_build_draft_assistant,
        raising=False,
    )
    monkeypatch.setattr(
        streamlit_app,
        "build_live_draft_context",
        lambda supplied_state: {
            "current_pick": 10,
            "next_user_pick": 16,
            "picks_until_user": 6,
            "user_on_clock": False,
        },
        raising=False,
    )
    monkeypatch.setattr(
        streamlit_app,
        "build_war_room_snapshot",
        lambda rankings, supplied_state, search_text="", position=None: {
            "rankings": rankings,
            "state": supplied_state,
            "search_text": search_text,
            "position": position,
        },
        raising=False,
    )

    snapshot = streamlit_app.build_live_view()

    assert calls["league_key"] == "drunk_sundays"
    assert calls["draft_context"]["picks_until_user"] == 6
    assert snapshot["rankings"] is board
    assert snapshot["state"] is state


def test_build_live_view_forwards_ui_filters(monkeypatch):
    state = _state()
    board = pd.DataFrame(
        [
            {
                "player_name_clean": "Beta RB",
                "position": "RB",
                "team": "DET",
                "draft_rank": 2,
            }
        ]
    )

    monkeypatch.setattr(
        streamlit_app,
        "load_war_room_state",
        lambda: state,
        raising=False,
    )
    monkeypatch.setattr(
        streamlit_app,
        "build_draft_assistant",
        lambda league_key, draft_context=None: board,
        raising=False,
    )
    monkeypatch.setattr(
        streamlit_app,
        "build_live_draft_context",
        lambda supplied_state: {
            "picks_until_user": 6,
        },
        raising=False,
    )

    captured = {}

    def fake_snapshot(rankings, supplied_state, search_text="", position=None):
        captured["search_text"] = search_text
        captured["position"] = position
        return {"ok": True}

    monkeypatch.setattr(
        streamlit_app,
        "build_war_room_snapshot",
        fake_snapshot,
        raising=False,
    )

    result = streamlit_app.build_live_view(
        search_text="beta",
        position="RB",
    )

    assert result == {"ok": True}
    assert captured == {
        "search_text": "beta",
        "position": "RB",
    }


class FakeStreamlit:
    def __init__(self):
        self.metrics = []
        self.subheaders = []
        self.dataframes = []
        self.markdowns = []
        self.messages = []
        self.search_value = ""
        self.position_value = "ALL"
        self.player_value = None
        self.button_values = {}
        self.rerun_count = 0

    def metric(self, label, value):
        self.metrics.append((label, value))

    def subheader(self, text):
        self.subheaders.append(text)

    def dataframe(self, dataframe, **kwargs):
        self.dataframes.append(dataframe)

    def markdown(self, body, **kwargs):
        self.markdowns.append((str(body), kwargs))

    def success(self, text):
        self.messages.append(("success", text))

    def info(self, text):
        self.messages.append(("info", text))

    def error(self, text):
        self.messages.append(("error", text))

    def text_input(self, label, value=""):
        return self.search_value

    def selectbox(self, label, options, index=0):
        if label == "Position":
            return self.position_value
        if label == "Draft player":
            if self.player_value is not None:
                return self.player_value
            return options[index] if options else None
        return options[index] if options else None

    def button(self, label, disabled=False):
        if disabled:
            return False
        return self.button_values.get(label, False)

    def rerun(self):
        self.rerun_count += 1


def test_render_war_room_snapshot_shows_context_and_live_panels():
    fake_st = FakeStreamlit()
    available = pd.DataFrame(
        [{"player_name_clean": "Beta RB", "position": "RB", "team": "DET"}]
    )
    roster = pd.DataFrame(
        [{"player_name": "User WR", "position": "WR", "nfl_team": "CLE"}]
    )
    history = pd.DataFrame(
        [{"pick_number": 9, "player_name": "User WR", "fantasy_team": "BLKWDW'S"}]
    )
    snapshot = {
        "context": {
            "current_pick": 10,
            "next_user_pick": 16,
            "picks_until_user": 6,
            "user_on_clock": False,
        },
        "filtered_available": available,
        "roster": roster,
        "recent_history": history,
    }

    streamlit_app.render_war_room_snapshot(fake_st, snapshot)

    assert ("Current Pick", 10) in fake_st.metrics
    assert ("Next BLKWDW'S Pick", 16) in fake_st.metrics
    assert ("Picks Until You", 6) in fake_st.metrics
    assert fake_st.subheaders == [
        "Available Players",
        "Your Roster",
        "Recent Draft History",
    ]
    assert len(fake_st.markdowns) == 1
    assert "Beta RB" in fake_st.markdowns[0][0]
    assert fake_st.markdowns[0][1]["unsafe_allow_html"] is True
    assert fake_st.dataframes == [roster, history]


def test_run_war_room_ui_forwards_filters_and_renders_snapshot(monkeypatch):
    fake_st = FakeStreamlit()
    fake_st.search_value = "beta"
    fake_st.position_value = "RB"
    snapshot = {"ok": True}
    captured = {}

    def fake_build_live_view(search_text="", position=None):
        captured["search_text"] = search_text
        captured["position"] = position
        return snapshot

    def fake_render(st, supplied_snapshot):
        captured["st"] = st
        captured["snapshot"] = supplied_snapshot

    def fake_actions(st, supplied_snapshot):
        captured["actions_st"] = st
        captured["actions_snapshot"] = supplied_snapshot

    monkeypatch.setattr(
        streamlit_app,
        "build_live_view",
        fake_build_live_view,
    )
    monkeypatch.setattr(
        streamlit_app,
        "render_war_room_snapshot",
        fake_render,
        raising=False,
    )
    monkeypatch.setattr(
        streamlit_app,
        "render_draft_actions",
        fake_actions,
        raising=False,
    )

    streamlit_app.run_war_room_ui(fake_st)

    assert captured["search_text"] == "beta"
    assert captured["position"] == "RB"
    assert captured["st"] is fake_st
    assert captured["snapshot"] is snapshot
    assert captured["actions_st"] is fake_st
    assert captured["actions_snapshot"] is snapshot


def test_record_selected_player_uses_fresh_state_and_core_recorder(monkeypatch):
    state = _state()
    available = pd.DataFrame(
        [
            {
                "player_name_clean": "Beta RB",
                "position": "RB",
                "team": "DET",
                "draft_rank": 2,
            }
        ]
    )
    captured = {}

    monkeypatch.setattr(streamlit_app, "load_war_room_state", lambda: state)

    def fake_record_manual_pick(supplied_state, player_row):
        captured["state"] = supplied_state
        captured["player_name"] = player_row["player_name_clean"]
        return {"player_name": player_row["player_name_clean"]}

    monkeypatch.setattr(
        streamlit_app,
        "record_manual_pick",
        fake_record_manual_pick,
        raising=False,
    )

    result = streamlit_app.record_selected_player(available, "Beta RB")

    assert captured == {
        "state": state,
        "player_name": "Beta RB",
    }
    assert result == {"player_name": "Beta RB"}


def test_record_selected_player_rejects_missing_player():
    available = pd.DataFrame(
        [{"player_name_clean": "Beta RB", "position": "RB", "team": "DET"}]
    )

    with pytest.raises(ValueError, match="not available"):
        streamlit_app.record_selected_player(available, "Missing WR")


def test_undo_latest_pick_uses_fresh_state_and_core_undo(monkeypatch):
    state = _state()
    removed = {"player_name": "Beta RB", "pick_number": 10}
    captured = {}

    monkeypatch.setattr(streamlit_app, "load_war_room_state", lambda: state)

    def fake_undo(supplied_state):
        captured["state"] = supplied_state
        return removed

    monkeypatch.setattr(
        streamlit_app,
        "undo_last_manual_pick",
        fake_undo,
        raising=False,
    )

    result = streamlit_app.undo_latest_pick()

    assert captured["state"] is state
    assert result is removed


def test_render_draft_actions_records_selected_player_and_reruns(monkeypatch):
    fake_st = FakeStreamlit()
    fake_st.player_value = "Beta RB"
    fake_st.button_values["Record Pick"] = True
    available = pd.DataFrame(
        [{"player_name_clean": "Beta RB", "position": "RB", "team": "DET"}]
    )
    snapshot = {
        "available": available,
        "filtered_available": available,
        "recent_history": pd.DataFrame(),
    }
    captured = {}

    def fake_record(supplied_available, player_name):
        captured["available"] = supplied_available
        captured["player_name"] = player_name
        return {"player_name": player_name, "pick_number": 10}

    monkeypatch.setattr(streamlit_app, "record_selected_player", fake_record)

    streamlit_app.render_draft_actions(fake_st, snapshot)

    assert captured["available"] is available
    assert captured["player_name"] == "Beta RB"
    assert fake_st.rerun_count == 1


def test_render_draft_actions_undoes_latest_pick_and_reruns(monkeypatch):
    fake_st = FakeStreamlit()
    fake_st.button_values["Undo Last Pick"] = True
    available = pd.DataFrame(
        [{"player_name_clean": "Beta RB", "position": "RB", "team": "DET"}]
    )
    snapshot = {
        "available": available,
        "filtered_available": available,
        "recent_history": pd.DataFrame(
            [{"pick_number": 10, "player_name": "Alpha WR"}]
        ),
    }
    removed = {"player_name": "Alpha WR", "pick_number": 10}
    captured = {}

    def fake_undo():
        captured["called"] = True
        return removed

    monkeypatch.setattr(streamlit_app, "undo_latest_pick", fake_undo)

    streamlit_app.render_draft_actions(fake_st, snapshot)

    assert captured["called"] is True
    assert fake_st.rerun_count == 1
