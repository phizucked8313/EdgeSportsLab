# Rookie Identity and Fantasy Player Pool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve canonical 2026 rookie identity while adding a separate draftability layer that keeps fringe/current-camp records out of EdgeIQ rankings and mocks.

**Architecture:** `roster_loader.py` remains the authoritative source of rookie identity using current roster metadata. `projections.py` adds draftability after historical stats and current roster identity are merged. Downstream live projections filter to `is_fantasy_draftable == True`, while the full master table remains available for diagnostics.

**Tech Stack:** Python 3, pandas, nflreadpy, pytest

**Spec:** `docs/superpowers/specs/2026-08-19-rookie-player-pool-design.md`

## Global Constraints

- `is_rookie` must be based on `rookie_year == 2026`, never on absence of 2025 statistics.
- Identity and draftability must remain separate fields.
- Injury/reserve status alone must not make a valuable player non-draftable.
- Do not hard-code named players or outside consensus rankings.
- Preserve the full master table for diagnostics; filter only the live draftable projection/ranking path.
- Do not change QB/VORP, keeper, depth-chart, or scoring behavior in this recovery item.

---

### Task 1: Lock Canonical Rookie Identity With Tests

**Files:**
- Create: `tests/test_rookie_player_pool.py`
- Modify only if required by failing test: `fantasy_draft_model/integrations/roster_loader.py`

**Interfaces:**
- Consumes: `prepare_fantasy_rosters()` current roster metadata.
- Produces: canonical `is_rookie` derived from `rookie_year == CURRENT_SEASON`.

- [ ] **Step 1: Write failing/characterization tests**

Add tests that verify the canonical rule directly on a synthetic roster frame via a small helper function `add_rookie_identity(df, current_season=2026)`:

```python
import pandas as pd

from fantasy_draft_model.integrations.roster_loader import add_rookie_identity


def test_rookie_identity_comes_from_rookie_year_not_missing_stats():
    df = pd.DataFrame([
        {"full_name": "True Rookie", "rookie_year": 2026, "years_exp": 0},
        {"full_name": "Veteran", "rookie_year": 2024, "years_exp": 2},
        {"full_name": "Odd Veteran", "rookie_year": 2025, "years_exp": 0},
    ])
    result = add_rookie_identity(df, current_season=2026).set_index("full_name")

    assert bool(result.loc["True Rookie", "is_rookie"]) is True
    assert bool(result.loc["Veteran", "is_rookie"]) is False
    assert bool(result.loc["Odd Veteran", "is_rookie"]) is False
```

- [ ] **Step 2: Run the new test and verify RED**

Run:

```bash
python -m pytest tests/test_rookie_player_pool.py::test_rookie_identity_comes_from_rookie_year_not_missing_stats -v
```

Expected: FAIL because `add_rookie_identity` does not yet exist.

- [ ] **Step 3: Implement the minimal identity helper**

In `roster_loader.py` add:

```python
def add_rookie_identity(df, current_season=CURRENT_SEASON):
    df = df.copy()
    rookie_year = pd.to_numeric(df.get("rookie_year"), errors="coerce")
    df["is_rookie"] = rookie_year.eq(current_season)
    return df
```

Then replace the inline `df["is_rookie"] = ...` assignment in `prepare_fantasy_rosters()` with:

```python
    df = add_rookie_identity(df)
```

- [ ] **Step 4: Run the test and verify GREEN**

```bash
python -m pytest tests/test_rookie_player_pool.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add fantasy_draft_model/integrations/roster_loader.py tests/test_rookie_player_pool.py
git commit -m "test: lock canonical 2026 rookie identity"
```

---

### Task 2: Preserve Current-Roster Presence Through the Master Merge

**Files:**
- Modify: `fantasy_draft_model/models/projections.py`
- Modify: `tests/test_rookie_player_pool.py`

**Interfaces:**
- Consumes: historical player rows + current roster rows.
- Produces: `on_current_roster` boolean in merged master player table.

- [ ] **Step 1: Add failing merge-presence test**

Use a small extracted helper `merge_current_roster_identity(historical_df, roster_df)` so the behavior can be tested without network calls:

```python
def test_current_roster_presence_is_preserved_after_outer_merge():
    historical = pd.DataFrame([
        {"player_id": "old", "player_name_clean": "Old Veteran", "team": "AAA", "position": "WR", "games_played": 10},
    ])
    roster = pd.DataFrame([
        {"player_id": "rook", "roster_player_name": "True Rookie", "current_team": "BBB", "current_position": "RB", "status": "Active", "rookie_year": 2026, "is_rookie": True},
    ])

    result = merge_current_roster_identity(historical, roster).set_index("player_id")

    assert bool(result.loc["rook", "on_current_roster"]) is True
    assert bool(result.loc["old", "on_current_roster"]) is False
```

- [ ] **Step 2: Run and verify RED**

```bash
python -m pytest tests/test_rookie_player_pool.py::test_current_roster_presence_is_preserved_after_outer_merge -v
```

Expected: FAIL because the helper/flag does not exist.

- [ ] **Step 3: Extract merge helper and add flag**

Refactor only the existing merge body from `add_current_roster_identity()` into:

```python
def merge_current_roster_identity(historical_df, roster_df):
    historical_df = historical_df.copy()
    roster_df = roster_df.copy()
    roster_df["on_current_roster"] = True

    merged_df = historical_df.merge(roster_df, on="player_id", how="outer")
    merged_df["on_current_roster"] = merged_df["on_current_roster"].fillna(False).astype(bool)
    # existing authoritative-name/team/position fill and numeric fill logic follows unchanged
    return merged_df
```

`add_current_roster_identity()` should prepare/rename the live roster frame and then call the helper.

- [ ] **Step 4: Run and verify GREEN**

```bash
python -m pytest tests/test_rookie_player_pool.py -v
```

- [ ] **Step 5: Commit**

```bash
git add fantasy_draft_model/models/projections.py tests/test_rookie_player_pool.py
git commit -m "feat: preserve current roster presence in master table"
```

---

### Task 3: Add Separate Fantasy Draftability Flag

**Files:**
- Modify: `fantasy_draft_model/models/projections.py`
- Modify: `tests/test_rookie_player_pool.py`

**Interfaces:**
- Consumes: merged master rows with `on_current_roster`, `is_rookie`, `draft_number`, `games_played`, `status`, `team`, `position`.
- Produces: `add_fantasy_draftable_flag(df)` and boolean `is_fantasy_draftable`.

- [ ] **Step 1: Add failing draftability tests**

```python
def test_draftability_is_separate_from_rookie_identity():
    df = pd.DataFrame([
        {"player_name_clean": "Drafted Rookie", "position": "RB", "team": "AAA", "on_current_roster": True, "is_rookie": True, "draft_number": 45, "games_played": 0, "status": "Active"},
        {"player_name_clean": "Fringe Rookie", "position": "WR", "team": "BBB", "on_current_roster": True, "is_rookie": True, "draft_number": 0, "games_played": 0, "status": "Inactive"},
        {"player_name_clean": "Veteran Producer", "position": "WR", "team": "CCC", "on_current_roster": True, "is_rookie": False, "draft_number": 0, "games_played": 12, "status": "Active"},
        {"player_name_clean": "Historical Only", "position": "WR", "team": "DDD", "on_current_roster": False, "is_rookie": False, "draft_number": 0, "games_played": 10, "status": None},
        {"player_name_clean": "PUP Star", "position": "RB", "team": "EEE", "on_current_roster": True, "is_rookie": False, "draft_number": 0, "games_played": 15, "status": "PUP"},
    ])
    result = add_fantasy_draftable_flag(df).set_index("player_name_clean")

    assert bool(result.loc["Drafted Rookie", "is_fantasy_draftable"]) is True
    assert bool(result.loc["Fringe Rookie", "is_fantasy_draftable"]) is False
    assert bool(result.loc["Veteran Producer", "is_fantasy_draftable"]) is True
    assert bool(result.loc["Historical Only", "is_fantasy_draftable"]) is False
    assert bool(result.loc["PUP Star", "is_fantasy_draftable"]) is True
    assert bool(result.loc["Fringe Rookie", "is_rookie"]) is True
```

- [ ] **Step 2: Run and verify RED**

```bash
python -m pytest tests/test_rookie_player_pool.py::test_draftability_is_separate_from_rookie_identity -v
```

Expected: FAIL because `add_fantasy_draftable_flag` does not exist.

- [ ] **Step 3: Implement conservative draftability**

```python
DRAFTABLE_POSITIONS = {"QB", "RB", "WR", "TE"}
NON_DRAFTABLE_FRINGE_STATUSES = {"inactive", "waived", "released", "cut"}


def add_fantasy_draftable_flag(df):
    df = df.copy()

    position_ok = df["position"].isin(DRAFTABLE_POSITIONS)
    team_ok = df["team"].notna() & df["team"].astype(str).str.strip().ne("")
    roster_ok = df.get("on_current_roster", False)
    games = pd.to_numeric(df.get("games_played", 0), errors="coerce").fillna(0)
    draft_number = pd.to_numeric(df.get("draft_number", 0), errors="coerce").fillna(0)
    rookie = df.get("is_rookie", False).fillna(False).astype(bool)
    status = df.get("status", "").fillna("").astype(str).str.strip().str.lower()

    prior_production = games > 0
    drafted_rookie = rookie & (draft_number > 0)
    active_udfa_rookie = rookie & draft_number.le(0) & status.isin({"active", "act"})
    current_veteran = (~rookie) & prior_production

    meaningful = prior_production | drafted_rookie | active_udfa_rookie | current_veteran
    fringe_block = rookie & draft_number.le(0) & status.isin(NON_DRAFTABLE_FRINGE_STATUSES)

    df["is_fantasy_draftable"] = (
        position_ok & team_ok & roster_ok & meaningful & ~fringe_block
    ).astype(bool)

    return df
```

This deliberately keeps active UDFAs visible because legitimate undrafted rookies can earn fantasy roles; clearly inactive/fringe UDFAs are filtered. Later depth-chart freshness (#9) can sharpen this without corrupting rookie identity.

- [ ] **Step 4: Run and verify GREEN**

```bash
python -m pytest tests/test_rookie_player_pool.py -v
```

- [ ] **Step 5: Commit**

```bash
git add fantasy_draft_model/models/projections.py tests/test_rookie_player_pool.py
git commit -m "feat: separate fantasy draftability from rookie identity"
```

---

### Task 4: Add Draftability to Master Table and Live Projection Boundary

**Files:**
- Modify: `fantasy_draft_model/models/projections.py`
- Modify: `fantasy_draft_model/engines/projection_engine.py`
- Modify: `tests/test_rookie_player_pool.py`

**Interfaces:**
- Consumes: `add_fantasy_draftable_flag(df)`.
- Produces: full master table with flag plus live projection pool filtered to draftable rows.

- [ ] **Step 1: Add source-regression test**

```python
from pathlib import Path


def test_live_projection_engine_filters_to_fantasy_draftable_pool():
    source = Path("fantasy_draft_model/engines/projection_engine.py").read_text(encoding="utf-8")
    assert 'is_fantasy_draftable' in source
```

- [ ] **Step 2: Run and verify RED**

```bash
python -m pytest tests/test_rookie_player_pool.py::test_live_projection_engine_filters_to_fantasy_draftable_pool -v
```

- [ ] **Step 3: Wire master-table flag**

In `create_master_player_table()` call:

```python
    df = add_fantasy_draftable_flag(df)
```

after current roster identity and before sorting/return.

- [ ] **Step 4: Filter live projection pool once**

Immediately after `build_player_profiles()` in `build_2026_projections()`:

```python
    if "is_fantasy_draftable" in df.columns:
        df = df[df["is_fantasy_draftable"] == True].copy()
```

Do not change the full master-table return path.

- [ ] **Step 5: Run focused tests**

```bash
python -m pytest tests/test_rookie_player_pool.py tests/test_rookie_projection_model.py tests/test_current_injury_normalizer.py tests/test_current_injury_pipeline.py -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add fantasy_draft_model/models/projections.py fantasy_draft_model/engines/projection_engine.py tests/test_rookie_player_pool.py
git commit -m "feat: filter live projections to draftable player pool"
```

---

### Task 5: Live Diagnostic and Recovery Verification

**Files:**
- No production changes expected unless diagnostics expose a concrete defect.

**Interfaces:**
- Consumes: `create_master_player_table()` and `build_2026_projections()`.
- Produces: evidence for recovery item #3 completion.

- [ ] **Step 1: Run compile check**

```bash
python -m py_compile fantasy_draft_model/integrations/roster_loader.py fantasy_draft_model/models/projections.py fantasy_draft_model/engines/projection_engine.py
```

- [ ] **Step 2: Run full focused regression suite**

```bash
python -m pytest tests/test_rookie_player_pool.py tests/test_rookie_projection_model.py tests/test_current_injury_normalizer.py tests/test_current_injury_pipeline.py -v
```

- [ ] **Step 3: Compare raw rookies vs draftable rookies**

```bash
python -c "from fantasy_draft_model.models.projections import create_master_player_table; d=create_master_player_table(); r=d[d['is_rookie']==True]; print('raw rookies=',len(r)); print('draftable rookies=',int(r['is_fantasy_draftable'].sum())); print(r.groupby(['position','is_fantasy_draftable']).size().to_string())"
```

Expected: raw rookie count remains intact, draftable rookie count is materially smaller.

- [ ] **Step 4: Inspect excluded rookie examples**

```bash
python -c "from fantasy_draft_model.models.projections import create_master_player_table; d=create_master_player_table(); r=d[(d['is_rookie']==True)&(d['is_fantasy_draftable']==False)]; cols=['player_name_clean','team','position','status','rookie_year','years_exp','draft_number','on_current_roster']; print(r[cols].head(60).to_string(index=False))"
```

Expected: exclusions are explainable fringe/non-current records rather than obviously valuable drafted/active rookies.

- [ ] **Step 5: Inspect live projection rookie count**

```bash
python -c "from fantasy_draft_model.engines.projection_engine import build_2026_projections; d=build_2026_projections(); r=d[d['is_rookie']==True]; print('live draftable rookies=',len(r)); print(r.groupby('position').size().to_string())"
```

- [ ] **Step 6: Confirm git state**

```bash
git status --short
```

Expected: only runtime/cache artifacts, if any.

---

## Self-Review

- Spec coverage: canonical rookie identity, current-roster presence, separate draftability, historical-only veteran exclusion, injury-status preservation, downstream live filtering, and live diagnostics are all assigned to tasks.
- Placeholder scan: no TBD/TODO/implement-later steps remain.
- Type consistency: all helpers consume and return pandas DataFrames; all new flags are booleans.
- Scope: rookie projection math, QB/VORP, keepers, scoring, and depth-chart freshness remain untouched.
