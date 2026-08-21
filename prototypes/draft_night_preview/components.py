"""Escaped, dependency-free HTML renderers for the synthetic preview."""

from html import escape
from typing import Iterable

from .fixtures import (
    AtRiskEntry,
    AvailablePlayer,
    DraftCompleteFixture,
    DraftHeader,
    DraftHistoryEntry,
    PlayerExplanation,
    RosterEntry,
    WaitScenario,
)


RECOMMENDATION_CLASSES = {
    "SMASH PICK": "recommendation-smash",
    "DRAFT NOW": "recommendation-draft-now",
    "STRONG TARGET": "recommendation-strong-target",
    "GOOD VALUE": "recommendation-good-value",
    "CONSIDER": "recommendation-consider",
    "WAIT": "recommendation-wait",
    "SAFE TO WAIT": "recommendation-safe-wait",
}

AVAILABILITY_CLASSES = {
    "Available": "availability-available",
    "Keeper": "availability-keeper",
    "Unavailable": "availability-unavailable",
}


def _text(value: object) -> str:
    return escape(str(value), quote=False)


def _cell(value: object) -> str:
    return f"<td>{_text(value)}</td>"


def recommendation_class(label: str) -> str:
    """Map a controlled recommendation label to a safe display class."""
    return RECOMMENDATION_CLASSES.get(label, "recommendation-neutral")


def render_draft_header(header: DraftHeader) -> str:
    clock = "ON THE CLOCK" if header.on_clock else "WAITING"
    return (
        '<section class="draft-header" aria-label="Draft context">'
        '<span class="prototype-marker">SYNTHETIC PROTOTYPE</span>'
        f'<div><span>Current Pick</span><strong>{header.current_pick}</strong></div>'
        f'<div><span>Picks Until {_text(header.user_team)}</span><strong>{header.picks_until_user}</strong></div>'
        f'<div><span>Next {_text(header.user_team)} Pick</span><strong>{header.next_user_pick}</strong></div>'
        f'<div><span>Round</span><strong>{header.round_number}</strong></div>'
        f'<div><span>Pick in Round</span><strong>{header.pick_in_round}</strong></div>'
        f'<strong class="clock-state">{clock}</strong>'
        '</section>'
    )


def render_available_players(players: Iterable[AvailablePlayer]) -> str:
    headers = (
        "Overall Rank", "Player", "Position Rank", "NFL Team", "Bye", "Tier",
        "Projected Points", "VORP", "EdgeScore", "Draft Brain", "Recommendation", "Availability",
    )
    rows = []
    for player in players:
        injury = f"<small>Current injury: {_text(player.current_injury)}</small>" if player.current_injury else ""
        availability = _text(player.availability)
        if player.keeper_cost:
            availability += f" · Cost {_text(player.keeper_cost)}"
        row_class = " selected-player" if player.selected else ""
        rows.append(
            f'<tr class="player-row {AVAILABILITY_CLASSES.get(player.availability, "availability-neutral")}{row_class}">'
            f'{_cell(player.overall_rank)}{_cell(player.name)}{_cell(player.position_rank)}'
            f'{_cell(player.nfl_team)}{_cell(player.bye_week)}{_cell(f"{player.position} Tier {player.tier}")}'
            f'{_cell(f"{player.projected_points:.1f}")}{_cell(f"{player.vorp:.1f}")}'
            f'{_cell(f"{player.edge_score:.1f}")}{_cell(f"{player.draft_brain:.1f}")}'
            f'<td><span class="{recommendation_class(player.recommendation)}">{_text(player.recommendation)}</span></td>'
            f'<td>{availability}{injury}</td></tr>'
        )
    header_html = "".join(f"<th scope=\"col\">{_text(header)}</th>" for header in headers)
    return f'<section class="available-players"><h2>Available Players</h2><table><thead><tr>{header_html}</tr></thead><tbody>{"".join(rows)}</tbody></table></section>'


def render_roster(roster: Iterable[RosterEntry]) -> str:
    rows = []
    for entry in roster:
        state = f"Keeper · Cost {_text(entry.keeper_cost)}" if entry.is_keeper else "Drafted"
        rows.append(
            f"<tr>{_cell(entry.position)}{_cell(entry.player)}{_cell(entry.nfl_team)}{_cell(entry.bye_week)}"
            f"{_cell(f'R{entry.round_number}/P{entry.pick_in_round}')}<td>{state}</td></tr>"
        )
    return '<section class="roster"><h2>Your Roster</h2><table><thead><tr><th>Position</th><th>Player</th><th>NFL Team</th><th>Bye</th><th>Round/Pick</th><th>State</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table></section>"


def render_history(history: Iterable[DraftHistoryEntry]) -> str:
    rows = [
        f"<tr>{_cell(entry.pick_number)}{_cell(entry.round_number)}{_cell(entry.fantasy_team)}{_cell(entry.player)}{_cell(entry.position)}{_cell(entry.nfl_team)}</tr>"
        for entry in history
    ]
    return '<section class="draft-history"><h2>Recent Draft History</h2><table><thead><tr><th>Pick</th><th>Round</th><th>Fantasy Team</th><th>Player</th><th>Position</th><th>NFL Team</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table></section>"


def render_explanation(explanation: PlayerExplanation) -> str:
    return (
        '<section class="player-explanation">'
        f'<h2>Why EdgeIQ likes {_text(explanation.player_name)}</h2>'
        f'<p>{_text(explanation.why)}</p><h3>Warnings</h3><p>{_text(explanation.warning)}</p>'
        f'<dl><dt>Projection</dt><dd>{explanation.projection:.1f}</dd><dt>VORP</dt><dd>{explanation.vorp:.1f}</dd>'
        f'<dt>EdgeScore</dt><dd>{explanation.edge_score:.1f}</dd><dt>Confidence</dt><dd>{_text(explanation.confidence)}</dd>'
        f'<dt>Current injury status</dt><dd>{_text(explanation.current_injury_status)}</dd>'
        f'<dt>Position Tier</dt><dd>{_text(explanation.position_tier)}</dd></dl>'
        f'<h3>Next player comparison</h3><p>Next: {_text(explanation.next_player_name)} — {_text(explanation.next_player_comparison)}</p>'
        '</section>'
    )


def render_at_risk(entries: Iterable[AtRiskEntry]) -> str:
    cards = []
    for entry in entries:
        cards.append(
            f'<article><h3>{_text(entry.player)} <span>{_text(entry.risk)}</span></h3>'
            f'<dl><dt>Risk</dt><dd>{_text(entry.risk)}</dd><dt>Teams selecting before BLKWDW\'S</dt><dd>{_text(", ".join(entry.selecting_teams))}</dd>'
            f'<dt>Positional needs</dt><dd>{_text(", ".join(entry.positional_needs))}</dd><dt>Why</dt><dd>{_text(entry.explanation)}</dd></dl></article>'
        )
    return '<section class="at-risk"><h2>At Risk Before Your Next Pick</h2><p class="synthetic-note">Prototype display · synthetic risk</p>' + "".join(cards) + "</section>"


def render_wait_panel(scenario: WaitScenario) -> str:
    return (
        '<section class="wait-panel"><h2>What If I Wait</h2><p class="synthetic-note">Prototype display · synthetic scenario</p><dl>'
        f'<dt>Survival chance</dt><dd>{_text(scenario.survival_chance)}</dd><dt>Tier drop</dt><dd>{_text(scenario.tier_drop)}</dd>'
        f'<dt>Replacement alternatives</dt><dd>{_text(", ".join(scenario.replacement_alternatives))}</dd><dt>Urgency</dt><dd>{_text(scenario.urgency)}</dd>'
        '</dl></section>'
    )


def render_draft_complete(summary: DraftCompleteFixture) -> str:
    roster_html = render_roster(summary.roster)
    history_html = render_history(summary.recent_picks)
    return (
        '<section class="draft-complete"><span class="prototype-marker">SYNTHETIC PROTOTYPE</span><h1>Draft Complete</h1>'
        f'<h2>Draft summary</h2><dl><dt>Total picks</dt><dd>{summary.total_picks}</dd><dt>Starters</dt><dd>{summary.starters}</dd><dt>Bench players</dt><dd>{summary.bench_players}</dd></dl>'
        f'<h2>Roster recap</h2>{roster_html}<h2>Recent picks</h2>{history_html}</section>'
    )
