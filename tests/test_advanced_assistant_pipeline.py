import pandas as pd

from fantasy_draft_model import draft_assistant


def _base_rankings():
    return pd.DataFrame(
        [
            {
                "player_name_clean": "Player A",
                "position": "RB",
                "team": "BUF",
                "bye_week": 7,
                "draft_rank": 1,
            },
            {
                "player_name_clean": "Player B",
                "position": "WR",
                "team": "DAL",
                "bye_week": 14,
                "draft_rank": 2,
            },
        ]
    )


def test_build_draft_assistant_passes_league_key_and_context(monkeypatch):
    calls = []

    def fake_rankings(league_key):
        calls.append(("rankings", league_key))
        return _base_rankings()

    def fake_pressure(df):
        calls.append(("pressure", None))
        result = df.copy()
        result["pressure_score"] = [70.0, 40.0]
        result["pressure_label"] = ["ELEVATED", "MODERATE"]
        result["pressure_bar"] = ["PRESSURE-A", "PRESSURE-B"]
        return result

    def fake_brain(df, draft_context):
        calls.append(("brain", dict(draft_context)))
        assert "pressure_score" in df.columns
        result = df.copy()
        result["brain_score"] = [60.0, 90.0]
        result["brain_recommendation"] = ["GOOD VALUE", "SMASH PICK"]
        result["brain_reasons"] = [["reason-a"], ["reason-b"]]
        result["brain_warnings"] = [[], []]
        return result

    monkeypatch.setattr(draft_assistant, "build_draft_rankings", fake_rankings)
    monkeypatch.setattr(
        draft_assistant,
        "add_pressure_meter",
        fake_pressure,
        raising=False,
    )
    monkeypatch.setattr(draft_assistant, "add_draft_brain", fake_brain)

    board = draft_assistant.build_draft_assistant(
        "drunk_sundays",
        draft_context={"picks_until_user": 7},
    )

    assert calls == [
        ("rankings", "drunk_sundays"),
        ("pressure", None),
        ("brain", {"picks_until_user": 7}),
    ]
    assert board["player_name_clean"].tolist() == ["Player B", "Player A"]


def test_final_assistant_board_exposes_pressure_and_brain_outputs(monkeypatch):
    monkeypatch.setattr(
        draft_assistant,
        "build_draft_rankings",
        lambda league_key: _base_rankings(),
    )

    def fake_pressure(df):
        result = df.copy()
        result["pressure_score"] = 55.0
        result["pressure_label"] = "MODERATE"
        result["pressure_bar"] = "PRESSURE"
        return result

    def fake_brain(df, draft_context):
        result = df.copy()
        result["brain_score"] = [80.0, 70.0]
        result["brain_recommendation"] = ["DRAFT NOW", "STRONG TARGET"]
        result["brain_reasons"] = [["reason"], ["reason"]]
        result["brain_warnings"] = [[], ["warning"]]
        return result

    monkeypatch.setattr(
        draft_assistant,
        "add_pressure_meter",
        fake_pressure,
        raising=False,
    )
    monkeypatch.setattr(draft_assistant, "add_draft_brain", fake_brain)

    board = draft_assistant.build_draft_assistant(
        "drunk_sundays",
        draft_context={"picks_until_user": 5},
    )

    required = {
        "pressure_score",
        "pressure_label",
        "pressure_bar",
        "brain_score",
        "brain_recommendation",
        "brain_reasons",
        "brain_warnings",
    }

    assert required.issubset(board.columns)
    assert board["brain_score"].is_monotonic_decreasing
