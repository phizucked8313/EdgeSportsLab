import pandas as pd
import pytest

from fantasy_draft_model.engines import cpu_draft, mock_draft_engine


def _neutral_tendencies(team_name):
    return {
        "qb_aggression": 1.0,
        "rb_aggression": 1.0,
        "wr_aggression": 1.0,
        "te_aggression": 1.0,
        "rookie_aggression": 1.0,
        "risk_tolerance": 1.0,
    }


def _special_teams_pool():
    return pd.DataFrame([
        {
            "player_name_clean": "Best WR",
            "position": "WR",
            "draft_rank": 1.0,
        },
        {
            "player_name_clean": "Best DEF",
            "position": "DEF",
            "draft_rank": 4.0,
        },
        {
            "player_name_clean": "Best K",
            "position": "K",
            "draft_rank": 5.0,
        },
    ])


def _complete_skill_counts(**overrides):
    counts = {
        "QB": 1,
        "RB": 3,
        "WR": 3,
        "TE": 1,
        "K": 1,
        "DEF": 1,
    }
    counts.update(overrides)
    return counts


def test_team_position_counts_include_kicker_and_defense():
    draft_results = [
        {
            "fantasy_team": "CPU Team",
            "position": "QB",
        },
        {
            "fantasy_team": "CPU Team",
            "position": "K",
        },
        {
            "fantasy_team": "CPU Team",
            "position": "DEF",
        },
        {
            "fantasy_team": "Other Team",
            "position": "K",
        },
    ]

    counts = mock_draft_engine.get_team_position_counts(
        draft_results,
        "CPU Team",
    )

    assert counts == {
        "QB": 1,
        "RB": 0,
        "WR": 0,
        "TE": 0,
        "K": 1,
        "DEF": 1,
    }


def test_15_round_final_pick_forces_missing_kicker(monkeypatch):
    monkeypatch.setattr(
        cpu_draft,
        "get_manager_tendencies",
        _neutral_tendencies,
    )

    pick = cpu_draft.make_cpu_pick(
        _special_teams_pool(),
        _complete_skill_counts(K=0),
        round_number=15,
        team_name="CPU Team",
        draft_rounds=15,
    )

    assert pick["position"] == "K"
    assert pick["player_name_clean"] == "Best K"


def test_16_round_league_uses_round_16_as_true_final_pick(monkeypatch):
    monkeypatch.setattr(
        cpu_draft,
        "get_manager_tendencies",
        _neutral_tendencies,
    )

    counts = _complete_skill_counts(K=0)

    round_15_pick = cpu_draft.make_cpu_pick(
        _special_teams_pool(),
        counts,
        round_number=15,
        team_name="CPU Team",
        draft_rounds=16,
    )
    round_16_pick = cpu_draft.make_cpu_pick(
        _special_teams_pool(),
        counts,
        round_number=16,
        team_name="CPU Team",
        draft_rounds=16,
    )

    assert round_15_pick["position"] == "WR"
    assert round_16_pick["position"] == "K"


def test_safety_fallback_never_reintroduces_second_kicker_or_defense(monkeypatch):
    monkeypatch.setattr(
        cpu_draft,
        "get_manager_tendencies",
        _neutral_tendencies,
    )

    only_illegal_specialists = pd.DataFrame([
        {
            "player_name_clean": "Second K",
            "position": "K",
            "draft_rank": 1.0,
        },
        {
            "player_name_clean": "Second DEF",
            "position": "DEF",
            "draft_rank": 2.0,
        },
    ])

    with pytest.raises(ValueError, match="No legal CPU pick"):
        cpu_draft.make_cpu_pick(
            only_illegal_specialists,
            _complete_skill_counts(),
            round_number=14,
            team_name="CPU Team",
            draft_rounds=15,
        )


def test_mock_draft_passes_league_draft_rounds_to_cpu_pick(monkeypatch):
    league = {
        "name": "Test League",
        "league_key": "test_league",
        "team_count": 1,
        "draft_rounds": 16,
        "draft_order": ["CPU Team"],
    }
    rankings = pd.DataFrame([
        {
            "player_name_clean": "Only WR",
            "position": "WR",
            "team": "AAA",
            "draft_rank": 1.0,
            "projected_points": 100.0,
            "is_rookie": False,
        }
    ])
    captured = {}

    monkeypatch.setattr(
        mock_draft_engine,
        "load_mock_league",
        lambda league_name: league,
    )
    monkeypatch.setattr(
        mock_draft_engine,
        "build_draft_rankings",
        lambda league_key: rankings.copy(),
    )
    monkeypatch.setattr(
        mock_draft_engine,
        "build_league_keeper_reservations",
        lambda league_name: {},
    )
    monkeypatch.setattr(
        mock_draft_engine,
        "get_bye_week",
        lambda nfl_team: 7,
    )

    def fake_cpu_pick(
        available,
        team_position_counts,
        round_number,
        team_name,
        draft_rounds,
    ):
        captured["draft_rounds"] = draft_rounds
        return available.iloc[0]

    monkeypatch.setattr(
        mock_draft_engine,
        "make_cpu_pick",
        fake_cpu_pick,
    )

    mock_draft_engine.run_mock_draft(
        "Test League",
        user_team="Human Team",
        rounds=1,
    )

    assert captured["draft_rounds"] == 16
