# EdgeIQ League-Specific Scoring Design

Date: 2026-08-19
Branch: `league-scoring-audit`
Recovery item: #6 — League Scoring Audit

## Goal

Make EdgeIQ scoring explicitly league-specific for the two 2026 Yahoo keeper leagues:

- `drunk_sundays` — Yahoo league 390151
- `somewhat_related` — Yahoo league 950841

There must be **no silent default league**. Any public projection/ranking path that depends on league economics must require a league key and fail clearly when the key is missing or invalid.

This item wires offensive scoring completely now. Kicker and defense/special-teams rules are stored and tested now so #13 can build their projection/ranking engines later without rediscovering league settings.

## Source of Truth

The scoring values in this design come from the 2026 Yahoo league settings screenshots supplied by Shawn on 2026-08-19.

Yahoo's official Fantasy Football scoring FAQ also confirms that performance bonus thresholds are cumulative. Therefore, for a ladder such as +2 at 100 rushing yards and +4 at 200 rushing yards, a 200-yard rushing game earns both bonuses (+6 total bonus) in addition to ordinary rushing-yard points.

Long-play categories are distinct Yahoo scoring categories and can stack with ordinary yardage/TD scoring and with each other when the same play qualifies.

## Scope

### In scope for #6

1. Split scoring into explicit league profiles.
2. Require `league_key` through public scoring/projection/ranking entry points.
3. Remove hardcoded offensive scoring values from Python.
4. Support all confirmed offensive categories for both leagues.
5. Add historical play-by-play aggregation for 40+ yard offensive categories.
6. Preserve and apply cumulative yardage performance bonuses.
7. Store complete kicker scoring settings for both leagues.
8. Store complete defense/special-teams scoring settings for both leagues.
9. Add tests proving the two leagues produce different results where their rules differ.
10. Keep VORP and downstream rankings using the selected league's scoring-driven projected points.

### Explicitly out of scope for #6

- Building kicker projections/rankings.
- Building defense/special-teams projections/rankings.
- Changing keeper rules.
- Changing draft order.
- Manager tendencies.
- Re-tuning QB economics beyond what league-specific scoring naturally changes.
- Adding arbitrary consensus/manual ranking corrections.

K/DEF projection behavior remains recovery item #13.

---

# 1. Configuration Architecture

## Current problem

`fantasy_draft_model/config/league_settings.json` currently contains one shared `scoring` object, while `add_custom_fantasy_scoring()` historically hardcoded those values. That cannot represent two materially different leagues safely.

## New structure

Keep shared structural settings at the top level for now (season, teams, lineup) and add league-specific scoring profiles under `league_profiles`.

Conceptual shape:

```json
{
  "season": 2026,
  "teams": 12,
  "lineup": { ... },
  "league_profiles": {
    "drunk_sundays": {
      "league_name": "Drunk Sundays",
      "league_id": "390151",
      "scoring": {
        "offense": { ... },
        "kicker": { ... },
        "defense": { ... }
      }
    },
    "somewhat_related": {
      "league_name": "Somewhat Related League",
      "league_id": "950841",
      "scoring": {
        "offense": { ... },
        "kicker": { ... },
        "defense": { ... }
      }
    }
  }
}
```

The current top-level `replacement_levels` object is not authoritative for VORP anymore; #5 derives replacement levels dynamically from league structure and projections. This design does not reintroduce fixed replacement levels.

## Loader contract

Change:

```python
load_league_settings()
```

to require:

```python
load_league_settings(league_key)
```

Behavior:

- `league_key is None` -> raise clear `ValueError`/`TypeError` explaining that a league key is required.
- unknown key -> raise clear `ValueError` listing valid keys.
- valid key -> return a resolved settings dictionary containing shared structural settings plus the selected league profile/scoring.

No fallback to Drunk Sundays, Somewhat Related, or any other profile is allowed.

---

# 2. Confirmed Offensive Scoring

## Shared base offense rules

Both leagues use:

| Category | Value |
|---|---:|
| Passing yards | 1 point / 25 yards (`0.04`) |
| Passing TD | 4 |
| Interception thrown | -1 |
| Rushing yards | 1 point / 10 yards (`0.10`) |
| Rushing TD | 6 |
| Reception | 1 |
| Receiving yards | 1 point / 10 yards (`0.10`) |
| Receiving TD | 6 |
| Return TD | 6 |
| 2-point conversion | 2 |
| Fumble lost | -2 |
| Offensive fumble return TD | 6 |

## Shared cumulative yardage bonuses

Both leagues use the same performance-bonus ladders:

### Passing

- 300+ yards: +2
- 400+ yards: +4 additional
- 500+ yards: +6 additional

Because Yahoo bonuses are cumulative:

- 300–399 -> +2 total bonus
- 400–499 -> +6 total bonus
- 500+ -> +12 total bonus

### Rushing

- 100+ yards: +2
- 200+ yards: +4 additional
- 300+ yards: +6 additional

Cumulative totals:

- 100–199 -> +2
- 200–299 -> +6
- 300+ -> +12

### Receiving

- 100+ yards: +2
- 200+ yards: +4 additional
- 300+ yards: +6 additional

Cumulative totals:

- 100–199 -> +2
- 200–299 -> +6
- 300+ -> +12

## Drunk Sundays explosive-play rules

| Category | Value |
|---|---:|
| 40+ yard completion | +4 |
| 40+ yard passing TD | +4 |
| 40+ yard run | 0 / not configured |
| 40+ yard rushing TD | +4 |
| 40+ yard reception | 0 / not configured |
| 40+ yard receiving TD | +4 |

## Somewhat Related explosive-play rules

| Category | Value |
|---|---:|
| 40+ yard completion | +2 |
| 40+ yard passing TD | +4 |
| 40+ yard run | +2 |
| 40+ yard rushing TD | +4 |
| 40+ yard reception | +2 |
| 40+ yard receiving TD | +4 |

## Stacking behavior

Scoring categories stack independently.

Examples:

- In Drunk Sundays, a 40+ yard passing TD can earn the normal passing TD points, ordinary passing-yard points, +4 for the 40+ completion, and +4 for the 40+ passing TD.
- In Somewhat Related, a 40+ yard rushing TD can earn ordinary rushing yards, the normal rushing TD, +2 for the 40+ run, and +4 for the 40+ rushing TD.
- Yardage milestone bonuses also stack with these play bonuses when a player's game total crosses the configured thresholds.

---

# 3. Kicker Scoring Stored for #13

## Shared made-kick rules

Both leagues:

| Category | Value |
|---|---:|
| FG 0–19 | 3 |
| FG 20–29 | 3 |
| FG 30–39 | 3.5 |
| FG 40–49 | 4 |
| FG 50+ | 5 |
| PAT made | 1 |
| PAT missed | -1 |

## Drunk Sundays missed-field-goal penalties

| Miss distance | Value |
|---|---:|
| 0–19 | -1 |
| 20–29 | -1 |
| 30–39 | -1 |
| 40–49 | -1 |
| 50+ | -1 |

## Somewhat Related missed-field-goal penalties

No missed-field-goal categories were configured/shown between made field goals and PAT settings in the supplied 2026 Yahoo scoring screen. Store these as zero/not configured rather than borrowing Drunk Sundays rules.

No kicker projections are added in #6.

---

# 4. Defense/Special-Teams Scoring Stored for #13

## Shared event scoring

Both leagues:

| Category | Value |
|---|---:|
| Sack | 1 |
| Interception | 2 |
| Fumble recovery | 2 |
| TD | 6 |
| Safety | 2 |
| Block kick | 2 |
| Kickoff/punt return TD | 6 |
| Extra point returned | 2 |

## Drunk Sundays points allowed

| Points allowed | Value |
|---|---:|
| 0 | 14 |
| 1–6 | 12 |
| 7–13 | 10 |
| 14–20 | 7 |
| 21–27 | 4 |
| 28–34 | 2 |
| 35+ | 0 |

## Drunk Sundays defensive yards allowed

| Yards allowed | Value |
|---|---:|
| 0–99 | 10 |
| 100–199 | 8 |
| 200–299 | 6 |
| 300–399 | 2 |
| 400–499 | 0 |
| 500+ | -2 |

This makes Drunk Sundays defense materially more valuable than ordinary Yahoo default DST scoring and must be respected by #13.

## Somewhat Related points allowed

| Points allowed | Value |
|---|---:|
| 0 | 10 |
| 1–6 | 8 |
| 7–13 | 6 |
| 14–20 | 4 |
| 21–27 | 2 |
| 28–34 | 1 |
| 35+ | 0 |

## Somewhat Related defensive yards allowed

No defensive-yards-allowed scoring ladder was configured/shown in the supplied 2026 Yahoo settings. Store it as absent/not configured, not as Yahoo default and not as the Drunk Sundays ladder.

No DST projections are added in #6.

---

# 5. Long-Play Data Pipeline

## Why weekly player stats are insufficient

The existing `nflreadpy.load_player_stats()` weekly table supplies aggregate weekly/season stats but does not provide the event-level counts needed to distinguish:

- 40+ completions
- 40+ passing TDs
- 40+ runs
- 40+ rushing TDs
- 40+ receptions
- 40+ receiving TDs

`nflreadpy.load_pbp(seasons=[2025])` is the correct historical source for those event-level counts.

## New integration

Add a focused integration module, recommended path:

`fantasy_draft_model/integrations/long_play_loader.py`

Responsibilities:

1. Load 2025 regular-season play-by-play with `nflreadpy.load_pbp(seasons=[2025])`.
2. Keep only columns required for long-play classification and player IDs.
3. Derive six event counters at player level:
   - `plays_40_pass_completion`
   - `plays_40_pass_td`
   - `plays_40_rush`
   - `plays_40_rush_td`
   - `plays_40_reception`
   - `plays_40_reception_td`
4. Aggregate by GSIS player ID so it can merge with the existing master player table's `player_id`.
5. Merge these counters into the historical master table before custom scoring is calculated.
6. Fill missing counters with zero.

The loader must use event/player identifiers from nflverse rather than matching by display name.

## 40-yard classification

A play qualifies as 40+ when the applicable credited gain is at least 40 yards.

Passing completion counts credit the passer.
Receiving counts credit the receiver.
Rushing counts credit the rusher.
TD variants require both the 40+ condition and the applicable touchdown condition.

A single play may legitimately increment both a generic 40+ event count and its TD counterpart because Yahoo scores those categories separately.

---

# 6. Historical Performance Bonus Pipeline

The current code only creates three simple game flags (`game_300_pass`, `game_100_rush`, `game_100_receive`). That is insufficient for the real league ladders.

Replace/extend these flags so each player's weekly row can generate cumulative threshold counts for:

Passing:
- `games_300_pass`
- `games_400_pass`
- `games_500_pass`

Rushing:
- `games_100_rush`
- `games_200_rush`
- `games_300_rush`

Receiving:
- `games_100_receive`
- `games_200_receive`
- `games_300_receive`

When season totals are aggregated, each count represents how many games crossed that exact threshold. Because thresholds are cumulative, a 500-yard passing game increments all three passing counters.

The custom scoring function multiplies each counter by its configured bonus value and sums them.

---

# 7. Scoring Function Contract

`add_custom_fantasy_scoring()` must stop loading a silent default.

Recommended contract:

```python
def add_custom_fantasy_scoring(df, league_settings):
    ...
```

The caller must supply already-resolved league settings.

This keeps the scoring function deterministic and easy to unit test. League selection belongs at public pipeline boundaries, not deep inside arithmetic helpers.

The arithmetic should include all supported offensive columns when present and use zero-safe helpers for historical columns that are legitimately absent for rookies.

---

# 8. League Key Through the Public Pipeline

Require explicit `league_key` at all public paths whose output depends on scoring/economics.

At minimum:

```python
create_master_player_table(league_key)
build_player_profiles(league_key)
build_2026_projections(league_key)
build_draft_rankings(league_key)
```

The selected settings flow downward:

`build_draft_rankings(league_key)`
→ `build_2026_projections(league_key)`
→ `build_player_profiles(league_key)`
→ `create_master_player_table(league_key)`
→ `load_league_settings(league_key)`
→ `add_custom_fantasy_scoring(df, league_settings)`

The same resolved settings must be passed into `calculate_vorp(df, league_settings)` so #5's dynamic replacement logic continues using the selected league's structure.

Any CLI/UI/mock-draft caller that currently calls these functions without a league key must be updated to pass its league explicitly.

---

# 9. Test Strategy

TDD remains mandatory for behavior changes.

## Config/selection tests

- valid `drunk_sundays` loads correct profile
- valid `somewhat_related` loads correct profile
- missing league key fails
- invalid league key fails clearly
- K/DEF values from screenshots are preserved exactly

The current test `test_default_scoring_path_uses_configured_league_values` conflicts with the approved no-default rule and must be replaced with a test asserting that no default is allowed.

The current test asserting the old +3/+3/+3 bonus values is obsolete because the supplied 2026 Yahoo settings show +2/+4/+6 cumulative ladders.

## Arithmetic tests

Use synthetic rows to isolate each category:

- ordinary yard/reception/TD/turnover scoring
- cumulative 300/400/500 passing bonuses
- cumulative 100/200/300 rushing bonuses
- cumulative 100/200/300 receiving bonuses
- Drunk Sundays 40+ completion/TD stacking
- Somewhat Related 40+ run/reception/TD stacking
- same synthetic player scores differently under the two profiles

## Long-play aggregation tests

Use a tiny synthetic PBP frame so tests do not require the network:

- 39-yard play does not count
- 40-yard play does count
- 40+ pass TD increments completion and pass-TD counters
- 40+ rush TD increments run and rush-TD counters
- 40+ receiving TD increments reception and receiving-TD counters
- IDs are attributed to the correct passer/rusher/receiver

## Pipeline tests

- `build_2026_projections("drunk_sundays")` executes
- `build_2026_projections("somewhat_related")` executes
- no-argument call fails intentionally
- selected league flows into scoring and VORP
- existing rookie/injury/QB/VORP tests remain green after being updated to pass an explicit league key where required

## Final verification

1. focused #6 tests
2. all existing regression tests
3. full `pytest -q`
4. live projection diagnostic for both leagues
5. compare representative players whose explosive-play profile should produce a league scoring difference
6. verify no public scoring-sensitive path silently defaults to a league

---

# 10. Error Handling

Fail fast on configuration/programmer errors:

- missing league key
- invalid league key
- missing selected scoring profile
- malformed required scoring block

Do not silently substitute another league's scoring.

For optional historical event counters, missing player rows after a valid merge are zero, not errors.

Network/data-loader failures from nflreadpy should surface with enough context to identify the failing source rather than silently dropping all explosive-play bonuses.

---

# 11. Performance and Data Loading

Play-by-play is much larger than weekly player stats. The long-play loader should:

- load only the required season (2025 for the current baseline)
- filter to regular season
- select only required columns before converting/aggregating where practical
- aggregate once to player-level counters before merging

No repeated PBP load should occur per player or per league. The historical long-play counts are league-independent; only the points assigned to those counts differ by league.

---

# 12. Compatibility With Other Recovery Items

- #5 VORP remains dynamic; it receives selected league settings explicitly.
- #7 keepers are unchanged.
- #8 league profile/order audit can later move lineup/team-count fields into per-league profiles if the two leagues differ structurally. #6 does not assume future equality beyond the current shared config.
- #9 depth charts unchanged.
- #10/#11 injury logic unchanged.
- #12 CPU QB behavior can consume the selected league rankings later.
- #13 will consume the kicker/DST scoring blocks stored here.
- #18 printable fallback must call rankings with an explicit league key and can generate a separate board for each league.

---

# Acceptance Criteria

#6 is complete only when all of the following are true:

1. EdgeIQ has separate `drunk_sundays` and `somewhat_related` scoring profiles.
2. No scoring-sensitive public pipeline silently chooses a league.
3. All confirmed offensive scoring categories from the Yahoo screenshots are represented.
4. Cumulative performance bonuses are modeled correctly.
5. Historical 40+ play counts are derived from play-by-play and included in scoring.
6. The same player/data can score differently between leagues according to their configured rules.
7. All supplied kicker and DST rules are stored accurately for #13.
8. Drunk Sundays defensive yards-allowed scoring is preserved; Somewhat Related does not inherit it.
9. Focused tests pass.
10. Full test suite passes.
11. Live projections can be built explicitly for both leagues.
12. No unrelated ranking/manual tuning is introduced.
