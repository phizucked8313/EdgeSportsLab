# EdgeIQ 2026 Rookie Projection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Version 1 `rookie_talent_score × positional multiplier` baseline with a tested multi-factor rookie projection model using draft capital, conservative roster opportunity, positional rookie curves, a neutral Option C prospect hook, and a bounded team-environment multiplier.

**Architecture:** Keep the rookie model in `fantasy_draft_model/engines/talent_engine.py` so downstream interfaces stay compact. Add focused component functions, then update `projection_engine.py` to call them before `add_rookie_baseline_projection()`. The model must not depend on the stale 2025 depth-chart loader and must leave rookie identification unchanged for Recovery Item #3.

**Tech Stack:** Python 3.14, pandas, numpy-free model arithmetic, pytest, existing EdgeIQ projection pipeline.

**Spec:** `docs/superpowers/specs/2026-08-19-rookie-projection-design.md`

## Global Constraints

- Recovery Item #2 only: do not redefine `is_rookie`.
- Do not use `depth_chart_loader.py` or 2025 depth-chart rows.
- Do not change QB/VORP economics, keeper rules, league scoring, or draft order.
- No player-specific manual boosts.
- Missing draft capital receives a low non-zero score.
- Missing team environment defaults to `1.00`.
- Non-rookies keep neutral component fields and `rookie_baseline_projection = 0.0`.
- Unsupported positions receive `rookie_baseline_projection = 0.0`.
- Add `rookie_prospect_profile_score = 50.0` as the neutral Option C hook.
- Position bounds: RB 70–290, WR 60–260, TE 35–190, QB 40–330.
- Composite weights: 45% talent, 30% opportunity, 20% position curve, 5% prospect profile; team environment multiplies the weighted score afterward.

---

## File Structure

- Modify `fantasy_draft_model/engines/talent_engine.py` — all rookie component scoring and baseline conversion.
- Modify `fantasy_draft_model/engines/projection_engine.py` — call the new component functions in the 2026 projection pipeline.
- Create `tests/test_rookie_projection_model.py` — unit/regression coverage for the multi-factor model.

---

### Task 1: Smooth Draft-Capital Talent Score

**Files:**
- Modify: `fantasy_draft_model/engines/talent_engine.py`
- Create: `tests/test_rookie_projection_model.py`

**Interfaces:**
- Consumes: dataframe columns `is_rookie`, `draft_number`.
- Produces: `calculate_rookie_talent_score(df: pandas.DataFrame) -> pandas.DataFrame` with `rookie_talent_score`.

- [ ] **Step 1: Write the failing talent-score tests**

Create `tests/test_rookie_projection_model.py`:

```python
import pandas as pd

from fantasy_draft_model.engines.talent_engine import (
    calculate_rookie_talent_score,
)


def rookie_frame():
    return pd.DataFrame([
        {"player_name_clean": "Pick One", "position": "RB", "team": "AAA", "status": "Active", "is_rookie": True, "draft_number": 1},
        {"player_name_clean": "Pick Thirty Two", "position": "RB", "team": "BBB", "status": "Active", "is_rookie": True, "draft_number": 32},
        {"player_name_clean": "Pick One Hundred", "position": "RB", "team": "CCC", "status": "Active", "is_rookie": True, "draft_number": 100},
        {"player_name_clean": "Missing Pick", "position": "RB", "team": "DDD", "status": "Active", "is_rookie": True, "draft_number": None},
        {"player_name_clean": "Veteran", "position": "RB", "team": "EEE", "status": "Active", "is_rookie": False, "draft_number": 1},
    ])


def test_earlier_draft_capital_scores_higher_and_is_smooth():
    result = calculate_rookie_talent_score(rookie_frame()).set_index("player_name_clean")

    assert result.loc["Pick One", "rookie_talent_score"] > result.loc["Pick Thirty Two", "rookie_talent_score"]
    assert result.loc["Pick Thirty Two", "rookie_talent_score"] > result.loc["Pick One Hundred", "rookie_talent_score"]
    assert result.loc["Pick One", "rookie_talent_score"] == 100.0


def test_missing_draft_capital_is_low_but_nonzero_and_veterans_stay_neutral():
    result = calculate_rookie_talent_score(rookie_frame()).set_index("player_name_clean")

    assert result.loc["Missing Pick", "rookie_talent_score"] == 30.0
    assert result.loc["Veteran", "rookie_talent_score"] == 50.0
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
python -m pytest tests/test_rookie_projection_model.py -v
```

Expected: at least `test_earlier_draft_capital_scores_higher_and_is_smooth` FAILS because the current broad bucket gives picks 1 and 32 the same score.

- [ ] **Step 3: Replace bucketed draft capital with a smooth monotonic score**

In `talent_engine.py`, implement the rookie branch inside `calculate_rookie_talent_score()` as:

```python
    df["rookie_talent_score"] = 50.0

    if "is_rookie" not in df.columns:
        return df

    if "draft_number" not in df.columns:
        df["draft_number"] = None

    rookie_mask = df["is_rookie"] == True

    for index in df[rookie_mask].index:
        draft_number = pd.to_numeric(
            pd.Series([df.at[index, "draft_number"]]),
            errors="coerce",
        ).iloc[0]

        if pd.isna(draft_number) or draft_number <= 0:
            score = 30.0
        else:
            capped_pick = min(float(draft_number), 257.0)
            score = 100.0 - ((capped_pick - 1.0) / 256.0) * 70.0
            score = max(30.0, min(100.0, score))

        df.at[index, "rookie_talent_score"] = round(score, 2)
```

- [ ] **Step 4: Run the talent tests and verify GREEN**

Run:

```bash
python -m pytest tests/test_rookie_projection_model.py -v
```

Expected: 2 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add fantasy_draft_model/engines/talent_engine.py tests/test_rookie_projection_model.py
git commit -m "feat: smooth rookie draft capital score"
```

---

### Task 2: Add Conservative Roster Opportunity and Position Curves

**Files:**
- Modify: `fantasy_draft_model/engines/talent_engine.py`
- Modify: `tests/test_rookie_projection_model.py`

**Interfaces:**
- Consumes: `rookie_talent_score`, `is_rookie`, `position`, `team`, optional `status`.
- Produces: `add_rookie_opportunity_score(df)` and `add_rookie_position_curve(df)` with `rookie_opportunity_score` and `rookie_position_curve_score`.

- [ ] **Step 1: Add failing component tests**

Append to `tests/test_rookie_projection_model.py`:

```python
from fantasy_draft_model.engines.talent_engine import (
    add_rookie_opportunity_score,
    add_rookie_position_curve,
)


def test_high_capital_rookie_gets_more_opportunity_than_late_pick():
    df = pd.DataFrame([
        {"player_name_clean": "Early", "position": "WR", "team": "AAA", "status": "Active", "is_rookie": True, "draft_number": 10},
        {"player_name_clean": "Late", "position": "WR", "team": "BBB", "status": "Active", "is_rookie": True, "draft_number": 220},
    ])
    df = calculate_rookie_talent_score(df)
    result = add_rookie_opportunity_score(df).set_index("player_name_clean")

    assert result.loc["Early", "rookie_opportunity_score"] > result.loc["Late", "rookie_opportunity_score"]
    assert result["rookie_opportunity_score"].between(35.0, 90.0).all()


def test_position_curves_are_distinct_and_veterans_are_neutral():
    df = pd.DataFrame([
        {"player_name_clean": "RB Rookie", "position": "RB", "is_rookie": True},
        {"player_name_clean": "WR Rookie", "position": "WR", "is_rookie": True},
        {"player_name_clean": "TE Rookie", "position": "TE", "is_rookie": True},
        {"player_name_clean": "QB Rookie", "position": "QB", "is_rookie": True},
        {"player_name_clean": "Veteran", "position": "RB", "is_rookie": False},
    ])
    result = add_rookie_position_curve(df).set_index("player_name_clean")

    assert result.loc["RB Rookie", "rookie_position_curve_score"] == 85.0
    assert result.loc["WR Rookie", "rookie_position_curve_score"] == 75.0
    assert result.loc["QB Rookie", "rookie_position_curve_score"] == 65.0
    assert result.loc["TE Rookie", "rookie_position_curve_score"] == 55.0
    assert result.loc["Veteran", "rookie_position_curve_score"] == 50.0
```

- [ ] **Step 2: Run the new tests and verify RED**

Run:

```bash
python -m pytest tests/test_rookie_projection_model.py -v
```

Expected: import/attribute failure because the two new functions do not yet exist.

- [ ] **Step 3: Implement `add_rookie_opportunity_score()`**

Add to `talent_engine.py`:

```python
POSITION_OPPORTUNITY_BASE = {
    "RB": 65.0,
    "WR": 60.0,
    "TE": 50.0,
    "QB": 45.0,
}

ACTIVE_STATUSES = {"active", "act"}
LIMITED_STATUSES = {"inactive", "ir", "pup", "reserve", "res"}


def add_rookie_opportunity_score(df):
    df = df.copy()
    df["rookie_opportunity_score"] = 50.0

    if "is_rookie" not in df.columns:
        return df

    if "rookie_talent_score" not in df.columns:
        df = calculate_rookie_talent_score(df)

    for index in df[df["is_rookie"] == True].index:
        position = str(df.at[index, "position"]).upper().strip()
        base = POSITION_OPPORTUNITY_BASE.get(position, 45.0)
        talent = float(df.at[index, "rookie_talent_score"])

        score = base + (talent - 50.0) * 0.35

        team = df.at[index, "team"] if "team" in df.columns else None
        if pd.notna(team) and str(team).strip():
            score += 5.0
        else:
            score -= 10.0

        status = df.at[index, "status"] if "status" in df.columns else None
        status_key = "" if pd.isna(status) else str(status).strip().lower()
        if status_key in ACTIVE_STATUSES:
            score += 5.0
        elif status_key in LIMITED_STATUSES:
            score -= 10.0

        df.at[index, "rookie_opportunity_score"] = round(
            max(35.0, min(90.0, score)),
            2,
        )

    return df
```

- [ ] **Step 4: Implement `add_rookie_position_curve()`**

Add:

```python
ROOKIE_POSITION_CURVE = {
    "RB": 85.0,
    "WR": 75.0,
    "QB": 65.0,
    "TE": 55.0,
}


def add_rookie_position_curve(df):
    df = df.copy()
    df["rookie_position_curve_score"] = 50.0

    if "is_rookie" not in df.columns:
        return df

    rookie_mask = df["is_rookie"] == True
    df.loc[rookie_mask, "rookie_position_curve_score"] = (
        df.loc[rookie_mask, "position"]
        .astype(str)
        .str.upper()
        .map(ROOKIE_POSITION_CURVE)
        .fillna(50.0)
    )

    return df
```

- [ ] **Step 5: Run the component tests and verify GREEN**

Run:

```bash
python -m pytest tests/test_rookie_projection_model.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add fantasy_draft_model/engines/talent_engine.py tests/test_rookie_projection_model.py
git commit -m "feat: add rookie opportunity and position curves"
```

---

### Task 3: Add Team Environment, Prospect Hook, and Composite Score

**Files:**
- Modify: `fantasy_draft_model/engines/talent_engine.py`
- Modify: `tests/test_rookie_projection_model.py`

**Interfaces:**
- Consumes: talent, opportunity, position curve, `is_rookie`.
- Produces: `add_rookie_team_environment(df)`, `add_rookie_projection_components(df)`, columns `rookie_team_environment_multiplier`, `rookie_prospect_profile_score`, `rookie_projection_score`.

- [ ] **Step 1: Add failing composite tests**

Append:

```python
from fantasy_draft_model.engines.talent_engine import (
    add_rookie_team_environment,
    add_rookie_projection_components,
)


def test_team_environment_defaults_to_neutral():
    df = pd.DataFrame([
        {"player_name_clean": "Rookie", "position": "RB", "is_rookie": True},
    ])
    result = add_rookie_team_environment(df)
    assert result.loc[0, "rookie_team_environment_multiplier"] == 1.0


def test_composite_score_rewards_stronger_available_inputs():
    df = pd.DataFrame([
        {"player_name_clean": "Strong", "position": "WR", "team": "AAA", "status": "Active", "is_rookie": True, "draft_number": 8},
        {"player_name_clean": "Weak", "position": "WR", "team": "BBB", "status": "Active", "is_rookie": True, "draft_number": 220},
    ])
    result = add_rookie_projection_components(df).set_index("player_name_clean")

    assert result.loc["Strong", "rookie_projection_score"] > result.loc["Weak", "rookie_projection_score"]
    assert result.loc["Strong", "rookie_prospect_profile_score"] == 50.0
    assert result.loc["Weak", "rookie_team_environment_multiplier"] == 1.0
```

- [ ] **Step 2: Run and verify RED**

Run:

```bash
python -m pytest tests/test_rookie_projection_model.py -v
```

Expected: import/attribute failure for the new functions.

- [ ] **Step 3: Implement neutral team environment**

Add:

```python
def add_rookie_team_environment(df):
    df = df.copy()
    if "rookie_team_environment_multiplier" not in df.columns:
        df["rookie_team_environment_multiplier"] = 1.0
    else:
        df["rookie_team_environment_multiplier"] = (
            pd.to_numeric(
                df["rookie_team_environment_multiplier"],
                errors="coerce",
            )
            .fillna(1.0)
            .clip(lower=0.95, upper=1.05)
        )
    return df
```

- [ ] **Step 4: Implement the composite pipeline**

Add:

```python
def add_rookie_projection_components(df):
    df = df.copy()
    df = calculate_rookie_talent_score(df)
    df = add_rookie_opportunity_score(df)
    df = add_rookie_position_curve(df)
    df = add_rookie_team_environment(df)

    df["rookie_prospect_profile_score"] = 50.0
    df["rookie_projection_score"] = 50.0

    if "is_rookie" not in df.columns:
        return df

    rookie_mask = df["is_rookie"] == True

    weighted = (
        df.loc[rookie_mask, "rookie_talent_score"] * 0.45
        + df.loc[rookie_mask, "rookie_opportunity_score"] * 0.30
        + df.loc[rookie_mask, "rookie_position_curve_score"] * 0.20
        + df.loc[rookie_mask, "rookie_prospect_profile_score"] * 0.05
    )

    df.loc[rookie_mask, "rookie_projection_score"] = (
        weighted
        * df.loc[rookie_mask, "rookie_team_environment_multiplier"]
    ).clip(lower=0.0, upper=100.0).round(2)

    return df
```

- [ ] **Step 5: Run and verify GREEN**

Run:

```bash
python -m pytest tests/test_rookie_projection_model.py -v
```

Expected: 6 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add fantasy_draft_model/engines/talent_engine.py tests/test_rookie_projection_model.py
git commit -m "feat: add rookie composite projection score"
```

---

### Task 4: Replace the Version 1 Rookie Baseline Formula

**Files:**
- Modify: `fantasy_draft_model/engines/talent_engine.py`
- Modify: `tests/test_rookie_projection_model.py`

**Interfaces:**
- Consumes: `rookie_projection_score`, `position`, `is_rookie`.
- Produces: `add_rookie_baseline_projection(df)` and bounded `rookie_baseline_projection`.

- [ ] **Step 1: Add failing baseline-bound tests**

Append:

```python
from fantasy_draft_model.engines.talent_engine import (
    add_rookie_baseline_projection,
)


POSITION_BOUNDS = {
    "RB": (70.0, 290.0),
    "WR": (60.0, 260.0),
    "TE": (35.0, 190.0),
    "QB": (40.0, 330.0),
}


def test_rookie_baselines_respect_position_specific_bounds():
    rows = []
    for position in POSITION_BOUNDS:
        rows.append({
            "player_name_clean": f"{position} Rookie",
            "position": position,
            "team": "AAA",
            "status": "Active",
            "is_rookie": True,
            "draft_number": 1,
        })
    df = add_rookie_projection_components(pd.DataFrame(rows))
    result = add_rookie_baseline_projection(df)

    for _, row in result.iterrows():
        low, high = POSITION_BOUNDS[row["position"]]
        assert low <= row["rookie_baseline_projection"] <= high


def test_veterans_and_unsupported_positions_do_not_get_rookie_baseline():
    df = pd.DataFrame([
        {"player_name_clean": "Veteran", "position": "RB", "is_rookie": False, "rookie_projection_score": 100.0},
        {"player_name_clean": "Rookie K", "position": "K", "is_rookie": True, "rookie_projection_score": 100.0},
    ])
    result = add_rookie_baseline_projection(df).set_index("player_name_clean")

    assert result.loc["Veteran", "rookie_baseline_projection"] == 0.0
    assert result.loc["Rookie K", "rookie_baseline_projection"] == 0.0
```

- [ ] **Step 2: Run and verify RED**

Run:

```bash
python -m pytest tests/test_rookie_projection_model.py -v
```

Expected: failure because the current baseline still uses `rookie_talent_score × positional multiplier` and does not consume `rookie_projection_score`.

- [ ] **Step 3: Replace the baseline function body**

Use:

```python
ROOKIE_PROJECTION_BOUNDS = {
    "RB": (70.0, 290.0),
    "WR": (60.0, 260.0),
    "TE": (35.0, 190.0),
    "QB": (40.0, 330.0),
}


def add_rookie_baseline_projection(df):
    df = df.copy()
    df["rookie_baseline_projection"] = 0.0

    if "is_rookie" not in df.columns:
        return df

    if "rookie_projection_score" not in df.columns:
        df = add_rookie_projection_components(df)

    for index in df[df["is_rookie"] == True].index:
        position = str(df.at[index, "position"]).upper().strip()
        bounds = ROOKIE_PROJECTION_BOUNDS.get(position)

        if bounds is None:
            continue

        low, high = bounds
        score = float(df.at[index, "rookie_projection_score"])
        baseline = low + (score / 100.0) * (high - low)
        df.at[index, "rookie_baseline_projection"] = round(
            max(low, min(high, baseline)),
            2,
        )

    return df
```

- [ ] **Step 4: Run and verify GREEN**

Run:

```bash
python -m pytest tests/test_rookie_projection_model.py -v
```

Expected: 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add fantasy_draft_model/engines/talent_engine.py tests/test_rookie_projection_model.py
git commit -m "feat: replace rookie baseline projection formula"
```

---

### Task 5: Wire the Multi-Factor Model into `projection_engine.py`

**Files:**
- Modify: `fantasy_draft_model/engines/projection_engine.py`
- Modify: `tests/test_rookie_projection_model.py`

**Interfaces:**
- Consumes: `add_rookie_projection_components(df)` and `add_rookie_baseline_projection(df)`.
- Produces: existing `build_2026_projections()` output with upgraded rookie baseline fields.

- [ ] **Step 1: Add a failing source-regression test**

Append:

```python
from pathlib import Path


def test_projection_engine_calls_multi_factor_rookie_components():
    source = Path(
        "fantasy_draft_model/engines/projection_engine.py"
    ).read_text(encoding="utf-8")

    assert "add_rookie_projection_components" in source
    assert "add_rookie_baseline_projection" in source
```

- [ ] **Step 2: Run and verify RED**

Run:

```bash
python -m pytest tests/test_rookie_projection_model.py::test_projection_engine_calls_multi_factor_rookie_components -v
```

Expected: FAIL because `projection_engine.py` currently imports only `calculate_rookie_talent_score` and `add_rookie_baseline_projection`.

- [ ] **Step 3: Update the import**

Replace the talent-engine import in `projection_engine.py` with:

```python
from fantasy_draft_model.engines.talent_engine import (
    add_rookie_projection_components,
    add_rookie_baseline_projection,
)
```

- [ ] **Step 4: Update the rookie pipeline calls**

Replace:

```python
    df = calculate_rookie_talent_score(
        df
    )

    df = add_rookie_baseline_projection(
        df
    )
```

with:

```python
    df = add_rookie_projection_components(
        df
    )

    df = add_rookie_baseline_projection(
        df
    )
```

- [ ] **Step 5: Run the rookie unit/regression suite**

Run:

```bash
python -m pytest tests/test_rookie_projection_model.py -v
```

Expected: 9 tests PASS.

- [ ] **Step 6: Run the existing current-injury regression suite too**

Run:

```bash
python -m pytest tests/test_current_injury_normalizer.py tests/test_current_injury_pipeline.py tests/test_rookie_projection_model.py -v
```

Expected: all current injury and rookie tests PASS, proving Recovery Item #2 did not break Recovery Item #1.

- [ ] **Step 7: Commit**

```bash
git add fantasy_draft_model/engines/projection_engine.py tests/test_rookie_projection_model.py
git commit -m "feat: wire multi-factor rookie projections"
```

---

### Task 6: Live Rookie Projection Validation

**Files:**
- No production changes expected unless the smoke test exposes a concrete defect.

**Interfaces:**
- Consumes: `build_2026_projections()`.
- Produces: live inspection table of rookie component scores and baselines.

- [ ] **Step 1: Compile changed production modules**

Run:

```bash
python -m py_compile fantasy_draft_model/engines/talent_engine.py fantasy_draft_model/engines/projection_engine.py
```

Expected: no traceback.

- [ ] **Step 2: Run all focused tests**

Run:

```bash
python -m pytest tests/test_current_injury_normalizer.py tests/test_current_injury_pipeline.py tests/test_rookie_projection_model.py -v
```

Expected: all tests PASS.

- [ ] **Step 3: Print live rookie outputs**

Run:

```bash
python -c "from fantasy_draft_model.engines.projection_engine import build_2026_projections; d=build_2026_projections(); r=d[d['is_rookie']==True].copy(); cols=['player_name_clean','team','position','draft_number','rookie_talent_score','rookie_opportunity_score','rookie_position_curve_score','rookie_projection_score','rookie_baseline_projection','projected_points']; print(r.sort_values('rookie_projection_score',ascending=False)[cols].head(40).round(2).to_string(index=False)); print('rookies=',len(r))"
```

Expected: rookies print with non-flat component separation; no stale depth-chart dependency is invoked by the rookie model itself.

- [ ] **Step 4: Check model bounds by position**

Run:

```bash
python -c "from fantasy_draft_model.engines.projection_engine import build_2026_projections; d=build_2026_projections(); r=d[d['is_rookie']==True]; print(r.groupby('position')['rookie_baseline_projection'].agg(['count','min','max','mean']).round(2).to_string())"
```

Expected: RB/WR/TE/QB baselines stay within the defined model bounds; unsupported positions remain zero.

- [ ] **Step 5: Confirm git state**

Run:

```bash
git status --short
```

Expected: only intentional runtime/cache artifacts, if any; production and test changes are committed.

---

## Self-Review

- Spec coverage: smooth draft capital, conservative opportunity, positional curves, neutral team environment, Option C hook, weighted composite, position-specific bounds, missing-data behavior, veteran protection, projection integration, and live validation are all assigned to tasks.
- Placeholder scan: no TBD/TODO/"implement later" steps remain.
- Type consistency: every component consumes and returns pandas DataFrames; function names match across tests and projection integration.
- Scope: rookie identification remains untouched and is explicitly deferred to Recovery Item #3; stale 2025 depth charts are not used by this model; QB/VORP economics remain untouched.
