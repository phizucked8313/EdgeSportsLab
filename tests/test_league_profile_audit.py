from fantasy_draft_model.engines.mock_draft_engine import calculate_snake_pick
from fantasy_draft_model.models.league_profile import get_league


DRUNK_SUNDAYS_ORDER = [
    "Parrots",
    "Go Time",
    "Hashbrownies",
    "The Bird Is The Word",
    "Tez Swagg",
    "Diamonds Forever Inn The House",
    "Long & Deep",
    "Only Here To Beat My Husband",
    "BLKWDW'S",
    "Door Dash At 2AM",
    "It's Geoffrey James Beeitch",
    "Hawk Tua",
]

SOMEWHAT_RELATED_ORDER = [
    "Stopped Short",
    "Winner in Mexico",
    "Sixty Niners",
    "Fat Dink",
    "Phizucked",
    "Buttnuggets",
    "Hashbrownies",
    "Retriever's",
    "Phinatic",
    "S U C K I T",
    "Injured Reserve",
    "Jabronies",
]


def test_drunk_sundays_profile_matches_known_draft_order():
    league = get_league("Drunk Sundays")

    assert league["team_count"] == 12
    assert league["draft_order"] == DRUNK_SUNDAYS_ORDER
    assert len(set(league["draft_order"])) == 12
    assert league["draft_order"].index("BLKWDW'S") + 1 == 9


def test_somewhat_related_profile_matches_known_draft_order():
    league = get_league("Somewhat Related")

    assert league["team_count"] == 12
    assert league["draft_order"] == SOMEWHAT_RELATED_ORDER
    assert len(set(league["draft_order"])) == 12
    assert league["draft_order"].index("Phizucked") + 1 == 5


def test_roster_size_matches_starters_plus_bench_for_each_league():
    for league_name in ("Drunk Sundays", "Somewhat Related"):
        league = get_league(league_name)
        expected_roster_size = sum(league["starters"].values()) + league["bench_size"]

        assert league["roster_size"] == expected_roster_size


def test_draft_rounds_match_roster_size_for_each_league():
    for league_name in ("Drunk Sundays", "Somewhat Related"):
        league = get_league(league_name)

        assert league["draft_rounds"] == league["roster_size"], (
            f"{league_name} draft_rounds={league['draft_rounds']} "
            f"but roster_size={league['roster_size']}"
        )


def test_user_snake_pick_math_matches_each_profile():
    drunk = get_league("Drunk Sundays")
    somewhat = get_league("Somewhat Related")

    drunk_slot = drunk["draft_order"].index("BLKWDW'S") + 1
    somewhat_slot = somewhat["draft_order"].index("Phizucked") + 1

    assert calculate_snake_pick(1, drunk_slot, drunk["team_count"]) == 9
    assert calculate_snake_pick(2, drunk_slot, drunk["team_count"]) == 16

    assert calculate_snake_pick(1, somewhat_slot, somewhat["team_count"]) == 5
    assert calculate_snake_pick(2, somewhat_slot, somewhat["team_count"]) == 20
