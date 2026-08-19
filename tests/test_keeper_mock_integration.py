import pandas as pd
import pytest

from fantasy_draft_model.engines import mock_draft_engine


def test_mock_draft_forwards_league_key_to_rankings(monkeypatch):
    class ReachedRankings(Exception):
        pass

    monkeypatch.setattr(
        mock_draft_engine,
        "load_mock_league",
        lambda league_name: {"league_key": "somewhat_related"},
    )

    def fake_build_draft_rankings(league_key):
        assert league_key == "somewhat_related"
        raise ReachedRankings

    monkeypatch.setattr(
        mock_draft_engine,
        "build_draft_rankings",
        fake_build_draft_rankings,
    )

    with pytest.raises(ReachedRankings):
        mock_draft_engine.run_mock_draft(
            "Somewhat Related",
            "Phizucked",
            rounds=1,
        )


def test_keeper_reservations_fail_if_team_missing_from_draft_order(monkeypatch):
    keepers = pd.DataFrame(
        [
            {
                "owner_team": "Missing Team",
                "player_name": "Keeper Player",
                "keeper_type": "standard",
                "keeper_round": 15,
            }
        ]
    )

    monkeypatch.setattr(
        mock_draft_engine,
        "load_mock_keepers",
        lambda league_name: keepers.copy(),
    )

    with pytest.raises(ValueError, match="Missing Team.*draft order"):
        mock_draft_engine.build_keeper_reservations(
            "Drunk Sundays",
            {"Known Team": 1},
            12,
        )


def test_somewhat_related_round_16_keeper_gets_correct_snake_pick(monkeypatch):
    keepers = pd.DataFrame(
        [
            {
                "owner_team": "Phizucked",
                "player_name": "Keeper Player",
                "keeper_type": "standard",
                "keeper_round": 16,
            }
        ]
    )

    monkeypatch.setattr(
        mock_draft_engine,
        "load_mock_keepers",
        lambda league_name: keepers.copy(),
    )

    reservations = mock_draft_engine.build_keeper_reservations(
        "Somewhat Related",
        {"Phizucked": 5},
        12,
    )

    # Round 16 is even, so slot 5 picks 8th in the round:
    # 15 completed rounds * 12 teams + 8 = overall pick 188.
    assert reservations[188] == {
        "team": "Phizucked",
        "player": "Keeper Player",
        "round": 16,
        "keeper_type": "standard",
    }


def test_keeper_player_is_removed_before_cpu_pick(monkeypatch):
    league = {
        "league_key": "drunk_sundays",
        "team_count": 2,
        "draft_order": ["Keeper Team", "CPU Team"],
    }
    rankings = pd.DataFrame(
        [
            {
                "player_name_clean": "Keeper Player",
                "position": "RB",
                "team": "AAA",
                "draft_rank": 1,
                "projected_points": 250.0,
                "is_rookie": False,
            },
            {
                "player_name_clean": "Other Player",
                "position": "WR",
                "team": "BBB",
                "draft_rank": 2,
                "projected_points": 240.0,
                "is_rookie": False,
            },
        ]
    )
    reservations = {
        1: {
            "team": "Keeper Team",
            "player": "Keeper Player",
            "round": 1,
            "keeper_type": "standard",
        }
    }
    captured = {}

    monkeypatch.setattr(
        mock_draft_engine,
        "load_mock_league",
        lambda league_name: league,
    )
    monkeypatch.setattr(
        mock_draft_engine,
        "build_draft_rankings",
        lambda *args, **kwargs: rankings.copy(),
    )
    monkeypatch.setattr(
        mock_draft_engine,
        "build_league_keeper_reservations",
        lambda league_name: reservations.copy(),
    )
    monkeypatch.setattr(
        mock_draft_engine,
        "get_bye_week",
        lambda team: 1,
    )

    def fake_cpu_pick(available, *args, **kwargs):
        captured["available_names"] = available[
            "player_name_clean"
        ].tolist()
        return available.iloc[0]

    monkeypatch.setattr(
        mock_draft_engine,
        "make_cpu_pick",
        fake_cpu_pick,
    )

    results = mock_draft_engine.run_mock_draft(
        "Drunk Sundays",
        "Nobody",
        rounds=1,
    )

    assert captured["available_names"] == ["Other Player"]
    assert sum(
        pick["player"] == "Keeper Player"
        for pick in results
    ) == 1


def test_default_mock_rounds_reach_somewhat_related_round_16_keeper(monkeypatch):
    league = {
        "league_key": "somewhat_related",
        "team_count": 1,
        "draft_order": ["Keeper Team"],
        "draft_rounds": 16,
    }

    rows = [
        {
            "player_name_clean": "Keeper Player",
            "position": "RB",
            "team": "AAA",
            "draft_rank": 1,
            "projected_points": 300.0,
            "is_rookie": False,
        }
    ]
    for index in range(1, 16):
        rows.append(
            {
                "player_name_clean": f"Player {index}",
                "position": "WR",
                "team": "BBB",
                "draft_rank": index + 1,
                "projected_points": 300.0 - index,
                "is_rookie": False,
            }
        )
    rankings = pd.DataFrame(rows)

    reservations = {
        16: {
            "team": "Keeper Team",
            "player": "Keeper Player",
            "round": 16,
            "keeper_type": "standard",
        }
    }

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
        lambda league_name: reservations.copy(),
    )
    monkeypatch.setattr(
        mock_draft_engine,
        "get_bye_week",
        lambda team: 1,
    )
    monkeypatch.setattr(
        mock_draft_engine,
        "make_cpu_pick",
        lambda available, *args, **kwargs: available.iloc[0],
    )

    results = mock_draft_engine.run_mock_draft(
        "Somewhat Related",
        "Nobody",
    )

    assert len(results) == 16
    assert results[-1]["round"] == 16
    assert results[-1]["player"] == "Keeper Player"
    assert results[-1]["keeper"] is True
