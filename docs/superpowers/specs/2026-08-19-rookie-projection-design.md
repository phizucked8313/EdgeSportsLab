# EdgeIQ 2026 Rookie Projection Model Design

## Goal

Replace the Version 1 rookie baseline projection (`rookie_talent_score × positional multiplier`) with a multi-factor 2026 rookie fantasy projection model that is materially more realistic while staying focused enough for the current draft deadline.

## Scope

This change is Recovery Item #2 only. It improves rookie projections for players already identified as rookies in the master player pool. It does not redefine `is_rookie`; that is Recovery Item #3. It does not fix 2026 depth-chart freshness; that is Recovery Item #9. It does not recalibrate QB/VORP economics; those are Recovery Items #4 and #5.

## Current State

`fantasy_draft_model/engines/talent_engine.py` currently:

1. assigns `rookie_talent_score` from broad draft-number buckets;
2. converts that score directly to a baseline fantasy projection using one positional multiplier;
3. leaves rookie projections largely disconnected from current roster opportunity, realistic positional rookie scoring curves, and team environment.

The master player table already carries useful fields including `draft_number`, `years_exp`, `entry_year`, `rookie_year`, `team`, `position`, `status`, and `is_rookie`.

## Recommended Architecture

Keep rookie modeling inside `talent_engine.py` for this deadline, but split the model into clear, testable components:

1. `calculate_rookie_talent_score(df)` — draft-capital-driven NFL investment signal.
2. `add_rookie_opportunity_score(df)` — current roster opportunity proxy from available 2026 roster context without relying on the stale 2025 depth-chart dataset.
3. `add_rookie_position_curve(df)` — position-specific expected first-year production curve.
4. `add_rookie_team_environment(df)` — small, bounded landing-spot modifier.
5. `add_rookie_projection_components(df)` — combine the model components into a stable 0–100 rookie projection score.
6. `add_rookie_baseline_projection(df)` — convert the composite score into realistic position-specific fantasy-point ranges.

The existing public function names used by `projection_engine.py` should remain compatible where practical so downstream code changes stay minimal.

## Model Components

### 1. Draft Capital / Talent

Draft capital remains the strongest input available now because it incorporates the NFL's information and investment decision. The current broad buckets should be refined into a smoother score so pick 5 and pick 32 are not identical.

Use a monotonic scale from elite first-round capital toward late-round/undrafted capital. Missing or undrafted data receives a low but non-zero score rather than zero.

Target range: roughly 30–100.

### 2. Roster Opportunity

Use only current 2026 roster data available in the master player table. Do not depend on `depth_chart_loader.py` in this recovery item because it is still pinned to 2025.

Opportunity should consider:

- roster status when available;
- whether the player is on a current NFL team;
- draft capital as a secondary proxy for expected early role;
- position-specific immediacy.

The initial implementation should be conservative. It must not pretend to know exact RB1/WR1 depth-chart placement when the current data source cannot support that claim.

Target range: roughly 35–90.

### 3. Positional Rookie Curve

Rookie positions historically enter fantasy relevance at different rates. The model should encode that structurally:

- RB: highest immediate-year conversion opportunity;
- WR: strong immediate upside but more variable than RB;
- TE: slower first-year production curve;
- QB: separate treatment because fantasy value depends heavily on earning/holding the starting job.

This component should affect both baseline range and model weighting rather than simply multiplying every rookie score by a constant.

### 4. Team Environment

Use a deliberately small modifier. Landing spot matters, but it should not overpower draft capital/talent.

For this deadline, team environment should be neutral by default and bounded tightly. If reliable team-context fields are not already present, use `1.00` rather than guessing.

The architecture must leave a clean field (`rookie_team_environment_multiplier`) for future offense/QB/coaching integration.

### 5. Future Prospect Profile Hook

Option B must be Option C-ready. Add a neutral component now:

`rookie_prospect_profile_score = 50.0`

Later, Option C can replace this neutral score with college production, age, athletic testing, dominator/market-share, efficiency, and related prospect metrics without rewriting the rest of the projection model.

## Composite Rookie Projection Score

Initial recommended weighting:

- 45% draft-capital/talent score
- 30% roster opportunity score
- 20% positional rookie curve score
- 5% prospect profile score (neutral in Option B)

Team environment is applied as a small multiplier after the weighted score rather than a large additive weight.

This weighting keeps NFL investment as the strongest signal while preventing the current model from treating every rookie with the same draft-capital bucket as equivalent.

## Position-Specific Fantasy Point Ranges

Convert the composite rookie score into a bounded season fantasy-point baseline by position. The ranges should be realistic enough to differentiate elite and fringe rookies without allowing one formula to inflate all positions.

Initial target ranges for a 17-game PPR-style environment:

- RB: approximately 70–290 points
- WR: approximately 60–260 points
- TE: approximately 35–190 points
- QB: approximately 40–330 points

These are model bounds, not guarantees. A rookie's final projection should still pass through the existing opportunity, injury-risk, and later ranking/VORP logic.

## Missing Data Behavior

- Missing `draft_number`: use a low draft-capital score, not zero.
- Missing roster `status`: use neutral opportunity treatment.
- Missing team environment: multiplier = `1.00`.
- Non-rookies: retain neutral/default component fields and must not have their veteran baseline replaced by the rookie baseline.
- Unsupported positions: rookie baseline = `0.0`.

## Guardrails

- No player-specific manual boosts.
- No adjustment merely because an outside ranking is higher/lower.
- No dependence on stale 2025 depth-chart rows.
- No changes to rookie identification logic in this task.
- No changes to QB/VORP ranking economics in this task.
- No attempt to implement the full Option C college/prospect dataset now.

## Testing

Unit tests should verify at minimum:

1. earlier draft capital produces a higher talent score than later draft capital;
2. a high-capital rookie produces a higher composite score than an otherwise identical late-round rookie;
3. RB/WR/TE/QB use distinct positional curves and projection ranges;
4. team environment defaults to neutral when no context is available;
5. missing draft capital does not crash the model;
6. veterans do not receive rookie baseline overrides;
7. rookie baseline projections remain within the defined positional bounds;
8. the existing `projection_engine.py` can call the upgraded rookie functions without interface breakage.

## Validation

After unit tests pass, run the live 2026 projection pipeline and print the top rookie QB/RB/WR/TE outputs with:

- player name
- team
- position
- draft number
- rookie talent score
- rookie opportunity score
- rookie position curve score
- composite rookie projection score
- rookie baseline projection

The result should show sensible separation among rookies based on the available data rather than the current flat `talent × multiplier` behavior.

## Non-Goals

This recovery item does not:

- verify the full 2026 rookie class;
- filter the 227 rookie candidates;
- fetch current 2026 depth charts;
- add college production/athletic datasets;
- recalibrate league scoring;
- fix QB/VORP values;
- change keepers or draft order.
