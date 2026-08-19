import pandas as pd

from fantasy_draft_model.engines import cpu_draft


def _available():
    return pd.DataFrame([
        {
            "player_name_clean": "Top QB",
            "position": "QB",
            "draft_rank": 1.0,
        },
        {
            "player_name_clean": "Top WR",
            "position": "WR",
            "draft_rank": 2.0,
        },
    ])


def _neutral_tendencies(team_name):
    return {
        "qb_aggression": 1.0,
        "rb_aggression": 1.0,
        "wr_aggression": 1.0,
        "te_aggression": 1.0,
        "rookie_aggression": 1.0,
        "risk_tolerance": 1.0,
    }


def test_cpu_without_qb_can_take_first_qb_early(monkeypatch):
    monkeypatch.setattr(
        cpu_draft,
        "get_manager_tendencies",
        _neutral_tendencies,
    )

    pick = cpu_draft.make_cpu_pick(
        _available(),
        {"QB": 0, "RB": 2, "WR": 2, "TE": 1},
        round_number=3,
        team_name="Test Team",
    )

    assert pick["position"] == "QB"
    assert pick["player_name_clean"] == "Top QB"


def test_cpu_with_one_qb_blocks_second_qb_through_round_10(monkeypatch):
    monkeypatch.setattr(
        cpu_draft,
        "get_manager_tendencies",
        _neutral_tendencies,
    )

    pick = cpu_draft.make_cpu_pick(
        _available(),
        {"QB": 1, "RB": 2, "WR": 2, "TE": 1},
        round_number=10,
        team_name="Test Team",
    )

    assert pick["position"] == "WR"
    assert pick["player_name_clean"] == "Top WR"


def test_cpu_with_one_qb_can_take_backup_starting_round_11(monkeypatch):
    monkeypatch.setattr(
        cpu_draft,
        "get_manager_tendencies",
        _neutral_tendencies,
    )

    pick = cpu_draft.make_cpu_pick(
        _available(),
        {"QB": 1, "RB": 2, "WR": 2, "TE": 1},
        round_number=11,
        team_name="Test Team",
    )

    assert pick["position"] == "QB"
    assert pick["player_name_clean"] == "Top QB"


def test_cpu_with_two_qbs_never_takes_third_qb(monkeypatch):
    monkeypatch.setattr(
        cpu_draft,
        "get_manager_tendencies",
        _neutral_tendencies,
    )

    pick = cpu_draft.make_cpu_pick(
        _available(),
        {
            "QB": 2,
            "RB": 3,
            "WR": 3,
            "TE": 1,
            "K": 1,
            "DEF": 1,
        },
        round_number=11,
        team_name="Test Team",
    )

    assert pick["position"] == "WR"
    assert pick["player_name_clean"] == "Top WR"
