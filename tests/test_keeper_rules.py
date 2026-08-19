import pandas as pd
import pytest

from fantasy_draft_model import keepers
from fantasy_draft_model.models.league_profile import get_league


def test_drunk_sundays_keeper_policy_is_explicit():
    league = get_league("Drunk Sundays")

    assert league["league_key"] == "drunk_sundays"
    assert league["keeper_rules"] == {
        "standard": 15,
        "rookie": 3,
    }


def test_somewhat_related_keeper_policy_is_explicit():
    league = get_league("Somewhat Related")

    assert league["league_key"] == "somewhat_related"
    assert league["keeper_rules"] == {
        "standard": 16,
    }


def test_somewhat_related_standard_keeper_costs_round_16(tmp_path, monkeypatch):
    keeper_file = tmp_path / "keepers.csv"
    monkeypatch.setattr(keepers, "KEEPER_FILE", keeper_file)

    keepers.add_keeper(
        "Somewhat Related",
        "Phizucked",
        "Example Veteran",
        "standard",
    )

    saved = pd.read_csv(keeper_file)

    assert len(saved) == 1
    assert saved.loc[0, "keeper_type"] == "standard"
    assert saved.loc[0, "keeper_round"] == 16


def test_somewhat_related_rejects_rookie_keeper_type(tmp_path, monkeypatch):
    keeper_file = tmp_path / "keepers.csv"
    monkeypatch.setattr(keepers, "KEEPER_FILE", keeper_file)

    with pytest.raises(ValueError, match="rookie"):
        keepers.add_keeper(
            "Somewhat Related",
            "Phizucked",
            "Example Rookie",
            "rookie",
        )


def test_drunk_sundays_keeps_existing_round_costs(tmp_path, monkeypatch):
    keeper_file = tmp_path / "keepers.csv"
    monkeypatch.setattr(keepers, "KEEPER_FILE", keeper_file)

    keepers.add_keeper(
        "Drunk Sundays",
        "BLKWDW'S",
        "Example Veteran",
        "standard",
    )
    keepers.add_keeper(
        "Drunk Sundays",
        "BLKWDW'S",
        "Example Rookie",
        "rookie",
    )

    saved = pd.read_csv(keeper_file).set_index("player_name")

    assert saved.loc["Example Veteran", "keeper_round"] == 15
    assert saved.loc["Example Rookie", "keeper_round"] == 3
