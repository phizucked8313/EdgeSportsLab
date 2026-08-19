# League-Specific Scoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make EdgeIQ require an explicit league and calculate 2026 fantasy projections from the exact 2026 Yahoo scoring profiles for Drunk Sundays and Somewhat Related, including cumulative yardage bonuses and 40+ yard offensive categories, while storing K/DEF rules for recovery item #13.

**Architecture:** `league_settings.json` becomes the single source of truth for two `league_profiles`. `load_league_settings(league_key)` resolves shared structural settings plus one profile and never silently defaults. Historical weekly stats provide ordinary production and cumulative game-threshold counters; a focused play-by-play loader provides 40+ event counters. The explicit `league_key` flows from rankings -> projections -> player profiles -> master table, and the same resolved settings are supplied to VORP.

**Tech Stack:** Python 3.14, pandas, nflreadpy/nflverse, pytest, JSON configuration.

**Spec:** `docs/superpowers/specs/2026-08-19-league-specific-scoring-design.md`

## Global Constraints

- Supported league keys are exactly `drunk_sundays` and `somewhat_related`.
- No public scoring/projection/ranking path may silently choose a league.
- Drunk Sundays Yahoo league ID is `390151`; Somewhat Related Yahoo league ID is `950841`.
- Yardage performance bonuses are cumulative.
- Offensive long-play scoring is wired in #6; kicker and defense scoring rules are stored/tested in #6 but K/DEF projection/ranking logic remains #13.
- Do not change keeper logic, draft order, manager tendencies, or the #4 QB-economics model except where league-specific scoring naturally changes projected points.
- Do not reintroduce fixed VORP replacement levels; #5 dynamic lineup/FLEX calibration remains authoritative.
- Historical source season for projection baselines remains 2025.
- Use player IDs, not display-name joins, for long-play attribution.
- Every production behavior change follows RED -> GREEN -> regression verification.

---

### Task 1: Replace Shared Scoring With Explicit League Profiles

**Files:**
- Modify: `fantasy_draft_model/config/league_settings.json`
- Modify: `fantasy_draft_model/config.py`
- Modify: `tests/test_league_scoring.py`

**Interfaces:**
- Produces: `load_league_settings(league_key: str) -> dict`
- Valid keys: `drunk_sundays`, `somewhat_related`
- Returned dictionary keeps shared `season`, `teams`, and `lineup`, and exposes the selected profile as `league_name`, `league_id`, `keeper_league`, and `scoring`.

- [ ] **Step 1: Replace the obsolete default-path tests with failing league-selection tests**

Add/replace tests in `tests/test_league_scoring.py`:

```python
import pytest

from fantasy_draft_model.config import load_league_settings


def test_league_settings_require_explicit_key():
    with pytest.raises(TypeError):
        load_league_settings()


def test_unknown_league_key_fails_clearly():
    with pytest.raises(ValueError, match="drunk_sundays.*somewhat_related"):
        load_league_settings("not_a_league")


def test_drunk_sundays_profile_matches_yahoo_settings():
    settings = load_league_settings("drunk_sundays")
    offense = settings["scoring"]["offense"]
    defense = settings["scoring"]["defense"]

    assert settings["league_id"] == "390151"
    assert offense["passing_yard"] == 0.04
    assert offense["reception"] == 1.0
    assert offense["bonus_300_passing"] == 2
    assert offense["bonus_400_passing"] == 4
    assert offense["bonus_500_passing"] == 6
    assert offense["play_40_completion"] == 4
    assert offense["play_40_run"] == 0
    assert offense["play_40_reception"] == 0
    assert offense["play_40_passing_td"] == 4
    assert offense["play_40_rushing_td"] == 4
    assert offense["play_40_receiving_td"] == 4
    assert defense["points_allowed"]["0"] == 14
    assert defense["yards_allowed"]["0_99"] == 10
    assert defense["yards_allowed"]["500_plus"] == -2


def test_somewhat_related_profile_matches_yahoo_settings():
    settings = load_league_settings("somewhat_related")
    offense = settings["scoring"]["offense"]
    defense = settings["scoring"]["defense"]

    assert settings["league_id"] == "950841"
    assert offense["play_40_completion"] == 2
    assert offense["play_40_run"] == 2
    assert offense["play_40_reception"] == 2
    assert offense["play_40_passing_td"] == 4
    assert offense["play_40_rushing_td"] == 4
    assert offense["play_40_receiving_td"] == 4
    assert defense["points_allowed"]["0"] == 10
    assert defense["points_allowed"]["28_34"] == 1
    assert defense["yards_allowed"] == {}
```

- [ ] **Step 2: Run the selection tests and verify RED**

Run:

```bash
python -m pytest tests/test_league_scoring.py -v
```

Expected: failures because `load_league_settings()` still has the old no-argument shared-settings contract and `league_profiles` do not exist.

- [ ] **Step 3: Convert `league_settings.json` to explicit profiles**

Keep shared `season`, `teams`, and `lineup`. Replace the old top-level `scoring` and `yahoo_leagues` blocks with `league_profiles` containing the exact screenshot values.

Required offense keys for both profiles:

```json
{
  "passing_yard": 0.04,
  "passing_td": 4,
  "passing_interception": -1,
  "rushing_yard": 0.1,
  "rushing_td": 6,
  "reception": 1.0,
  "receiving_yard": 0.1,
  "receiving_td": 6,
  "return_td": 6,
  "two_point_conversion": 2,
  "fumble_lost": -2,
  "offensive_fumble_return_td": 6,
  "bonus_300_passing": 2,
  "bonus_400_passing": 4,
  "bonus_500_passing": 6,
  "bonus_100_rushing": 2,
  "bonus_200_rushing": 4,
  "bonus_300_rushing": 6,
  "bonus_100_receiving": 2,
  "bonus_200_receiving": 4,
  "bonus_300_receiving": 6
}
```

Add Drunk Sundays explosive values `4,4,0,4,0,4` for completion/pass-TD/run/rush-TD/reception/rec-TD and Somewhat Related values `2,4,2,4,2,4`.

Store K rules exactly as the screenshots show: made FGs `3,3,3.5,4,5`, PAT made `1`, PAT missed `-1`; Drunk Sundays missed FGs are `-1` in every distance bucket, Somewhat Related missed-FG buckets are zero/not configured.

Store DST event scoring for both: sack `1`, interception `2`, fumble recovery `2`, TD `6`, safety `2`, block kick `2`, kickoff/punt return TD `6`, extra point returned `2`. Store the exact points-allowed ladders and only Drunk Sundays' yards-allowed ladder from the spec.

- [ ] **Step 4: Implement the resolver in `config.py`**

Use this contract:

```python
def load_league_settings(league_key: str):
    with open(LEAGUE_SETTINGS_FILE, "r", encoding="utf-8") as file:
        root = json.load(file)

    profiles = root["league_profiles"]
    if league_key not in profiles:
        valid = ", ".join(sorted(profiles))
        raise ValueError(
            f"Unknown league_key {league_key!r}. Valid league keys: {valid}"
        )

    profile = profiles[league_key]
    return {
        "season": root["season"],
        "teams": root["teams"],
        "lineup": root["lineup"],
        "league_key": league_key,
        "league_name": profile["league_name"],
        "league_id": profile["league_id"],
        "keeper_league": profile["keeper_league"],
        "scoring": profile["scoring"],
    }
```

Do not provide a default value for `league_key`.

- [ ] **Step 5: Run Task 1 tests and verify GREEN**

```bash
python -m pytest tests/test_league_scoring.py -v
```

Expected: profile/selection tests pass; arithmetic tests that still use the old `scoring` shape may fail until Task 4 and should be updated in Task 4 rather than weakening the resolver contract.

- [ ] **Step 6: Commit Task 1**

```bash
git add fantasy_draft_model/config.py fantasy_draft_model/config/league_settings.json tests/test_league_scoring.py
git commit -m "feat: add explicit league scoring profiles"
```

---

### Task 2: Build Cumulative Weekly Performance-Bonus Counters

**Files:**
- Modify: `fantasy_draft_model/models/projections.py`
- Modify: `tests/test_league_scoring.py`

**Interfaces:**
- Consumes weekly columns: `passing_yards`, `rushing_yards`, `receiving_yards`
- Produces season counters: `games_300_pass`, `games_400_pass`, `games_500_pass`, `games_100_rush`, `games_200_rush`, `games_300_rush`, `games_100_receive`, `games_200_receive`, `games_300_receive`

- [ ] **Step 1: Add failing cumulative-flag test**

```python
from fantasy_draft_model.models.projections import add_bonus_flags


def test_bonus_flags_are_cumulative():
    weekly = pd.DataFrame(
        {
            "passing_yards": [500],
            "rushing_yards": [300],
            "receiving_yards": [300],
        }
    )

    result = add_bonus_flags(weekly)

    assert result.loc[0, [
        "game_300_pass", "game_400_pass", "game_500_pass",
        "game_100_rush", "game_200_rush", "game_300_rush",
        "game_100_receive", "game_200_receive", "game_300_receive",
    ]].tolist() == [1] * 9
```

- [ ] **Step 2: Run and verify RED**

```bash
python -m pytest tests/test_league_scoring.py::test_bonus_flags_are_cumulative -v
```

Expected: FAIL because the 400/500, 200/300, and 200/300 counters do not exist.

- [ ] **Step 3: Extend `add_bonus_flags()` with all nine threshold flags**

Implement each flag as `(yards.fillna(0) >= threshold).astype(int)` so a 500-yard passing game increments all three passing thresholds and equivalent rushing/receiving ladders are cumulative.

- [ ] **Step 4: Add the new counters to `build_master_player_table().agg(...)`**

Aggregate every new `game_*` flag with `sum` exactly as the existing three counters are aggregated.

- [ ] **Step 5: Run and verify GREEN**

```bash
python -m pytest tests/test_league_scoring.py::test_bonus_flags_are_cumulative -v
```

Expected: PASS.

- [ ] **Step 6: Commit Task 2**

```bash
git add fantasy_draft_model/models/projections.py tests/test_league_scoring.py
git commit -m "feat: add cumulative yardage bonus counters"
```

---

### Task 3: Add 2025 Long-Play Aggregation From Play-by-Play

**Files:**
- Create: `fantasy_draft_model/integrations/long_play_loader.py`
- Create: `tests/test_long_play_loader.py`
- Modify: `fantasy_draft_model/models/projections.py`

**Interfaces:**
- Produces: `aggregate_long_play_counts(pbp_df: pd.DataFrame) -> pd.DataFrame`
- Produces: `load_2025_long_play_counts() -> pd.DataFrame`
- Output key: `player_id`
- Output counters: `plays_40_pass_completion`, `plays_40_pass_td`, `plays_40_rush`, `plays_40_rush_td`, `plays_40_reception`, `plays_40_reception_td`

- [ ] **Step 1: Add a network-free failing aggregation test**

Create `tests/test_long_play_loader.py` with synthetic PBP rows using nflverse field names `yards_gained`, `complete_pass`, `pass_touchdown`, `rush_touchdown`, `passer_player_id`, `rusher_player_id`, and `receiver_player_id`:

```python
import pandas as pd

from fantasy_draft_model.integrations.long_play_loader import aggregate_long_play_counts


def test_40_plus_play_counts_are_attributed_by_player_id():
    pbp = pd.DataFrame(
        {
            "yards_gained": [39, 40, 45, 50],
            "complete_pass": [1, 1, 0, 0],
            "pass_touchdown": [0, 1, 0, 0],
            "rush_touchdown": [0, 0, 1, 0],
            "passer_player_id": ["QB1", "QB1", None, None],
            "receiver_player_id": ["WR1", "WR1", None, None],
            "rusher_player_id": [None, None, "RB1", "RB2"],
        }
    )

    result = aggregate_long_play_counts(pbp).set_index("player_id")

    assert result.loc["QB1", "plays_40_pass_completion"] == 1
    assert result.loc["QB1", "plays_40_pass_td"] == 1
    assert result.loc["WR1", "plays_40_reception"] == 1
    assert result.loc["WR1", "plays_40_reception_td"] == 1
    assert result.loc["RB1", "plays_40_rush"] == 1
    assert result.loc["RB1", "plays_40_rush_td"] == 1
    assert result.loc["RB2", "plays_40_rush"] == 1
    assert result.loc["RB2", "plays_40_rush_td"] == 0
```

The 39-yard completion must not count.

- [ ] **Step 2: Run and verify RED**

```bash
python -m pytest tests/test_long_play_loader.py -v
```

Expected: import failure because `long_play_loader.py` does not exist.

- [ ] **Step 3: Implement `aggregate_long_play_counts()`**

Build three small per-role frames from rows where `yards_gained >= 40`:

- passing: require `complete_pass == 1`, group by `passer_player_id`, count completions and `pass_touchdown == 1`
- receiving: require `complete_pass == 1`, group by `receiver_player_id`, count receptions and `pass_touchdown == 1`
- rushing: require non-null `rusher_player_id`, group by `rusher_player_id`, count runs and `rush_touchdown == 1`

Rename the ID column in each frame to `player_id`, outer-merge the three role frames, and fill all six counters with integer zero.

- [ ] **Step 4: Implement `load_2025_long_play_counts()`**

Use:

```python
import nflreadpy as nfl


def load_2025_long_play_counts():
    pbp = nfl.load_pbp(seasons=[2025]).to_pandas()
    if "season_type" in pbp.columns:
        pbp = pbp[pbp["season_type"] == "REG"].copy()
    return aggregate_long_play_counts(pbp)
```

The nflreadpy primary docs confirm `load_pbp(seasons=[...])` returns play-by-play data and supports the 2025 season.

- [ ] **Step 5: Merge long-play counters into the historical master table**

In `build_master_player_table()`, after weekly aggregation, merge `load_2025_long_play_counts()` on `player_id` with `how="left"`, then fill the six `plays_40_*` columns with zero and cast them to integers.

- [ ] **Step 6: Run and verify GREEN**

```bash
python -m pytest tests/test_long_play_loader.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit Task 3**

```bash
git add fantasy_draft_model/integrations/long_play_loader.py fantasy_draft_model/models/projections.py tests/test_long_play_loader.py
git commit -m "feat: aggregate historical 40-yard plays"
```

---

### Task 4: Make Offensive Arithmetic Fully League-Specific

**Files:**
- Modify: `fantasy_draft_model/models/projections.py`
- Modify: `tests/test_league_scoring.py`

**Interfaces:**
- Consumes: `add_custom_fantasy_scoring(df, league_settings)`
- Uses: `league_settings["scoring"]["offense"]`
- Produces: `custom_fantasy_points`, `custom_points_per_game`

- [ ] **Step 1: Add failing tests for exact cumulative and explosive-play arithmetic**

Use a synthetic row with zero ordinary stats except the category being tested. Add at least these tests:

```python
def test_passing_milestone_bonuses_stack_cumulatively():
    df = _zero_scoring_row()
    df.loc[0, "passing_yards"] = 500
    df.loc[0, ["games_300_pass", "games_400_pass", "games_500_pass"]] = 1

    settings = load_league_settings("drunk_sundays")
    result = add_custom_fantasy_scoring(df, settings)

    assert result.loc[0, "custom_fantasy_points"] == 32.0
    # 500 * .04 = 20; cumulative bonuses 2 + 4 + 6 = 12.


def test_same_long_play_profile_scores_differently_by_league():
    df = _zero_scoring_row()
    df.loc[0, "plays_40_rush"] = 1
    df.loc[0, "plays_40_reception"] = 1
    df.loc[0, "plays_40_rush_td"] = 1
    df.loc[0, "plays_40_reception_td"] = 1

    drunk = add_custom_fantasy_scoring(
        df, load_league_settings("drunk_sundays")
    )
    related = add_custom_fantasy_scoring(
        df, load_league_settings("somewhat_related")
    )

    assert drunk.loc[0, "custom_fantasy_points"] == 8
    assert related.loc[0, "custom_fantasy_points"] == 12
```

Also add focused tests for interception thrown `-1`, fumble lost `-2`, two-point conversion `+2`, return TD `+6`, and offensive fumble-return TD `+6` once their source columns are available in the master table.

- [ ] **Step 2: Verify the 2025 weekly player-stat schema before wiring the remaining ordinary categories**

Run locally:

```bash
python - <<'PY'
from fantasy_draft_model.integrations.data_loader import load_weekly_player_stats

df = load_weekly_player_stats()
keywords = ("interception", "fumble", "2pt", "two_point", "return", "special_teams")
print("\n".join(c for c in df.columns if any(k in c.lower() for k in keywords)))
PY
```

Expected: nflverse columns sufficient to identify passing interceptions and any available player-level fumble/2-point/special-teams scoring components. If a confirmed Yahoo category is not available in the weekly player table, derive it in the PBP integration rather than substituting `fantasy_points_ppr` or guessing.

- [ ] **Step 3: Run the new arithmetic tests and verify RED**

```bash
python -m pytest tests/test_league_scoring.py -v
```

Expected: failures because current arithmetic still assumes the old flat `scoring` object and old bonus values.

- [ ] **Step 4: Rewrite `add_custom_fantasy_scoring()` to use the selected offense profile**

Use `scoring = league_settings["scoring"]["offense"]`. Calculate points from explicit components only; do not use nflverse `fantasy_points_ppr` as a substitute for Yahoo custom scoring.

Required arithmetic categories:

```python
points = (
    receptions * scoring["reception"]
    + rushing_yards * scoring["rushing_yard"]
    + receiving_yards * scoring["receiving_yard"]
    + passing_yards * scoring["passing_yard"]
    + rushing_tds * scoring["rushing_td"]
    + receiving_tds * scoring["receiving_td"]
    + passing_tds * scoring["passing_td"]
    + passing_interceptions * scoring["passing_interception"]
    + fumbles_lost * scoring["fumble_lost"]
    + two_point_conversions * scoring["two_point_conversion"]
    + return_tds * scoring["return_td"]
    + offensive_fumble_return_tds * scoring["offensive_fumble_return_td"]
    + games_300_pass * scoring["bonus_300_passing"]
    + games_400_pass * scoring["bonus_400_passing"]
    + games_500_pass * scoring["bonus_500_passing"]
    + games_100_rush * scoring["bonus_100_rushing"]
    + games_200_rush * scoring["bonus_200_rushing"]
    + games_300_rush * scoring["bonus_300_rushing"]
    + games_100_receive * scoring["bonus_100_receiving"]
    + games_200_receive * scoring["bonus_200_receiving"]
    + games_300_receive * scoring["bonus_300_receiving"]
    + plays_40_pass_completion * scoring["play_40_completion"]
    + plays_40_pass_td * scoring["play_40_passing_td"]
    + plays_40_rush * scoring["play_40_run"]
    + plays_40_rush_td * scoring["play_40_rushing_td"]
    + plays_40_reception * scoring["play_40_reception"]
    + plays_40_reception_td * scoring["play_40_receiving_td"]
)
```

Use the existing `_series_or_default(df, column, 0)` helper so rookies or data rows missing a legitimate historical category receive zero rather than crashing.

- [ ] **Step 5: Run Task 4 tests and verify GREEN**

```bash
python -m pytest tests/test_league_scoring.py tests/test_long_play_loader.py -v
```

Expected: all #6 arithmetic and long-play tests pass.

- [ ] **Step 6: Commit Task 4**

```bash
git add fantasy_draft_model/models/projections.py tests/test_league_scoring.py
git commit -m "feat: apply league-specific offensive scoring"
```

---

### Task 5: Thread Explicit League Selection Through Projection, VORP, and Rankings

**Files:**
- Modify: `fantasy_draft_model/models/projections.py`
- Modify: `fantasy_draft_model/models/player_profiles.py`
- Modify: `fantasy_draft_model/engines/projection_engine.py`
- Modify: `fantasy_draft_model/rankings.py`
- Modify: `fantasy_draft_model/engines/vorp_engine.py` only if needed to remove an internal no-argument settings fallback
- Modify: existing tests that invoke public pipeline functions
- Test: `tests/test_league_scoring.py`

**Interfaces:**
- `create_master_player_table(league_key: str)`
- `build_player_profiles(league_key: str)`
- `build_2026_projections(league_key: str)`
- `build_draft_rankings(league_key: str)`

- [ ] **Step 1: Add failing explicit-pipeline tests**

```python
def test_public_projection_pipeline_requires_league_key():
    with pytest.raises(TypeError):
        build_2026_projections()


def test_public_rankings_pipeline_requires_league_key():
    with pytest.raises(TypeError):
        build_draft_rankings()
```

Add a focused monkeypatch test proving the selected league reaches VORP, for example by patching `load_league_settings`/`calculate_vorp` or by calling the deterministic lower-level path with a synthetic resolved settings dictionary.

- [ ] **Step 2: Run and verify RED**

```bash
python -m pytest tests/test_league_scoring.py -v
```

Expected: public functions still accept no arguments.

- [ ] **Step 3: Change the master/profile/projection/ranking signatures**

Use required positional parameters with no defaults:

```python
def create_master_player_table(league_key): ...
def build_player_profiles(league_key): ...
def build_2026_projections(league_key): ...
def build_draft_rankings(league_key): ...
```

At `create_master_player_table(league_key)`, resolve settings once with `load_league_settings(league_key)` and pass the resolved dictionary to `add_custom_fantasy_scoring(df, league_settings)`.

At `build_2026_projections(league_key)`, resolve the same selected settings for `calculate_vorp(df, league_settings)` so the lineup/FLEX economics from #5 remain attached to the selected league context.

- [ ] **Step 4: Update existing regression tests to pass an explicit league key**

For tests whose purpose is unrelated to league differences, use `"drunk_sundays"` explicitly. Do not add defaults to production code to keep old tests green.

Files expected to need updates based on the current suite:

- `tests/test_current_injury_pipeline.py`
- `tests/test_rookie_player_pool.py`
- `tests/test_rookie_projection_model.py`
- `tests/test_qb_1qb_economics.py` only where a public projection/ranking builder is called
- `tests/test_vorp_calibration.py` only where a no-argument settings loader/builder is called

- [ ] **Step 5: Update executable/debug entry points**

Any `main()` function in `projections.py`, `player_profiles.py`, `projection_engine.py`, or `rankings.py` must pass an explicit league key. Use `drunk_sundays` only for these developer/demo entry points, not as a default function parameter.

- [ ] **Step 6: Run focused pipeline regression**

```bash
python -m pytest tests/test_league_scoring.py tests/test_vorp_calibration.py tests/test_qb_1qb_economics.py tests/test_rookie_player_pool.py tests/test_rookie_projection_model.py tests/test_current_injury_normalizer.py tests/test_current_injury_pipeline.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit Task 5**

```bash
git add fantasy_draft_model tests
git commit -m "feat: require explicit league through draft pipeline"
```

---

### Task 6: Live Two-League Verification and Full Regression Gate

**Files:**
- No planned production files unless verification exposes a defect
- Test: entire suite

**Interfaces:**
- Verifies both public league keys execute independently
- Verifies scoring differences flow into `projected_points`, VORP, and draft rankings

- [ ] **Step 1: Run the full test suite**

```bash
python -m pytest -q
```

Expected: zero failures.

- [ ] **Step 2: Run live projections for both leagues**

```bash
python - <<'PY'
from fantasy_draft_model.engines.projection_engine import build_2026_projections

for league in ("drunk_sundays", "somewhat_related"):
    df = build_2026_projections(league)
    print(league, len(df), round(df["projected_points"].sum(), 2))
PY
```

Expected: both leagues build successfully; both return a non-empty draftable player pool. Aggregate projected points should differ because the explosive-play profiles differ.

- [ ] **Step 3: Run live rankings for both leagues and compare position counts**

```bash
python - <<'PY'
from fantasy_draft_model.rankings import build_draft_rankings

for league in ("drunk_sundays", "somewhat_related"):
    df = build_draft_rankings(league)
    print(f"\n{league}")
    for cutoff in (25, 50, 100):
        counts = (
            df[df["draft_rank"] <= cutoff]["position"]
            .value_counts()
            .reindex(["QB", "RB", "WR", "TE"])
            .fillna(0)
            .astype(int)
            .to_dict()
        )
        print(f"Top {cutoff}: {counts}")
PY
```

Expected: no obvious QB regression from #4 and no broken VORP boundaries from #5. Do not manually tune rankings solely to force the two leagues apart.

- [ ] **Step 4: Verify a representative explosive-play difference**

Print players with the largest absolute difference between the two leagues' historical custom points and confirm the difference is explainable by configured 40+ categories rather than a merge duplication or missing player ID.

- [ ] **Step 5: Re-run full suite after any verification fix**

```bash
python -m pytest -q
```

Expected: zero failures.

- [ ] **Step 6: Commit any verification-only fixes**

If no fix was required, do not create an empty commit. If a defect was fixed, commit only the verified change and its regression test.

---

## Self-Review Checklist

- Spec coverage: explicit profiles, no default, cumulative yardage bonuses, long-play PBP aggregation, all confirmed offensive categories, K/DEF storage, explicit league propagation, VORP propagation, and live two-league verification are each assigned to a task.
- Placeholder scan: no `TBD`, `TODO`, or unspecified implementation steps remain.
- Type/signature consistency: `league_key: str` is required at all public boundaries; `add_custom_fantasy_scoring` consumes a resolved settings dictionary; `calculate_vorp` receives the same resolved dictionary.
- Scope discipline: K/DEF projection/ranking logic stays out of #6 and remains recovery item #13.
