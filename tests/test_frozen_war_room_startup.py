from hashlib import sha256

import pandas as pd

from fantasy_draft_model import draft_night_board
from fantasy_draft_model.live_war_room import (
    initialize_war_room,
    load_war_room_state,
    record_manual_pick,
    undo_last_manual_pick,
)
from fantasy_draft_model.ui import frozen_streamlit_app, streamlit_app
from fantasy_draft_model.ui.draft_war_room import filter_available_players


EXPECTED_FROZEN_SHA256 = (
    "1be7a6ce7e2f3b598b3e2419c837923b743796c4a68a5caf3cc5b334f64c5cf6"
)


def test_production_board_loader_uses_frozen_baseline_and_offline_special_teams(monkeypatch):
    monkeypatch.setattr(
        streamlit_app,
        "build_draft_rankings",
        lambda _league_key: (_ for _ in ()).throw(
            AssertionError("production draft-night startup called the live rankings builder")
        ),
    )
    monkeypatch.setattr(
        streamlit_app,
        "load_rankings_with_fallback",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("production draft-night startup called mutable cache fallback")
        ),
    )

    board, status = draft_night_board.load_production_draft_night_board(
        "drunk_sundays"
    )

    assert status.source == "FROZEN/OFFLINE"
    assert len(board) == 324

    supplemental = board["is_supplemental"].fillna(False).astype(bool)
    frozen = board.loc[~supplemental].copy()
    special = board.loc[supplemental].copy()

    assert len(frozen) == 300
    assert frozen["draft_rank"].tolist() == list(range(1, 301))
    assert len(special.loc[special["position"].eq("K")]) == 12
    assert len(special.loc[special["position"].eq("DEF")]) == 12
    assert special["draft_rank"].isna().all()
    assert special["supplemental_position_rank"].notna().all()
    assert set(special["ranking_source"]) == {"SUPPLEMENTAL/OFFLINE"}


def test_production_frozen_bytes_still_match_verified_checksum():
    assert (
        sha256(draft_night_board.FROZEN_TOP_300_CSV.read_bytes()).hexdigest()
        == EXPECTED_FROZEN_SHA256
    )


def test_special_teams_rows_are_searchable_without_fake_frozen_ranks():
    board, _status = draft_night_board.load_production_draft_night_board(
        "drunk_sundays"
    )

    defenses = board.loc[board["position"].eq("DEF")]
    kickers = board.loc[board["position"].eq("K")]

    assert "Philadelphia Eagles" in defenses["player_name_clean"].tolist()
    assert "Brandon Aubrey" in kickers["player_name_clean"].tolist()
    assert defenses["draft_rank"].isna().all()
    assert kickers["draft_rank"].isna().all()
    assert pd.to_numeric(
        defenses["supplemental_position_rank"], errors="raise"
    ).tolist() == list(range(1, 13))
    assert pd.to_numeric(
        kickers["supplemental_position_rank"], errors="raise"
    ).tolist() == list(range(1, 13))


def test_live_view_scores_only_frozen_rows_and_restores_frozen_rank_order(monkeypatch):
    state = {
        "league_name": "Drunk Sundays",
        "league_key": "drunk_sundays",
        "user_team": "BLKWDW'S",
        "team_count": 12,
        "draft_rounds": 15,
        "current_pick": 1,
        "manual_picks": [],
        "keeper_reservations": [],
        "processed_keeper_picks": [],
    }
    board, status = draft_night_board.load_production_draft_night_board(
        "drunk_sundays"
    )
    captured = {}

    monkeypatch.setattr(
        streamlit_app,
        "load_or_initialize_war_room_state",
        lambda: state,
    )
    monkeypatch.setattr(
        frozen_streamlit_app,
        "build_live_draft_context",
        lambda _state: {"picks_until_user": 8},
    )

    def fake_assistant(rankings, draft_context=None):
        captured["positions"] = set(rankings["position"])
        result = rankings.copy().iloc[::-1].reset_index(drop=True)
        result["brain_score"] = range(len(result))
        return result

    monkeypatch.setattr(
        frozen_streamlit_app,
        "build_draft_assistant_from_rankings",
        fake_assistant,
    )

    snapshot = frozen_streamlit_app.build_production_live_view(
        base_rankings=board,
        data_status=status,
    )

    assert "K" not in captured["positions"]
    assert "DEF" not in captured["positions"]
    assert set(snapshot["available"]["position"]) >= {
        "QB", "RB", "WR", "TE", "K", "DEF"
    }
    supplemental = snapshot["available"]["is_supplemental"].fillna(False).astype(bool)
    assert snapshot["available"].loc[supplemental, "brain_score"].isna().all()
    frozen_live = snapshot["available"].loc[~supplemental]
    assert frozen_live["draft_rank"].tolist() == sorted(
        frozen_live["draft_rank"].tolist()
    )


def test_kicker_and_defense_record_persist_and_undo(tmp_path):
    state_path = tmp_path / "war_room_state.json"
    state = initialize_war_room(
        "drunk_sundays",
        state_path=state_path,
        state_saver=lambda current, _path: current,
    )
    board, _status = draft_night_board.load_production_draft_night_board(
        "drunk_sundays"
    )
    kicker = board.loc[board["player_name_clean"].eq("Brandon Aubrey")].iloc[0]
    defense = board.loc[board["player_name_clean"].eq("Philadelphia Eagles")].iloc[0]

    kicker_pick = record_manual_pick(state, kicker, state_path=state_path)
    defense_pick = record_manual_pick(state, defense, state_path=state_path)

    assert kicker_pick["position"] == "K"
    assert defense_pick["position"] == "DEF"
    assert kicker_pick["draft_rank"] is None
    assert defense_pick["draft_rank"] is None

    persisted = load_war_room_state(state_path)
    drafted_names = [pick["player_name"] for pick in persisted["manual_picks"]]
    assert drafted_names[-2:] == ["Brandon Aubrey", "Philadelphia Eagles"]
    available = filter_available_players(board, persisted)
    assert "Brandon Aubrey" not in available["player_name_clean"].tolist()
    assert "Philadelphia Eagles" not in available["player_name_clean"].tolist()

    removed = undo_last_manual_pick(persisted, state_path=state_path)
    assert removed["player_name"] == "Philadelphia Eagles"
    restored = load_war_room_state(state_path)
    available_after_undo = filter_available_players(board, restored)
    assert "Philadelphia Eagles" in available_after_undo["player_name_clean"].tolist()
    assert "Brandon Aubrey" not in available_after_undo["player_name_clean"].tolist()
