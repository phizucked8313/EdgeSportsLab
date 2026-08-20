from dataclasses import replace

import pandas as pd

from fantasy_draft_model.draft_lifecycle import LifecycleInspection
from fantasy_draft_model.rankings_snapshot import RankingRefreshError
from fantasy_draft_model.ui import streamlit_app


class FakeStreamlit:
    def __init__(self):
        self.session_state = {}
        self.button_values = {}
        self.messages = []
        self.rendered_text = ""
        self.rerun_count = 0

    def button(self, label, disabled=False):
        self.button_calls[label] = {"disabled": disabled}
        return not disabled and self.button_values.get(label, False)

    @property
    def button_calls(self):
        if not hasattr(self, "_button_calls"):
            self._button_calls = {}
        return self._button_calls

    def caption(self, text):
        self.rendered_text += str(text)

    def info(self, text):
        self.messages.append(("info", text))
        self.rendered_text += str(text)

    def success(self, text):
        self.messages.append(("success", text))
        self.rendered_text += str(text)

    def error(self, text):
        self.messages.append(("error", text))
        self.rendered_text += str(text)

    def rerun(self):
        self.rerun_count += 1

    def text_input(self, _label, value=""):
        return value

    def selectbox(self, _label, options, index=0):
        return options[index] if options else None


def _inspection(draft_id="draft-1"):
    return LifecycleInspection(
        state={"draft_id": draft_id, "league_key": "drunk_sundays"},
        source="authoritative",
        requires_choice=True,
        can_resume=True,
        can_recover=False,
        is_legacy=False,
        completed_slots=12,
        total_slots=180,
        manual_pick_count=10,
        keeper_count=2,
        state_age_seconds=30.0,
        draft_id=draft_id,
        league_name="Drunk Sundays",
        status="active",
        created_at="2026-08-20T00:00:00+00:00",
        updated_at="2026-08-20T00:01:00+00:00",
        authoritative_path=streamlit_app.DEFAULT_STATE_PATH,
        backup_path=streamlit_app.DEFAULT_STATE_PATH.with_suffix(".backup.json"),
        recovery_metadata_path=streamlit_app.DEFAULT_STATE_PATH.with_suffix(".recovery.json"),
        authoritative_error=None,
        backup_error=None,
        legacy_error=None,
    )


def test_first_launch_renders_lifecycle_gate_without_building_live_board(monkeypatch):
    fake_st = FakeStreamlit()
    inspection = _inspection()
    monkeypatch.setattr(streamlit_app, "inspect_draft_lifecycle", lambda _path: inspection)
    monkeypatch.setattr(
        streamlit_app,
        "build_live_view",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("live board must wait for authorization")),
    )

    streamlit_app.run_war_room_ui(fake_st)

    assert fake_st.button_calls["Resume Draft"]["disabled"] is False
    assert fake_st.button_calls["Start New Draft"]["disabled"] is False
    assert "draft-1" in fake_st.rendered_text
    assert "12 of 180" in fake_st.rendered_text


def test_lifecycle_gate_displays_league_status_and_human_readable_state_age():
    fake_st = FakeStreamlit()

    streamlit_app.render_lifecycle_gate(fake_st, _inspection())

    assert "Drunk Sundays" in fake_st.rendered_text
    assert "active" in fake_st.rendered_text
    assert "30s old" in fake_st.rendered_text


def test_resume_authorizes_the_inspected_draft_id(monkeypatch):
    fake_st = FakeStreamlit()
    fake_st.button_values["Resume Draft"] = True
    inspection = _inspection()
    monkeypatch.setattr(streamlit_app, "inspect_draft_lifecycle", lambda _path: inspection)
    monkeypatch.setattr(streamlit_app, "resume_existing_draft", lambda *_args, **_kwargs: inspection.state)

    streamlit_app.run_war_room_ui(fake_st)

    assert fake_st.session_state[streamlit_app.DRAFT_AUTHORIZATION_KEY] == "draft-1"
    assert fake_st.rerun_count == 1


def test_start_uses_lifecycle_service_and_displays_verified_archive_root(monkeypatch):
    fake_st = FakeStreamlit()
    fake_st.button_values["Start New Draft"] = True
    inspection = replace(_inspection(), can_resume=False, state=None, draft_id=None)
    fresh = {"draft_id": "fresh-draft", "league_key": "drunk_sundays"}
    calls = []
    monkeypatch.setattr(streamlit_app, "inspect_draft_lifecycle", lambda _path: inspection)
    monkeypatch.setattr(
        streamlit_app,
        "start_new_draft",
        lambda *args: calls.append(args) or fresh,
    )

    streamlit_app.run_war_room_ui(fake_st)

    assert calls == [("drunk_sundays", streamlit_app.DEFAULT_STATE_PATH, streamlit_app.DRAFT_ARCHIVE_ROOT)]
    assert fake_st.session_state[streamlit_app.DRAFT_AUTHORIZATION_KEY] == "fresh-draft"
    assert str(streamlit_app.DRAFT_ARCHIVE_ROOT) in fake_st.rendered_text


def test_changed_disk_draft_id_invalidates_prior_session_authorization(monkeypatch):
    fake_st = FakeStreamlit()
    fake_st.session_state[streamlit_app.DRAFT_AUTHORIZATION_KEY] = "draft-1"
    inspection = _inspection(draft_id="replacement-draft")
    monkeypatch.setattr(streamlit_app, "inspect_draft_lifecycle", lambda _path: inspection)
    monkeypatch.setattr(
        streamlit_app,
        "build_live_view",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("replacement draft requires authorization")),
    )

    streamlit_app.run_war_room_ui(fake_st)

    assert streamlit_app.DRAFT_AUTHORIZATION_KEY not in fake_st.session_state
    assert "replacement-draft" in fake_st.rendered_text


def test_rankings_failure_shows_retry_and_runbook_without_player_board(monkeypatch):
    fake_st = FakeStreamlit()
    fake_st.session_state[streamlit_app.DRAFT_AUTHORIZATION_KEY] = "draft-1"
    inspection = _inspection()
    monkeypatch.setattr(streamlit_app, "inspect_draft_lifecycle", lambda _path: inspection)
    monkeypatch.setattr(
        streamlit_app,
        "get_or_build_base_rankings",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RankingRefreshError("live and cache unavailable")),
    )
    monkeypatch.setattr(
        streamlit_app,
        "build_live_view",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("player board must not render")),
    )

    streamlit_app.run_war_room_ui(fake_st)

    assert fake_st.button_calls["Retry"]["disabled"] is False
    assert "runbook" in fake_st.rendered_text.lower()


def test_state_swap_after_authorization_returns_to_lifecycle_gate_before_board(
    monkeypatch,
):
    fake_st = FakeStreamlit()
    fake_st.session_state[streamlit_app.DRAFT_AUTHORIZATION_KEY] = "draft-a"
    inspections = iter([_inspection("draft-a"), _inspection("draft-b")])
    replacement_state = {"draft_id": "draft-b", "league_key": "drunk_sundays"}
    board = pd.DataFrame([{"player_name_clean": "Alpha WR", "position": "WR"}])

    monkeypatch.setattr(
        streamlit_app,
        "inspect_draft_lifecycle",
        lambda _path: next(inspections),
    )
    monkeypatch.setattr(streamlit_app, "load_or_initialize_war_room_state", lambda: replacement_state)
    monkeypatch.setattr(streamlit_app, "get_or_build_base_rankings", lambda *_args, **_kwargs: board)
    monkeypatch.setattr(streamlit_app, "build_live_draft_context", lambda _state: {})
    monkeypatch.setattr(
        streamlit_app,
        "build_draft_assistant_from_rankings",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("replacement board must not build")),
    )

    streamlit_app.run_war_room_ui(fake_st)

    assert streamlit_app.DRAFT_AUTHORIZATION_KEY not in fake_st.session_state
    assert "draft-b" in fake_st.rendered_text


def test_stale_authorized_record_does_not_mutate_replacement_draft(monkeypatch):
    fake_st = FakeStreamlit()
    fake_st.button_values["Record Pick"] = True
    fake_st.session_state[streamlit_app.DRAFT_AUTHORIZATION_KEY] = "draft-a"
    available = pd.DataFrame([{"player_name_clean": "Alpha WR", "position": "WR"}])
    replacement_state = {"draft_id": "draft-b"}
    monkeypatch.setattr(streamlit_app, "load_war_room_state", lambda: replacement_state)
    monkeypatch.setattr(
        streamlit_app,
        "record_manual_pick",
        lambda *_args: (_ for _ in ()).throw(AssertionError("replacement draft must not mutate")),
    )

    streamlit_app.render_draft_actions(
        fake_st,
        {"available": available, "filtered_available": available, "recent_history": pd.DataFrame()},
        expected_draft_id="draft-a",
    )

    assert fake_st.rerun_count == 0
    assert streamlit_app.DRAFT_AUTHORIZATION_KEY not in fake_st.session_state
    assert any(kind == "error" and "changed" in text for kind, text in fake_st.messages)


def test_stale_authorized_undo_does_not_mutate_replacement_draft(monkeypatch):
    fake_st = FakeStreamlit()
    fake_st.button_values["Undo Last Pick"] = True
    fake_st.session_state[streamlit_app.DRAFT_AUTHORIZATION_KEY] = "draft-a"
    available = pd.DataFrame([{"player_name_clean": "Alpha WR", "position": "WR"}])
    replacement_state = {"draft_id": "draft-b"}
    monkeypatch.setattr(streamlit_app, "load_war_room_state", lambda: replacement_state)
    monkeypatch.setattr(
        streamlit_app,
        "undo_last_manual_pick",
        lambda *_args: (_ for _ in ()).throw(AssertionError("replacement draft must not mutate")),
    )

    streamlit_app.render_draft_actions(
        fake_st,
        {
            "available": available,
            "filtered_available": available,
            "recent_history": pd.DataFrame([{"pick_number": 1}]),
        },
        expected_draft_id="draft-a",
    )

    assert fake_st.rerun_count == 0
    assert streamlit_app.DRAFT_AUTHORIZATION_KEY not in fake_st.session_state
    assert any(kind == "error" and "changed" in text for kind, text in fake_st.messages)


def test_recovery_returns_to_gate_until_the_recovered_draft_is_explicitly_resumed(
    monkeypatch,
):
    fake_st = FakeStreamlit()
    fake_st.button_values["Recover Backup"] = True
    backup = replace(
        _inspection("draft-a"),
        state={"draft_id": "draft-a", "league_key": "drunk_sundays"},
        source="backup",
        can_resume=False,
        can_recover=True,
    )
    recovered = {"draft_id": "recovered-draft", "league_key": "drunk_sundays"}
    after_recovery = replace(
        _inspection("recovered-draft"),
        state=recovered,
        can_resume=True,
        can_recover=False,
        source="authoritative",
    )
    inspections = iter([backup, after_recovery])
    calls = []
    monkeypatch.setattr(streamlit_app, "inspect_draft_lifecycle", lambda _path: next(inspections))
    monkeypatch.setattr(
        streamlit_app,
        "recover_existing_draft",
        lambda *_args: calls.append("recover") or recovered,
    )
    monkeypatch.setattr(
        streamlit_app,
        "build_live_view",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("recovery must not enter board")),
    )

    streamlit_app.run_war_room_ui(fake_st)

    assert calls == ["recover"]
    assert streamlit_app.DRAFT_AUTHORIZATION_KEY not in fake_st.session_state
    assert fake_st.rerun_count == 1

    fake_st.button_values["Recover Backup"] = False
    fake_st.button_values["Resume Draft"] = True
    monkeypatch.setattr(
        streamlit_app,
        "resume_existing_draft",
        lambda *_args, **_kwargs: recovered,
    )

    streamlit_app.run_war_room_ui(fake_st)

    assert fake_st.session_state[streamlit_app.DRAFT_AUTHORIZATION_KEY] == "recovered-draft"
    assert fake_st.rerun_count == 2
