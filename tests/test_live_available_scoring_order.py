import pandas as pd

from fantasy_draft_model import draft_assistant
from fantasy_draft_model.draft_assistant import build_draft_assistant_from_rankings
from fantasy_draft_model.ui import draft_war_room, streamlit_app


def _row(name, position, draft_rank, tier, vorp, edgescore, projected_points):
    return {
        "player_name_clean": name,
        "position": position,
        "team": "TEST",
        "tier": tier,
        "tier_size": 2 if pd.notna(tier) else pd.NA,
        "tier_threshold": 17.5 if pd.notna(tier) else pd.NA,
        "tier_next_projection_drop": 17.5 if pd.notna(tier) else pd.NA,
        "tier_next_vorp_drop": 0.0 if pd.notna(tier) else pd.NA,
        "draft_rank": draft_rank,
        "vorp": vorp,
        "edgescore": edgescore,
        "projected_points": projected_points,
        "projection_score": edgescore,
        "projection_confidence": 90.0,
        "injury_risk_score": 10.0,
        "draft_score": -1.0,
    }


def _mixed_rankings():
    return pd.DataFrame([
        _row("RB A", "RB", 5, 2, 100.0, 80.0, 280.0),
        _row("RB B", "RB", 6, 2, 95.0, 79.0, 270.0),
        _row("K A", "K", 140, pd.NA, 1.0, 20.0, 130.0),
        _row("DEF A", "DEF", 150, pd.NA, 1.0, 19.0, 120.0),
    ])


def _state(manual_picks=None):
    return {
        "league_name": "Drunk Sundays",
        "league_key": "drunk_sundays",
        "user_team": "BLKWDW'S",
        "team_count": 12,
        "draft_rounds": 15,
        "current_pick": 2,
        "manual_picks": list(manual_picks or []),
        "keeper_reservations": [],
    }


def test_mixed_offense_kicker_and_defense_board_scores_without_tier_crash():
    board = build_draft_assistant_from_rankings(
        _mixed_rankings(),
        draft_context={"picks_until_user": 3, "drafted_picks": []},
    ).set_index("player_name_clean")

    assert set(board.index) == {"RB A", "RB B", "K A", "DEF A"}
    assert board.loc["RB A", "tier_remaining"] == 2
    assert board.loc[["K A", "DEF A"], "tier_scarcity_score"].eq(0.0).all()


def test_tierless_board_runs_exact_live_scoring_pipeline_and_replaces_stale_score(
    monkeypatch,
):
    rankings = pd.DataFrame([
        _row("K A", "K", 140, pd.NA, 1.0, 20.0, 130.0),
        _row("DEF A", "DEF", 150, pd.NA, 1.0, 19.0, 120.0),
    ]).drop(columns="tier")
    calls = []

    def fake_scarcity(board):
        calls.append("scarcity")
        return board.assign(tier_scarcity_score=0.0, tier_remaining=0)

    def fake_draft_score(board):
        calls.append("draft_score")
        assert "tier_scarcity_score" in board.columns
        return board.assign(draft_score=[40.0, 30.0])

    def fake_pressure(board):
        calls.append("pressure")
        assert board["draft_score"].tolist() == [40.0, 30.0]
        return board.assign(pressure_score=[20.0, 10.0])

    def fake_brain(board, context):
        calls.append("brain")
        assert board["pressure_score"].tolist() == [20.0, 10.0]
        return board.assign(brain_score=[50.0, 90.0])

    monkeypatch.setattr(draft_assistant, "add_live_tier_scarcity", fake_scarcity)
    monkeypatch.setattr(draft_assistant, "recalculate_live_draft_score", fake_draft_score)
    monkeypatch.setattr(draft_assistant, "add_pressure_meter", fake_pressure)
    monkeypatch.setattr(draft_assistant, "add_draft_brain", fake_brain)

    board = build_draft_assistant_from_rankings(rankings)

    assert calls == ["scarcity", "draft_score", "pressure", "brain"]
    assert board["draft_score"].tolist() == [30.0, 40.0]
    assert board["brain_score"].tolist() == [90.0, 50.0]


def test_build_live_view_filters_once_before_scoring_and_preserves_baseline_rank(
    monkeypatch,
):
    rankings = _mixed_rankings().iloc[:2].copy()
    state = _state([{"player_name": "RB A"}])
    real_filter = draft_war_room.filter_available_players
    filter_calls = []

    def tracking_filter(board, supplied_state):
        filter_calls.append(board["player_name_clean"].tolist())
        return real_filter(board, supplied_state)

    monkeypatch.setattr(streamlit_app, "load_or_initialize_war_room_state", lambda: state)
    monkeypatch.setattr(streamlit_app, "filter_available_players", tracking_filter)
    monkeypatch.setattr(draft_war_room, "filter_available_players", tracking_filter)

    snapshot = streamlit_app.build_live_view(base_rankings=rankings)
    available = snapshot["available"].set_index("player_name_clean")

    assert len(filter_calls) == 1
    assert "RB A" not in available.index
    assert available.loc["RB B", "tier_remaining"] == 1
    assert available.loc["RB B", "draft_rank"] == 6
    assert snapshot["available"]["brain_score"].is_monotonic_decreasing


def test_build_live_view_removes_keeper_before_scoring_and_enriches_roster_metadata(
    monkeypatch,
):
    rankings = _mixed_rankings().iloc[:2].copy()
    state = _state()
    state["keeper_reservations"] = [{
        "pick_number": 1,
        "round": 1,
        "fantasy_team": "BLKWDW'S",
        "player_name": "RB A",
        "position": None,
        "nfl_team": None,
    }]
    monkeypatch.setattr(streamlit_app, "load_or_initialize_war_room_state", lambda: state)

    snapshot = streamlit_app.build_live_view(base_rankings=rankings)
    available = snapshot["available"].set_index("player_name_clean")
    keeper = snapshot["roster"].iloc[0]

    assert list(available.index) == ["RB B"]
    assert available.loc["RB B", "tier_remaining"] == 1
    assert snapshot["available"]["brain_score"].is_monotonic_decreasing
    assert keeper["player_name"] == "RB A"
    assert keeper["position"] == "RB"
    assert keeper["nfl_team"] == "TEST"


def test_no_cache_and_no_unavailable_players_still_uses_canonical_filter(
    monkeypatch,
    tmp_path,
):
    rankings = _mixed_rankings()
    state = _state()
    real_filter = draft_war_room.filter_available_players
    filter_calls = []

    def tracking_filter(board, supplied_state):
        filter_calls.append(board["player_name_clean"].tolist())
        return real_filter(board, supplied_state)

    monkeypatch.setattr(streamlit_app, "load_or_initialize_war_room_state", lambda: state)
    monkeypatch.setattr(streamlit_app, "build_draft_rankings", lambda league_key: rankings)
    monkeypatch.setattr(streamlit_app, "filter_available_players", tracking_filter)
    monkeypatch.setattr(draft_war_room, "filter_available_players", tracking_filter)

    snapshot = streamlit_app.build_live_view(
        paths={
            "data_path": tmp_path / "rankings.csv",
            "metadata_path": tmp_path / "rankings.json",
        },
    )

    assert len(filter_calls) == 1
    assert snapshot["available"]["player_name_clean"].tolist()


def test_all_unavailable_board_returns_empty_scored_snapshot(monkeypatch):
    rankings = _mixed_rankings()
    state = _state([
        {"player_name": "RB A"},
        {"player_name": "RB B"},
        {"player_name": "K A"},
        {"player_name": "DEF A"},
    ])
    monkeypatch.setattr(streamlit_app, "load_or_initialize_war_room_state", lambda: state)

    snapshot = streamlit_app.build_live_view(base_rankings=rankings)

    assert snapshot["available"].empty
    assert {"draft_score", "pressure_score", "brain_score"}.issubset(
        snapshot["available"].columns
    )
