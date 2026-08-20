from dataclasses import FrozenInstanceError

import pytest

from prototypes.draft_night_preview.components import (
    recommendation_class,
    render_at_risk,
    render_available_players,
    render_draft_complete,
    render_draft_header,
    render_explanation,
    render_history,
    render_roster,
    render_wait_panel,
)
from prototypes.draft_night_preview.fixtures import complete_fixture, live_fixture


def test_live_fixture_is_immutable_and_covers_every_recommendation_state():
    fixture = live_fixture()

    assert {player.recommendation for player in fixture.available_players} == {
        "SMASH PICK",
        "DRAFT NOW",
        "STRONG TARGET",
        "GOOD VALUE",
        "CONSIDER",
        "WAIT",
        "SAFE TO WAIT",
    }
    with pytest.raises(FrozenInstanceError):
        fixture.header.current_pick = 99


def test_draft_header_emits_required_context_and_clock_state():
    html = render_draft_header(live_fixture().header)

    for label in (
        "SYNTHETIC PROTOTYPE",
        "Current Pick",
        "Picks Until BLKWDW'S",
        "Next BLKWDW'S Pick",
        "Round",
        "Pick in Round",
        "ON THE CLOCK",
    ):
        assert label in html


def test_available_players_emits_columns_recommendations_and_statuses():
    html = render_available_players(live_fixture().available_players)

    for label in (
        "Overall Rank",
        "Player",
        "Position Rank",
        "NFL Team",
        "Bye",
        "Tier",
        "Projected Points",
        "VORP",
        "EdgeScore",
        "Draft Brain",
        "Recommendation",
        "Availability",
        "SMASH PICK",
        "DRAFT NOW",
        "STRONG TARGET",
        "GOOD VALUE",
        "CONSIDER",
        "WAIT",
        "SAFE TO WAIT",
        "Keeper · Cost R7",
        "Unavailable",
        "Current injury: Questionable — ankle",
        "WR Tier 2",
    ):
        assert label in html


def test_roster_and_history_show_required_draft_context():
    fixture = live_fixture()

    roster_html = render_roster(fixture.roster)
    history_html = render_history(fixture.history)

    for label in ("Your Roster", "Position", "Player", "NFL Team", "Bye", "Round/Pick", "Keeper", "Cost R7", "Drafted"):
        assert label in roster_html
    for label in ("Recent Draft History", "Pick", "Round", "Fantasy Team", "Player", "Position", "NFL Team"):
        assert label in history_html


def test_explanation_emits_metrics_warning_injury_numbered_tier_and_comparison():
    html = render_explanation(live_fixture().explanation)

    for label in (
        "Why EdgeIQ likes",
        "Warnings",
        "Projection",
        "VORP",
        "EdgeScore",
        "Confidence",
        "Current injury status",
        "Position Tier",
        "Next player comparison",
        "WR Tier 2",
        "Next:",
    ):
        assert label in html


def test_prototype_panels_include_disclaimers_and_all_fixture_fields():
    fixture = live_fixture()

    risk_html = render_at_risk(fixture.at_risk)
    wait_html = render_wait_panel(fixture.wait_scenario)

    for label in (
        "At Risk Before Your Next Pick",
        "Prototype display · synthetic risk",
        "Risk",
        "Teams selecting before BLKWDW'S",
        "Positional needs",
        "Why",
    ):
        assert label in risk_html
    for label in (
        "What If I Wait",
        "Prototype display · synthetic scenario",
        "Survival chance",
        "Tier drop",
        "Replacement alternatives",
        "Urgency",
    ):
        assert label in wait_html


def test_draft_complete_output_contains_conclusive_summary_and_recent_picks():
    html = render_draft_complete(complete_fixture())

    for label in (
        "Draft Complete",
        "SYNTHETIC PROTOTYPE",
        "Roster recap",
        "Draft summary",
        "Recent picks",
        "Total picks",
    ):
        assert label in html


def test_recommendation_class_maps_known_labels_and_falls_back_to_neutral():
    assert recommendation_class("SMASH PICK") == "recommendation-smash"
    assert recommendation_class("SAFE TO WAIT") == "recommendation-safe-wait"
    assert recommendation_class("unrecognized") == "recommendation-neutral"


def test_renderers_escape_fixture_provided_html():
    fixture = live_fixture()
    player = fixture.available_players[0]
    escaped_player = type(player)(
        **{**player.__dict__, "name": "<script>alert('x')</script>"}
    )

    html = render_available_players((escaped_player,))

    assert "<script>" not in html
    assert "&lt;script&gt;alert('x')&lt;/script&gt;" in html
