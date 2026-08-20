import ast
from dataclasses import FrozenInstanceError
from importlib import import_module
from importlib.util import find_spec
from pathlib import Path

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
    assert 'class="player-row availability-unavailable"' in html


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


def test_preview_css_scopes_the_dark_responsive_draft_night_system():
    """Removing the scoped responsive visual system must fail this contract."""
    module_name = "prototypes.draft_night_preview.styles"
    assert find_spec(module_name) is not None, "styles module must expose preview_css()"
    css = import_module(module_name).preview_css()

    for rule in (
        ".edgeiq-preview",
        "--edgeiq-bg:",
        "--edgeiq-text:",
        "--edgeiq-muted:",
        "font-variant-numeric: tabular-nums",
        ".available-players",
        "overflow: auto",
        ".available-players thead th",
        "position: sticky",
        "top: 0",
        ".draft-header",
        ".primary-grid",
        ".right-rail",
        ".insight-grid",
        ".recommendation-smash",
        ".availability-keeper",
        ".availability-unavailable",
        "@media (max-width: 1450px)",
        "@media (min-width: 1800px)",
        "@media (prefers-reduced-motion: reduce)",
        "animation: none !important",
        "transition: none !important",
    ):
        assert rule in css

    assert "text-overflow: ellipsis" not in css
    assert "line-clamp" not in css


PREVIEW_ROOT = Path(__file__).resolve().parents[1] / "prototypes" / "draft_night_preview"


def _import_roots(path: Path) -> set[str]:
    """Return the roots of all imports declared by a Python module."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", maxsplit=1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", maxsplit=1)[0])
    return roots


def test_preview_modules_do_not_import_production_draft_model():
    """Coupling the isolated prototype to production modules must fail fast."""
    assert not [
        path for path in PREVIEW_ROOT.rglob("*.py")
        if "fantasy_draft_model" in _import_roots(path)
    ]


def test_streamlit_entry_point_composes_each_preview_state_and_renderer():
    """Removing a required preview surface must break the standalone entry point."""
    app_path = PREVIEW_ROOT / "app.py"
    assert app_path.is_file(), "app.py must provide the standalone Streamlit entry point"
    source = app_path.read_text(encoding="utf-8")

    for required_reference in (
        "Live Draft",
        "Draft Complete",
        "render_draft_header",
        "render_available_players",
        "render_roster",
        "render_history",
        "render_explanation",
        "render_at_risk",
        "render_wait_panel",
        "render_draft_complete",
        "preview_css",
    ):
        assert required_reference in source


def test_readme_documents_standalone_synthetic_prototype_boundaries():
    """Documentation must prevent treating prototype data or insights as production output."""
    readme_path = PREVIEW_ROOT / "README.md"
    assert readme_path.is_file(), "README.md must document how to run the preview safely"
    readme = readme_path.read_text(encoding="utf-8")

    for required_text in (
        "streamlit run prototypes/draft_night_preview/app.py",
        "synthetic-only",
        "Prototype display · synthetic risk",
        "Prototype display · synthetic scenario",
        "fantasy_draft_model",
        "persistence",
    ):
        assert required_text in readme
