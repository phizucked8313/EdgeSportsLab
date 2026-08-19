from fantasy_draft_model.keepers import load_keepers
from fantasy_draft_model.engines.mock_draft_engine import (
    build_keeper_reservations,
    build_draft_slot_map,
)
from fantasy_draft_model.models.league_profile import get_league


def test_drunk_sundays_live_keeper_data_is_valid_and_collision_free():
    league_name = "Drunk Sundays"
    league = get_league(league_name)
    keepers = load_keepers(league_name)
    draft_slots = build_draft_slot_map(league_name)

    assert len(keepers) == 15
    assert keepers["player_name"].str.lower().is_unique
    assert set(keepers["owner_team"]).issubset(set(league["draft_order"]))

    allowed_rounds = set(league["keeper_rules"].values())
    assert set(keepers["keeper_round"].astype(int)).issubset(allowed_rounds)

    reservations = build_keeper_reservations(
        league_name,
        draft_slots,
        league["team_count"],
    )

    assert len(reservations) == len(keepers)
    assert len(set(reservations)) == len(keepers)

    rookie_reservations = {
        pick: reservation["player"]
        for pick, reservation in reservations.items()
        if reservation["keeper_type"] == "rookie"
    }

    assert rookie_reservations == {
        26: "Omarion Hampton",
        33: "Ashton Jeanty",
        35: "Quinshon Judkins",
    }

    standard_picks = sorted(
        pick
        for pick, reservation in reservations.items()
        if reservation["keeper_type"] == "standard"
    )

    assert standard_picks == list(range(169, 181))
