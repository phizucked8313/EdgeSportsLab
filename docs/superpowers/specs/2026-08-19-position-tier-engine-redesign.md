# Position Tier Engine Redesign

## Summary

EdgeIQ will replace descriptive tier labels such as `ELITE SOLO TIER`, `SMALL TIER`, `LIMITED TIER`, and `DEPTH AVAILABLE` with numbered tiers that restart independently at each fantasy position.

Examples:

- `RB Tier 1`, `RB Tier 2`, `RB Tier 3`, ...
- `WR Tier 1`, `WR Tier 2`, `WR Tier 3`, ...
- `TE Tier 1`, `TE Tier 2`, `TE Tier 3`, ...
- `QB Tier 1`, `QB Tier 2`, `QB Tier 3`, ...

The redesign also replaces the current fixed tier-gap rule with a progressive threshold so later tiers require a larger separation before a new tier is created. Scarcity will no longer equate "one player in a tier" with "elite." Instead, scarcity will use tier number, players remaining in the tier, and the drop to the next tier.

## Goals

1. Make tier labels intuitive and position-specific.
2. Prevent a later singleton tier, such as RB Tier 6 containing one player, from receiving the same scarcity treatment as an isolated Tier 1 player.
3. Reduce over-fragmentation caused by applying the same tier-gap threshold at every depth of a position.
4. Preserve model independence: no manual RB, WR, TE, or QB ranking boosts.
5. Make live Draft Brain scarcity reflect the players who are still available, not players already drafted or reserved as keepers.
6. Keep the tier engine deterministic, explainable, and regression-tested.

## Non-goals

- Do not manually move individual players.
- Do not add a blanket RB bonus or TE penalty.
- Do not change projection formulas, VORP replacement ranks, EdgeScore weights, or league scoring in this redesign.
- Do not tune tier thresholds to match outside ADP or consensus rankings.
- Do not renumber a player's base tier during the draft. Base tier identity remains stable; only live scarcity changes as players leave the board.

## Current Problems

### Descriptive status conflates tier quality with tier size

The current engine labels every one-player tier `ELITE SOLO TIER`, regardless of whether it is Tier 1 or a much later tier. Downstream systems then map that label to maximum scarcity.

This causes an isolated player in a later tier to receive the same scarcity treatment as a genuinely elite top-tier player.

### Flat gap thresholds over-fragment later tiers

Current base thresholds are:

| Position | Base threshold |
| --- | ---: |
| QB | 18 |
| RB | 14 |
| WR | 14 |
| TE | 12 |

The same threshold is applied at every tier depth. That is acceptable near the top of the player pool, where small differences can matter, but it creates too many later singleton tiers.

### Live pressure is calculated before unavailable players are removed

The current War Room flow builds Pressure and Draft Brain from the full rankings board, then removes drafted players and keepers afterward when the UI snapshot is built. That means live board pressure and any future "players remaining in tier" calculation can still see unavailable players.

The redesigned tier system must calculate live scarcity from the available board before Pressure and Draft Brain run.

## Tier Assignment

### Position-local numbering

Each position is tiered independently. Tier numbering always starts at 1 within that position.

The player sort order inside a position remains:

1. `projected_points` descending
2. `vorp` descending as a tie-breaker

### Progressive threshold

Each position keeps its existing base threshold, but the threshold increases as the current tier number increases.

| Transition | Multiplier |
| --- | ---: |
| Tier 1 -> Tier 2 | 1.00x |
| Tier 2 -> Tier 3 | 1.25x |
| Tier 3 -> Tier 4 | 1.50x |
| Tier 4 -> later tiers | 1.75x |

Examples for RB/WR with a base threshold of 14:

- leave Tier 1 at a gap of 14.0 or more
- leave Tier 2 at a gap of 17.5 or more
- leave Tier 3 at a gap of 21.0 or more
- leave Tier 4 and all later tiers at a gap of 24.5 or more

A new tier begins when either:

- projected-point drop from the previous player >= effective threshold, or
- VORP drop from the previous player >= effective threshold

The effective threshold is based on the current tier before the new tier is created.

## Tier Data Model

The tier engine should expose these fields:

- `tier`: integer tier number within position
- `tier_size`: number of players assigned to the base tier
- `tier_drop`: projected-point drop from the previous player
- `tier_threshold`: threshold that applied when evaluating that player boundary
- `tier_next_drop`: projected-point drop from the final player in the current tier to the first player in the next tier; zero when no next tier exists

The descriptive `tier_status` field will be removed from ranking logic and draft-night display after consumers are migrated.

## Live Tier Availability

Base tiers are assigned once from the full ranking board and remain stable throughout the draft.

Before Pressure and Draft Brain are calculated, EdgeIQ must remove:

- manually drafted players
- keeper-reserved players

The available board then receives:

- `tier_remaining`: number of still-available players in the player's base position/tier

This keeps the tier identity stable while allowing urgency to increase naturally as players disappear.

Example:

- Three players begin in RB Tier 2.
- Two are drafted.
- The final player remains `RB Tier 2` but now has `tier_remaining = 1`.
- EdgeIQ may increase scarcity because the tier is nearly gone, without reclassifying that player as an elite Tier 1 asset.

## Scarcity Model

Scarcity will no longer be inferred from a text label.

The first implementation will calculate a 0-100 `tier_scarcity_score` from three signals:

1. **Tier depth** — earlier tiers are more valuable than later tiers.
2. **Players remaining** — fewer available players in the tier increases urgency.
3. **Drop to next tier** — a larger next-tier drop increases the cost of waiting.

### Tier depth factor

| Tier | Depth factor |
| --- | ---: |
| 1 | 1.00 |
| 2 | 0.85 |
| 3 | 0.70 |
| 4 | 0.55 |
| 5+ | 0.40 |

### Remaining-player pressure

`remaining_pressure = 100 / tier_remaining`, clipped to 0-100.

Examples:

- 1 remaining -> 100
- 2 remaining -> 50
- 3 remaining -> 33.33
- 4 remaining -> 25

### Next-tier drop pressure

`drop_pressure = min(100, 100 * tier_next_drop / effective_next_threshold)`

This measures whether the drop after the current tier is large relative to the threshold required to create the next tier.

### Final tier scarcity

`tier_scarcity_score = tier_depth_factor * (0.60 * remaining_pressure + 0.40 * drop_pressure)`

The score is clipped to 0-100 and rounded to two decimals.

This deliberately prevents a singleton in a late tier from receiving a 100 scarcity score. For example, a Tier 5 singleton can have high local urgency but is capped by the 0.40 depth factor.

## Downstream Scoring Changes

### Rankings

`calculate_draft_score` keeps its current 10% tier-scarcity weight, but consumes the numeric `tier_scarcity_score` produced by the new tier logic instead of mapping from `tier_status`.

No other Draft Score weights change in this redesign.

### Pressure Meter

The Pressure Meter will stop mapping `tier_status` to fixed `tier_pressure` values.

Instead:

`tier_pressure = tier_scarcity_score`

The existing Pressure Meter weight remains 30%.

### Draft Brain

Draft Brain will stop translating `tier_status` into 25/60/85/100 scarcity values.

It will use the same live `tier_scarcity_score` directly for its 15% scarcity component.

Brain reasons will use numeric/tier-aware language, for example:

- `Last player remaining in RB Tier 2`
- `Large drop after WR Tier 1`
- `Two players remain in TE Tier 3`

It will no longer use `Last player remaining in current tier` as evidence that a player is elite.

## War Room Data Flow

The live flow will become:

1. Load or reuse cached base rankings with stable numbered tiers.
2. Remove drafted players and keeper-reserved players.
3. Compute `tier_remaining` on the available board.
4. Recompute live `tier_scarcity_score` using remaining players and next-tier drop.
5. Run Pressure Meter on the available board.
6. Run Draft Brain on the available board.
7. Sort by live `brain_score`.
8. Apply search/position display filters only after scoring.

This order is required so Pressure, run urgency, wait analysis, and tier scarcity operate on players who can actually be drafted.

## UI Changes

The draft-night table will show numeric tier identity only.

Examples:

- `RB Tier 1`
- `WR Tier 3`
- `TE Tier 2`

Implementation may keep the underlying integer `tier` column and format the display label from `position` + `tier`; no duplicate scoring field is required.

The explanation panel should reference the same tier data used by scoring so explanations cannot drift from the model.

## Compatibility and Migration

During migration, tests and diagnostic tools that still reference `tier_status` must be updated to use numeric tier data and `tier_scarcity_score`.

The migration should be completed in one branch before removing `tier_status` from production code. A temporary compatibility field is acceptable only while converting consumers; it must not remain as an independent scoring source.

## Error Handling

- Missing or invalid position thresholds should fall back to the existing default threshold behavior only for unknown positions; QB/RB/WR/TE must always use explicit configured values.
- Empty position groups return without failure.
- Missing `tier_remaining` in non-live contexts should default to `tier_size`.
- `tier_remaining <= 0` must not cause division by zero; unavailable players should normally have been removed before live scoring.
- Draft completion, where `picks_until_user` can be `None`, must be handled safely while touching Draft Brain live-context code.

## Testing Strategy

Implementation will follow RED -> GREEN -> regression checkpoints.

Required tests:

1. Tier numbering restarts at 1 for each position.
2. Tier 1 uses the base threshold.
3. Tier 2 uses 1.25x base threshold.
4. Tier 3 uses 1.50x base threshold.
5. Tier 4+ uses 1.75x base threshold.
6. Either projection drop or VORP drop can create a new tier.
7. A late singleton does not receive Tier 1 scarcity.
8. `tier_remaining` shrinks when drafted/keeper players are removed while base `tier` remains unchanged.
9. Draft Score consumes numeric `tier_scarcity_score`.
10. Pressure Meter consumes the same numeric `tier_scarcity_score`.
11. Draft Brain consumes the same numeric `tier_scarcity_score`.
12. Brain reasons name the player's position tier and remaining count correctly.
13. Available-player filtering occurs before live Pressure/Brain scoring.
14. Existing ranking, keeper, War Room, performance, explanation, and draft-order regression suites remain green.
15. Draft completion does not crash when `picks_until_user` is `None`.

## Acceptance Criteria

The redesign is complete when:

- No production ranking decision depends on descriptive `tier_status` labels.
- Every QB/RB/WR/TE has a stable numbered position tier.
- Progressive thresholds are used exactly as specified.
- Later singleton tiers no longer receive elite-level scarcity solely because tier size is one.
- Live scarcity reflects only available players.
- Rankings, Pressure, Draft Brain, and explanations all consume the same numeric scarcity signal.
- The War Room remains fast enough for draft-night use and existing performance tests remain green.
- Full regression passes before the feature is considered draft-ready.
