import pandas as pd

from fantasy_draft_model.engines import cpu_draft
from fantasy_draft_model.engines.manager_tendency_engine import (
    get_manager_tendencies,
)
from fantasy_draft_model.models.league_profile import LEAGUES


TENDENCY_KEYS = [
    "qb_aggression",
    "rb_aggression",
    "wr_aggression",
    "te_aggression",
    "rookie_aggression",
    "risk_tolerance",
]

METADATA_KEYS = [
    "tendency_source",
    "tendency_confidence",
    "tendency_sample_size",
    "is_provisional",
]


def test_unknown_manager_uses_neutral_defaults_with_explicit_metadata():
    profile = get_manager_tendencies("Unknown Manager")

    for key in TENDENCY_KEYS:
        assert profile[key] == 1.0

    assert profile["tendency_source"] == "neutral_default"
    assert profile["tendency_confidence"] == 0.0
    assert profile["tendency_sample_size"] == 0
    assert profile["is_provisional"] is False


def test_manager_name_lookup_is_case_whitespace_and_apostrophe_tolerant():
    canonical = get_manager_tendencies("Parrots")
    normalized = get_manager_tendencies("  pArRoTs  ")

    assert normalized == canonical
    assert normalized["rb_aggression"] == 1.10

    # Apostrophe variants should normalize to the same safe fallback/profile key.
    straight = get_manager_tendencies("BLKWDW'S")
    curly = get_manager_tendencies("blkwdw’s")
    assert curly == straight


def test_every_league_manager_resolves_to_complete_bounded_profile():
    for league in LEAGUES.values():
        for team_name in league["draft_order"]:
            profile = get_manager_tendencies(team_name)

            for key in TENDENCY_KEYS + METADATA_KEYS:
                assert key in profile

            for key in TENDENCY_KEYS:
                assert 0.85 <= float(profile[key]) <= 1.15

            assert 0.0 <= float(profile["tendency_confidence"]) <= 1.0
            assert int(profile["tendency_sample_size"]) >= 0


def test_existing_manual_profiles_are_marked_provisional_not_empirical():
    for team_name in ["Parrots", "Go Time", "Hashbrownies"]:
        profile = get_manager_tendencies(team_name)

        assert profile["tendency_source"] == "manual_provisional"
        assert profile["tendency_confidence"] <= 0.25
        assert profile["tendency_sample_size"] == 0
        assert profile["is_provisional"] is True


def test_qb_aggressive_manager_cannot_bypass_one_qb_guardrail():
    available = pd.DataFrame([
        {
            "player_name_clean": "Best QB",
            "position": "QB",
            "draft_rank": 1.0,
        },
        {
            "player_name_clean": "Best WR",
            "position": "WR",
            "draft_rank": 2.0,
        },
    ])

    counts = {
        "QB": 1,
        "RB": 2,
        "WR": 2,
        "TE": 1,
        "K": 0,
        "DEF": 0,
    }

    pick = cpu_draft.make_cpu_pick(
        available,
        counts,
        round_number=10,
        team_name="Hashbrownies",
        draft_rounds=15,
    )

    assert pick["position"] == "WR"
