"""Immutable synthetic data for the draft-night presentation preview."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DraftHeader:
    current_pick: int
    picks_until_user: int
    next_user_pick: int
    round_number: int
    pick_in_round: int
    user_team: str
    on_clock: bool


@dataclass(frozen=True)
class AvailablePlayer:
    overall_rank: int
    name: str
    position: str
    position_rank: str
    nfl_team: str
    bye_week: int
    tier: int
    projected_points: float
    vorp: float
    edge_score: float
    draft_brain: float
    recommendation: str
    availability: str = "Available"
    keeper_cost: str | None = None
    current_injury: str | None = None
    selected: bool = False


@dataclass(frozen=True)
class RosterEntry:
    position: str
    player: str
    nfl_team: str
    bye_week: int
    round_number: int
    pick_in_round: int
    is_keeper: bool
    keeper_cost: str | None = None


@dataclass(frozen=True)
class DraftHistoryEntry:
    pick_number: int
    round_number: int
    fantasy_team: str
    player: str
    position: str
    nfl_team: str


@dataclass(frozen=True)
class PlayerExplanation:
    player_name: str
    why: str
    warning: str
    projection: float
    vorp: float
    edge_score: float
    confidence: str
    current_injury_status: str
    position_tier: str
    next_player_name: str
    next_player_comparison: str


@dataclass(frozen=True)
class AtRiskEntry:
    player: str
    risk: str
    selecting_teams: tuple[str, ...]
    positional_needs: tuple[str, ...]
    explanation: str


@dataclass(frozen=True)
class WaitScenario:
    survival_chance: str
    tier_drop: str
    replacement_alternatives: tuple[str, ...]
    urgency: str


@dataclass(frozen=True)
class LiveFixture:
    header: DraftHeader
    available_players: tuple[AvailablePlayer, ...]
    roster: tuple[RosterEntry, ...]
    history: tuple[DraftHistoryEntry, ...]
    explanation: PlayerExplanation
    at_risk: tuple[AtRiskEntry, ...]
    wait_scenario: WaitScenario


@dataclass(frozen=True)
class DraftCompleteFixture:
    roster: tuple[RosterEntry, ...]
    recent_picks: tuple[DraftHistoryEntry, ...]
    total_picks: int
    starters: int
    bench_players: int


def live_fixture() -> LiveFixture:
    """Return a deterministic, entirely synthetic live-draft snapshot."""
    return LiveFixture(
        header=DraftHeader(33, 4, 37, 3, 9, "BLKWDW'S", True),
        available_players=(
            AvailablePlayer(18, "Jalen Rivers", "WR", "WR4", "ATL", 12, 2, 254.6, 42.1, 91.4, 95.0, "SMASH PICK", current_injury="Questionable — ankle", selected=True),
            AvailablePlayer(21, "Marcus Vale", "RB", "RB8", "DEN", 10, 2, 238.7, 38.3, 87.8, 89.0, "DRAFT NOW"),
            AvailablePlayer(24, "Devin Cross", "WR", "WR6", "SEA", 8, 2, 242.5, 35.6, 84.5, 85.0, "STRONG TARGET"),
            AvailablePlayer(29, "Theo Grant", "TE", "TE3", "CIN", 5, 3, 178.4, 27.5, 79.6, 78.0, "GOOD VALUE"),
            AvailablePlayer(31, "Caleb North", "QB", "QB7", "MIN", 6, 3, 321.8, 20.8, 74.2, 72.0, "CONSIDER"),
            AvailablePlayer(36, "Isaiah Bell", "RB", "RB13", "PIT", 9, 4, 201.1, 15.2, 67.4, 63.0, "WAIT", availability="Keeper", keeper_cost="R7"),
            AvailablePlayer(42, "Noah Pierce", "WR", "WR15", "LAR", 7, 4, 198.8, 13.4, 61.9, 58.0, "SAFE TO WAIT", availability="Unavailable"),
        ),
        roster=(
            RosterEntry("RB", "Avery Stone", "DET", 8, 1, 9, False),
            RosterEntry("WR", "Miles Hart", "BUF", 7, 7, 9, True, "R7"),
        ),
        history=(
            DraftHistoryEntry(32, 3, "Fourth & Long", "Darius Cole", "RB", "HOU"),
            DraftHistoryEntry(31, 3, "Sunday Funday", "Rico Lane", "WR", "TB"),
            DraftHistoryEntry(30, 3, "Northside", "Wes King", "QB", "DAL"),
        ),
        explanation=PlayerExplanation(
            "Jalen Rivers",
            "Target share and red-zone usage create a clean weekly ceiling.",
            "Ankle practice status remains worth monitoring before kickoff.",
            254.6,
            42.1,
            91.4,
            "High",
            "Questionable — ankle",
            "WR Tier 2",
            "Devin Cross",
            "Cross projects 12.1 points lower and carries less VORP.",
        ),
        at_risk=(
            AtRiskEntry(
                "Jalen Rivers",
                "HIGH",
                ("Fourth & Long", "Sunday Funday", "Northside"),
                ("WR", "WR/RB", "WR"),
                "Three teams ahead need a receiver, so Rivers may not return.",
            ),
            AtRiskEntry(
                "Marcus Vale",
                "MEDIUM",
                ("Fourth & Long",),
                ("RB",),
                "One nearby roster has an immediate running-back need.",
            ),
        ),
        wait_scenario=WaitScenario(
            "42%",
            "WR Tier 2 to WR Tier 3",
            ("Devin Cross", "Theo Grant"),
            "Draft now",
        ),
    )


def complete_fixture() -> DraftCompleteFixture:
    """Return a deterministic synthetic draft-complete snapshot."""
    live = live_fixture()
    return DraftCompleteFixture(
        roster=live.roster + (
            RosterEntry("WR", "Jalen Rivers", "ATL", 12, 3, 9, False),
            RosterEntry("TE", "Theo Grant", "CIN", 5, 5, 9, False),
        ),
        recent_picks=live.history,
        total_picks=15,
        starters=9,
        bench_players=6,
    )
