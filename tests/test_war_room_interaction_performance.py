import pandas as pd

from fantasy_draft_model.engines import draft_brain_engine, run_detector_engine, what_if_i_wait_engine
from fantasy_draft_model.ui import draft_war_room, streamlit_app


def _brain_board():
    return pd.DataFrame(
        [
            {
                "player_name_clean": "Alpha WR",
                "position": "WR",
                "draft_rank": 1,
                "pressure_score": 80.0,
                "draft_score": 85.0,
                "edgescore": 88.0,
                "vorp": 45.0,
                "projection_confidence": 90.0,
                "injury_risk_score": 20.0,
                "projected_points": 300.0,
            },
            {
                "player_name_clean": "Beta WR",
                "position": "WR",
                "draft_rank": 2,
                "pressure_score": 70.0,
                "draft_score": 78.0,
                "edgescore": 82.0,
                "vorp": 35.0,
                "projection_confidence": 88.0,
                "injury_risk_score": 25.0,
                "projected_points": 280.0,
            },
        ]
    )


def test_build_live_draft_context_includes_current_manual_picks():
    manual_picks = [
        {
            "pick_number": 1,
            "player_name": "Alpha WR",
            "position": "WR",
            "fantasy_team": "Parrots",
        }
    ]
    state = {
        "league_name": "Drunk Sundays",
        "league_key": "drunk_sundays",
        "user_team": "BLKWDW'S",
        "team_count": 12,
        "draft_rounds": 15,
        "current_pick": 2,
        "manual_picks": manual_picks,
    }

    context = draft_war_room.build_live_draft_context(state)

    assert context["drafted_picks"] == manual_picks


def test_build_position_run_cache_uses_supplied_live_picks_only():
    rankings = pd.DataFrame(
        [
            {"player_name_clean": "WR One", "position": "WR"},
            {"player_name_clean": "WR Two", "position": "WR"},
            {"player_name_clean": "WR Three", "position": "WR"},
            {"player_name_clean": "RB One", "position": "RB"},
        ]
    )
    drafted_picks = [
        {"player_name": "WR One", "pick_number": 1},
        {"player_name": "WR Two", "pick_number": 2},
        {"player_name": "RB One", "pick_number": 3},
        {"player_name": "WR Three", "pick_number": 4},
    ]

    cache = run_detector_engine.build_position_run_cache(
        rankings,
        drafted_picks,
        recent_picks=8,
    )

    assert cache["WR"]["position_picks"] == 3
    assert cache["WR"]["run_label"] == "RUN STARTING"
    assert cache["RB"]["position_picks"] == 1
    assert cache["RB"]["run_label"] == "NORMAL"


def test_build_wait_report_cache_batches_same_position_fallbacks():
    board = _brain_board()

    cache = what_if_i_wait_engine.build_wait_report_cache(
        board,
        picks_until_next=7,
    )

    assert cache["Alpha WR"]["next_player"] == "Beta WR"
    assert cache["Alpha WR"]["picks_until_next"] == 7
    assert cache["Beta WR"]["next_player"] is None


def test_add_draft_brain_uses_batch_live_caches_once(monkeypatch):
    board = _brain_board()
    calls = {"wait": 0, "run": 0}

    wait_cache = {
        "Alpha WR": {"survival_score": 40.0, "projection_drop": 20.0},
        "Beta WR": {"survival_score": 55.0, "projection_drop": 0.0},
    }
    run_cache = {
        "WR": {
            "position": "WR",
            "position_picks": 3,
            "run_score": 75.0,
            "run_label": "RUN STARTING",
        }
    }

    def fake_wait_cache(df, picks_until_next=10):
        calls["wait"] += 1
        return wait_cache

    def fake_run_cache(df, drafted_picks, recent_picks=8):
        calls["run"] += 1
        return run_cache

    monkeypatch.setattr(
        draft_brain_engine,
        "build_wait_report_cache",
        fake_wait_cache,
        raising=False,
    )
    monkeypatch.setattr(
        draft_brain_engine,
        "build_position_run_cache",
        fake_run_cache,
        raising=False,
    )
    monkeypatch.setattr(
        draft_brain_engine,
        "analyze_wait",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("per-player analyze_wait should not run")
        ),
    )
    monkeypatch.setattr(
        draft_brain_engine,
        "get_position_run",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("per-player get_position_run should not run")
        ),
    )

    result = draft_brain_engine.add_draft_brain(
        board,
        {
            "picks_until_user": 7,
            "drafted_picks": [],
        },
    )

    assert calls == {"wait": 1, "run": 1}
    assert result["brain_score"].notna().all()


class _FakeForm:
    def __init__(self, st):
        self.st = st

    def __enter__(self):
        return self.st

    def __exit__(self, exc_type, exc, tb):
        return False


class _FormAwareStreamlit:
    def __init__(self):
        self.form_names = []
        self.submit_labels = []
        self.rerun_count = 0

    def form(self, name):
        self.form_names.append(name)
        return _FakeForm(self)

    def selectbox(self, label, options, index=0):
        return options[index] if options else None

    def form_submit_button(self, label, disabled=False):
        self.submit_labels.append(label)
        return False

    def button(self, label, disabled=False):
        if label == "Record Pick":
            raise AssertionError("Record Pick must be submitted through a form")
        return False

    def rerun(self):
        self.rerun_count += 1


def test_render_draft_actions_uses_form_for_player_selection():
    fake_st = _FormAwareStreamlit()
    available = pd.DataFrame(
        [{"player_name_clean": "Alpha WR", "position": "WR", "team": "CLE"}]
    )
    snapshot = {
        "available": available,
        "filtered_available": available,
        "recent_history": pd.DataFrame(),
    }

    streamlit_app.render_draft_actions(fake_st, snapshot)

    assert fake_st.form_names == ["draft_player_form"]
    assert fake_st.submit_labels == ["Record Pick"]
