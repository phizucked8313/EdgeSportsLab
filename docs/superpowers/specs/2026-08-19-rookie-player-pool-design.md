# 2026 Rookie Identity and Fantasy Player Pool Design

## Goal

Make EdgeIQ distinguish **who is truly a 2026 NFL rookie** from **who belongs in the fantasy draftable player pool**. The current live run reports 227 rookies across QB/RB/WR/TE. `roster_loader.py` already defines `is_rookie` from `rookie_year == 2026`, so the problem must be solved without reverting to the invalid shortcut of treating every player with no 2025 statistics as a rookie.

## Core Principle

Identity and draftability are separate concepts.

- `is_rookie` answers: **Is this player a member of the 2026 NFL rookie class?**
- `is_fantasy_draftable` answers: **Should this player currently enter EdgeIQ rankings/mocks/Top 250-300?**

A legitimate 2026 rookie may be `is_rookie == True` while `is_fantasy_draftable == False`. EdgeIQ must preserve that rookie identity instead of deleting or relabeling the player.

## Canonical Rookie Identity

The canonical rookie flag comes from current 2026 roster metadata, not historical-stat absence.

Primary rule:

```python
is_rookie = rookie_year == 2026
```

Supporting metadata used for diagnostics and consistency checks:

- `rookie_year`
- `entry_year`
- `years_exp`
- `draft_number`
- `status`
- `team`
- `position`

`years_exp == 0`, missing 2025 stats, or `entry_year == 2026` may be useful diagnostics, but none may independently override `rookie_year` unless a future data-quality repair layer explicitly documents why.

## Draftability Model

Create a separate `is_fantasy_draftable` flag after current roster identity has been merged into the master table.

### Always eligible for consideration

A player must first satisfy all of the following:

1. Position is one of `QB`, `RB`, `WR`, `TE`.
2. Has a current NFL team.
3. Is not clearly absent from the current roster pool because of stale historical-only identity.

### Draftable signals

A player is draftable when at least one meaningful signal exists:

- has prior NFL production (`games_played > 0`), or
- is a 2026 rookie with meaningful NFL investment/opportunity, such as positive `draft_number`, or
- is a 2026 rookie carried as active/current roster depth and not clearly a fringe/deep-camp-only record, or
- is a current veteran roster player with a role/status that keeps him fantasy-relevant even if 2025 production was zero.

The first implementation should remain conservative and data-driven. It must not hard-code named players or external consensus rankings.

## Status Handling

Do not equate injury/reserve status with non-draftable. OUT/IR/PUP can still contain valuable fantasy players. Current injury status remains the responsibility of recovery item #1/#10 and should affect projection/ranking, not rookie identity.

Clearly inactive/non-roster/fringe records may be excluded from the draftable pool if the roster/status metadata demonstrates they are not part of a current fantasy-relevant NFL role.

## Historical-Only Veterans

The outer merge in `add_current_roster_identity()` can retain players who have 2025 production but no current 2026 roster row. Those records must not silently enter the live 2026 draft pool merely because they have historical points. Draftability must prefer current roster presence.

## Required Outputs

The master table should expose at least:

- `is_rookie`
- `is_fantasy_draftable`
- `rookie_year`
- `entry_year`
- `years_exp`
- `draft_number`
- `status`
- current `team`
- `position`

A diagnostic helper should make it easy to inspect counts by rookie/draftable/status/position before rankings are generated.

## Integration Boundary

The canonical identity logic remains in `fantasy_draft_model/integrations/roster_loader.py`.

The draftability flag belongs in `fantasy_draft_model/models/projections.py` after current roster identity is merged, because draftability depends on both current roster metadata and historical production.

Downstream projection/ranking code should consume the filtered draftable pool, while diagnostics can still inspect the full master table.

## Non-Goals

This recovery item does not:

- change the multi-factor rookie projection formula from recovery item #2;
- recalibrate QB economics or VORP;
- fix stale depth charts;
- change keeper rules;
- add manager tendencies;
- use ADP or outside rankings to decide who is a rookie.

## Verification Criteria

Recovery item #3 is complete only when all of the following are demonstrated:

1. A known 2026 rookie remains `is_rookie == True` even with zero 2025 stats.
2. A veteran with zero/missing 2025 stats is not mislabeled as a rookie.
3. Rookie identity is explicitly tied to `rookie_year == 2026`.
4. `is_fantasy_draftable` is separate from `is_rookie`.
5. The live draftable rookie count is materially smaller than the raw full-roster rookie count without erasing legitimate rookies from the master table.
6. The projection engine/rankings operate on the draftable pool rather than all camp/fringe records.
7. Existing injury and rookie-projection regression tests still pass.
