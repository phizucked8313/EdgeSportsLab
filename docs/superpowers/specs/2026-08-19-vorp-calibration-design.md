# EdgeIQ VORP Calibration Design

## Goal

Replace hardcoded positional replacement ranks with league-settings-driven replacement levels that reflect a 12-team, 1-QB, 2-RB, 2-WR, 1-TE, 2-FLEX (RB/WR) starting lineup.

## Problem

`fantasy_draft_model/engines/vorp_engine.py` currently hardcodes:

- QB12
- RB24
- WR24
- TE12

That counts mandatory starters but ignores the league's 24 FLEX starting slots. As a result, RB and WR replacement points are too high and their VORP is understated relative to the actual player demand created by the lineup.

The repository already has authoritative league settings in `fantasy_draft_model/config/league_settings.json`, but the VORP engine does not use them.

## Approved Approach

Use dynamic FLEX-aware replacement ranks derived from projected points and the configured lineup.

### Mandatory starter demand

For each position:

`mandatory_starters = teams * lineup[position]`

For the current league:

- QB = 12 * 1 = 12
- RB = 12 * 2 = 24
- WR = 12 * 2 = 24
- TE = 12 * 1 = 12

### FLEX demand

The league has:

`flex_slots = teams * lineup["FLEX"]`

For the current league:

`12 * 2 = 24 FLEX slots`

FLEX eligibility for this model is RB/WR only, matching the league setup used by EdgeIQ.

To allocate those slots:

1. Sort RBs by `projected_points` descending and remove the top 24 mandatory RB starters.
2. Sort WRs by `projected_points` descending and remove the top 24 mandatory WR starters.
3. Combine the remaining RB and WR candidates.
4. Sort that combined pool by `projected_points` descending.
5. Take the top 24 FLEX candidates.
6. Count how many are RBs and how many are WRs.
7. Add those counts to the mandatory RB/WR starter counts.

Example: if the top 24 FLEX candidates contain 15 RBs and 9 WRs, replacement ranks become RB39 and WR33.

QB and TE do not receive FLEX allocations.

## Interfaces

Add a helper in `fantasy_draft_model/engines/vorp_engine.py`:

```python
def calculate_replacement_ranks(
    df: pd.DataFrame,
    league_settings: dict | None = None,
) -> dict[str, int]:
```

Behavior:

- If `league_settings` is supplied, use it directly. This makes unit testing deterministic.
- If omitted, load settings with `fantasy_draft_model.config.load_league_settings()`.
- Return replacement ranks for QB/RB/WR/TE.
- Use `projected_points` to allocate FLEX slots.
- Do not mutate the input DataFrame.

Update:

```python
def calculate_vorp(
    df: pd.DataFrame,
    league_settings: dict | None = None,
) -> pd.DataFrame:
```

`calculate_vorp()` will call `calculate_replacement_ranks()` and then keep the current VORP mechanics: the player at each derived replacement rank establishes `replacement_points`, and `vorp = projected_points - replacement_points`.

## Guardrails

- No manual RB/WR split.
- No ADP or consensus-rank input.
- No changes to projections.
- No changes to #4 QB scoring logic.
- No keeper adjustments in this task.
- No historical manager-behavior calibration in this task.
- Existing 12-team lineup settings remain the source of league structure.
- If fewer eligible FLEX candidates exist than configured FLEX slots, allocate all available candidates without crashing.
- If a position has fewer players than its calculated replacement rank, preserve the current fallback behavior of using the minimum available projected points for that position.

## Validation

Unit tests must prove:

1. Mandatory starter counts come from league settings rather than constants.
2. FLEX slots are allocated dynamically to RB/WR according to projected points.
3. QB and TE replacement ranks remain based only on mandatory starters.
4. Changing lineup settings changes the calculated replacement ranks.
5. `calculate_vorp()` uses the dynamically calculated replacement ranks.

Live validation must print the actual derived QB/RB/WR/TE replacement ranks and replacement points from the 2026 projection pool, then rerun the full test suite before #5 is marked complete.
