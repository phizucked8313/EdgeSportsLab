# EdgeIQ Current Injury Normalization Design

## Goal

Replace the broken 2026 `nflreadpy.load_injuries()` path for current injuries with a normalized Sleeper-based current-injury pipeline that feeds EdgeIQ's existing team injury impact, ripple, projection, and ranking logic without coupling those downstream engines directly to Sleeper-specific field names.

## Scope

This design covers the 2026 current-injury path only. Historical injury risk remains separate in `injury_risk.py` and can continue to use historical data through 2025 when that pipeline is repaired. The first enrichment pass targets fantasy-relevant players: Top 300 draftable players plus keepers and meaningful handcuffs/backups. Fringe players outside that set may remain unresearched unless their injury materially affects a fantasy-relevant teammate.

## Existing State

- `fantasy_draft_model/integrations/sleeper_api.py` successfully downloads current NFL player data and returns fantasy-relevant injured QB/RB/WR/TE players.
- `fantasy_draft_model/integrations/injury_history_loader.py` still attempts `nfl.load_injuries(seasons=[2026])`, which fails because the installed loader supports only seasons through 2025.
- `fantasy_draft_model/models/team_injury_impact_engine.py` expects normalized fields such as `report_status` and `practice_status` and converts player injuries into player/team impact scores.
- `fantasy_draft_model/engines/injury_ripple_engine.py` converts team injury-unit impact into position-specific fantasy ripple multipliers.
- `fantasy_draft_model/engines/projection_engine.py` already wires current injuries into the ripple path, but imports the broken `load_current_injuries()` from `injury_history_loader.py`.

## Architecture

The current-injury data flow will be:

`Sleeper API -> sleeper_api.py -> current_injury_normalizer.py -> team_injury_impact_engine.py -> injury_ripple_engine.py -> projection_engine.py`

The normalizer creates a stable EdgeIQ schema. Downstream engines consume EdgeIQ field names rather than vendor-specific names. This keeps future ESPN, team-report, or X/reporting enrichment additive instead of forcing rewrites.

## Normalized Injury Schema

Each normalized record will contain, where available:

- `sleeper_id`
- `espn_id`
- `yahoo_id`
- `player_name`
- `team`
- `position`
- `status`
- `report_status`
- `practice_status`
- `source_injury_body_part`
- `edgeiq_injury_body_part`
- `injury_start_date`
- `needs_research`
- `injury_data_quality`
- `injury_source`
- `injury_source_timestamp`

`report_status` maps Sleeper's `injury_status` into the values expected by EdgeIQ. `practice_status` maps Sleeper's `practice_participation`. `source_injury_body_part` preserves Sleeper's original value. `edgeiq_injury_body_part` initially mirrors the source unless later enrichment identifies a more specific verified diagnosis.

## Undisclosed Injury Handling

An `Undisclosed`, blank, `NaN`, or otherwise non-specific body-part value must not be treated as healthy or low-risk.

For a fantasy-relevant player with a non-specific injury:

- `needs_research = True`
- `injury_data_quality = "F"`
- `source_injury_body_part` retains the original Sleeper value
- `edgeiq_injury_body_part` remains non-specific until a reliable source confirms the diagnosis

The normalization layer must never guess a diagnosis. Enrichment is a separate step using reliable reporting.

## Injury Data Quality

Use the following source-quality grades:

- `A`: confirmed diagnosis from official team/NFL reporting or equivalent primary source
- `B`: diagnosis from a highly reliable national or team reporter
- `C`: diagnosis supported by multiple reputable secondary reports
- `D`: structured Sleeper designation/body-part data only
- `F`: unresolved, undisclosed, conflicting, or insufficiently specific information

The initial Sleeper-only normalization assigns `D` to specific injury/body-part records and `F` to unresolved/non-specific records.

## Fantasy-Relevant Research Queue

Automatic or manual enrichment should focus on:

1. Players in the current Top 300 draft pool.
2. Confirmed keepers in either league.
3. Meaningful handcuffs/backups whose role changes because of an injured starter.
4. Any injured player whose absence materially changes a Top 300 teammate's opportunity.

This keeps the current deadline focused while preserving a path to broader coverage later.

## Integration with Team Injury Impact

`team_injury_impact_engine.py` remains the primary consumer for team-level injury impact. It should receive the normalized dataframe with `report_status` and `practice_status` already present.

The existing status multipliers remain Version 1 model weights and are not recalibrated as part of this change. This implementation only fixes current data sourcing and schema compatibility.

## Integration with Projection Engine

`projection_engine.py` must stop importing current injuries from `injury_history_loader.py` and instead use the normalized Sleeper current-injury loader.

The projection path should preserve the existing pre-injury projection and ripple multiplier behavior so EdgeIQ can show how much the current injury environment changed each player's projection.

Historical injury-risk adjustments remain separate from current injury status.

## Error Handling

- Sleeper HTTP/network failures should raise a clear exception from the integration layer rather than silently returning a healthy league.
- Empty injury data should be handled as an explicit empty dataframe and should not produce false injury penalties.
- Missing optional fields should normalize to empty/None values without breaking downstream code.
- Unknown status values should be preserved for inspection and fall back to the existing conservative team-impact behavior rather than being silently mapped to healthy.

## Testing

Tests must cover at minimum:

- A known `IR` player maps to `report_status="IR"` and is not marked healthy.
- A `Questionable` player maps correctly.
- An `Undisclosed` player gets `needs_research=True` and `injury_data_quality="F"`.
- A specific injury body part gets `injury_data_quality="D"` before enrichment.
- A healthy player is not returned by the current-injury function.
- The projection engine no longer calls the 2026 `nflreadpy` injury loader.
- A normalized current injury can flow through `team_injury_impact_engine.py` and `injury_ripple_engine.py` without schema errors.

## Non-Goals

This change does not:

- rebuild historical durability/injury-risk scoring;
- recalibrate team injury impact weights;
- implement full X/Twitter ingestion;
- implement a paid injury API;
- research every one of the 141 Sleeper injury records;
- change rookie, QB/VORP, keeper, or league-scoring logic.

Those remain separate recovery items after the 2026 current-injury pipeline works end to end.
