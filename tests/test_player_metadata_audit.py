import pandas as pd

from fantasy_draft_model import rankings
from fantasy_draft_model.models.projections import merge_current_roster_identity
from fantasy_draft_model.models.schedule import BYE_WEEKS, get_bye_week


def test_current_roster_team_and_position_override_stale_historical_metadata():
    historical = pd.DataFrame([
        {
            "player_id": "00-test-player",
            "player_name_clean": "Test Player",
            "team": "OLD",
            "position": "RB",
            "games_played": 17,
        }
    ])
    current_roster = pd.DataFrame([
        {
            "player_id": "00-test-player",
            "roster_player_name": "Test Player",
            "current_team": "NEW",
            "current_position": "WR",
            "status": "ACT",
        }
    ])

    result = merge_current_roster_identity(
        historical,
        current_roster,
    )

    row = result.iloc[0]
    assert row["team"] == "NEW"
    assert row["position"] == "WR"
    assert bool(row["on_current_roster"]) is True


def test_all_32_nfl_teams_resolve_to_valid_2026_bye_week():
    assert len(BYE_WEEKS) == 32
    assert all(
        isinstance(get_bye_week(team), int)
        and 1 <= get_bye_week(team) <= 18
        for team in BYE_WEEKS
    )


def _stub_rankings_pipeline(monkeypatch):
    offense = pd.DataFrame([
        {
            "player_name_clean": "Offensive Player",
            "team": "BUF",
            "position": "WR",
            "position_rank": 1,
        }
    ])

    monkeypatch.setattr(
        rankings,
        "build_2026_projections",
        lambda league_key: offense.copy(),
    )

    for name in [
        "calculate_draft_score",
        "create_overall_rankings",
        "add_position_rank_label",
        "add_draft_value_label",
        "add_football_intelligence",
    ]:
        monkeypatch.setattr(
            rankings,
            name,
            lambda df: df.copy(),
        )

    monkeypatch.setattr(
        rankings,
        "build_kicker_rankings",
        lambda: pd.DataFrame([
            {
                "player_name_clean": "Test Kicker",
                "team": "DAL",
                "position": "K",
                "position_rank": 1,
            }
        ]),
    )
    monkeypatch.setattr(
        rankings,
        "build_defense_rankings",
        lambda: pd.DataFrame([
            {
                "player_name_clean": "Test Defense",
                "team": "BAL",
                "position": "DEF",
                "position_rank": 1,
            }
        ]),
    )


def test_build_draft_rankings_attaches_bye_week_to_offensive_players(monkeypatch):
    _stub_rankings_pipeline(monkeypatch)

    result = rankings.build_draft_rankings("drunk_sundays")
    offense = result.loc[
        result["player_name_clean"] == "Offensive Player"
    ].iloc[0]

    assert offense["team"] == "BUF"
    assert offense["position"] == "WR"
    assert offense["bye_week"] == get_bye_week("BUF")


def test_special_teams_keep_team_position_and_receive_bye_week(monkeypatch):
    _stub_rankings_pipeline(monkeypatch)

    result = rankings.build_draft_rankings("drunk_sundays")
    indexed = result.set_index("player_name_clean")

    kicker = indexed.loc["Test Kicker"]
    defense = indexed.loc["Test Defense"]

    assert kicker["team"] == "DAL"
    assert kicker["position"] == "K"
    assert kicker["bye_week"] == get_bye_week("DAL")

    assert defense["team"] == "BAL"
    assert defense["position"] == "DEF"
    assert defense["bye_week"] == get_bye_week("BAL")
