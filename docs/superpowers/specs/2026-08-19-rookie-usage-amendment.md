# EdgeIQ Rookie Projection Usage Amendment

## Purpose

Extend the approved 2026 rookie projection model with role-aware usage, a modest early-season WR ramp, and touch-efficiency fields without changing rookie identification, depth-chart sourcing, QB/VORP economics, keeper rules, or league scoring.

## Approved Behavior

### RB role and usage

Rookie RBs in a confirmed starting/lead role should receive more projected opportunity than otherwise-identical committee, backup, or depth RBs. Because the 2026 depth-chart source is not yet fixed, this recovery item must not guess a role. It should consume an optional `rookie_role` field when present and default to `UNKNOWN` when absent. Recovery Item #9 can later populate that field from fresh 2026 depth charts.

Initial RB role opportunity adjustments:

- `STARTER`: +15 opportunity points
- `LEAD`: +15
- `COMMITTEE`: +5
- `ROTATION`: 0
- `BACKUP`: -10
- `DEPTH`: -20
- `DEEP_DEPTH`: -25
- `UNKNOWN`: 0

The opportunity score remains clipped to the model's existing bounds.

### WR early-season ramp

Rookie WRs receive a modest six-week acclimation factor for season-long projection. The model should expose:

- `rookie_ramp_weeks = 6` for rookie WRs;
- `rookie_ramp_factor = 0.96` for rookie WRs;
- `rookie_ramp_factor = 1.00` for all other players in this recovery item.

This is intentionally modest: strong talent, draft capital, and opportunity can still produce a high rookie WR projection.

### Touches

For RB/WR/TE efficiency reporting:

`touches = carries + receptions`

This intentionally treats receptions as touches and does not treat targets as touches. Example: 14 carries + 5 receptions = 19 touches.

### Fantasy points per touch

For players with at least one touch:

`fantasy_points_per_touch = custom_fantasy_points / touches`

Players with zero touches receive `0.0` rather than an error.

### Projected rookie usage

After `rookie_baseline_projection` is available, estimate rookie usage from EdgeIQ's own veteran 2025 efficiency distribution rather than guessed hard-coded touch counts.

For each rookie RB/WR/TE:

1. Calculate the veteran position median `fantasy_points_per_touch` from non-rookies with meaningful touches.
2. `rookie_projected_touches = rookie_baseline_projection / veteran_position_median_fp_per_touch`.
3. `rookie_projected_touches_per_game = rookie_projected_touches / 17`.
4. For RBs, use the veteran RB median reception share of touches to split projected touches into `rookie_projected_receptions` and `rookie_projected_carries`.
5. For WR/TE, projected touches are receptions for this model and projected carries default to zero.

If a usable veteran position median does not exist, projected usage fields should remain `0.0` and a data-quality field should mark the estimate unresolved rather than inventing a constant.

## Data-quality guardrails

- Do not infer STARTER/LEAD from draft capital alone.
- Do not use the stale 2025 depth-chart loader to assign 2026 roles.
- Do not use points-per-touch alone to rank players; volume/opportunity remains a separate input.
- Do not treat WR/TE targets as touches.
- Do not fabricate touch estimates when veteran peer efficiency is unavailable.

## Testing

Tests must verify:

1. 14 carries + 5 receptions = 19 touches.
2. 19 fantasy points on 19 touches = 1.0 fantasy points per touch.
3. Otherwise-identical STARTER RB > BACKUP RB in rookie opportunity score.
4. Rookie WR ramp fields equal 6 weeks and 0.96; rookie RB remains 1.00.
5. Projected rookie RB touches equal projected carries + projected receptions.
6. Projected touch estimates use veteran position efficiency and do not require stale depth charts.
