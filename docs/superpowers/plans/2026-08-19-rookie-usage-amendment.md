# EdgeIQ Rookie Usage Amendment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add role-aware rookie RB opportunity, a modest six-week rookie WR ramp, actual touches/fantasy-points-per-touch metrics, and projected rookie usage derived from veteran peer efficiency.

**Architecture:** Keep role/ramp/usage helpers in `fantasy_draft_model/engines/talent_engine.py` so they travel with the rookie projection model. The role hook consumes optional `rookie_role` data but does not source depth charts itself. Actual touch efficiency is computed from existing carries, receptions, and custom fantasy points; projected rookie touches are derived only after the rookie baseline exists.

**Tech Stack:** Python 3.14, pandas, pytest.

**Spec:** `docs/superpowers/specs/2026-08-19-rookie-usage-amendment.md`

## Global Constraints

- Do not redefine `is_rookie`.
- Do not use `depth_chart_loader.py` in this amendment.
- Do not infer a 2026 starting role from draft capital alone.
- Touches = carries + receptions.
- Targets are not touches.
- Rookie WR season ramp: 6 weeks and factor 0.96.
- Projected touch counts must come from veteran peer efficiency, not fixed guessed touch-volume constants.
- If peer efficiency is unavailable, projected usage remains 0.0 with unresolved quality.

---

### Task A: Add touch-efficiency metrics, role-aware RB opportunity, and WR ramp

**Files:**
- Modify: `fantasy_draft_model/engines/talent_engine.py`
- Modify: `tests/test_rookie_projection_model.py`

**Interfaces:**
- Produces `add_touch_efficiency_metrics(df)`, `add_rookie_ramp_factor(df)`.
- Extends `add_rookie_opportunity_score(df)` to consume optional `rookie_role`.

- [ ] **Step 1: Add failing tests**

Append tests that assert:

```python
def test_touch_math_and_fantasy_points_per_touch():
    df = pd.DataFrame([{
        "player_name_clean": "Example RB",
        "position": "RB",
        "is_rookie": False,
        "carries": 14,
        "receptions": 5,
        "custom_fantasy_points": 19.0,
    }])
    result = add_touch_efficiency_metrics(df)
    assert result.loc[0, "touches"] == 19
    assert result.loc[0, "fantasy_points_per_touch"] == 1.0


def test_confirmed_starter_rb_gets_more_opportunity_than_backup():
    df = pd.DataFrame([
        {"player_name_clean": "Starter", "position": "RB", "team": "AAA", "status": "Active", "is_rookie": True, "draft_number": 20, "rookie_role": "STARTER"},
        {"player_name_clean": "Backup", "position": "RB", "team": "AAA", "status": "Active", "is_rookie": True, "draft_number": 20, "rookie_role": "BACKUP"},
    ])
    df = calculate_rookie_talent_score(df)
    result = add_rookie_opportunity_score(df).set_index("player_name_clean")
    assert result.loc["Starter", "rookie_opportunity_score"] > result.loc["Backup", "rookie_opportunity_score"]


def test_wr_gets_modest_six_week_ramp_and_rb_does_not():
    df = pd.DataFrame([
        {"player_name_clean": "WR", "position": "WR", "is_rookie": True},
        {"player_name_clean": "RB", "position": "RB", "is_rookie": True},
        {"player_name_clean": "Veteran", "position": "WR", "is_rookie": False},
    ])
    result = add_rookie_ramp_factor(df).set_index("player_name_clean")
    assert result.loc["WR", "rookie_ramp_weeks"] == 6
    assert result.loc["WR", "rookie_ramp_factor"] == 0.96
    assert result.loc["RB", "rookie_ramp_factor"] == 1.0
    assert result.loc["Veteran", "rookie_ramp_factor"] == 1.0
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
python -m pytest tests/test_rookie_projection_model.py -v
```

Expected: import/attribute failure for new helper functions and/or starter-vs-backup assertion failure.

- [ ] **Step 3: Implement minimal helpers and role adjustment**

Implement `add_touch_efficiency_metrics(df)` using carries + receptions and safe division. Implement `add_rookie_ramp_factor(df)` with WR rookie = 6/0.96 and everyone else = 0/1.00. Extend RB opportunity with the approved role adjustments while defaulting missing roles to UNKNOWN.

- [ ] **Step 4: Run tests and verify GREEN**

Run the full rookie test file and require all tests to pass.

---

### Task B: Apply WR ramp to the composite rookie projection score

**Files:**
- Modify: `fantasy_draft_model/engines/talent_engine.py`
- Modify: `tests/test_rookie_projection_model.py`

**Interfaces:**
- `add_rookie_projection_components(df)` must call `add_rookie_ramp_factor(df)` and multiply the rookie weighted score by both team environment and ramp factor.

- [ ] Write a failing test proving otherwise-identical WR and RB rows preserve their positional differences and that a rookie WR composite score is multiplied by 0.96.
- [ ] Run RED.
- [ ] Implement the one integration change.
- [ ] Run GREEN.

---

### Task C: Add projected rookie usage after baseline projection

**Files:**
- Modify: `fantasy_draft_model/engines/talent_engine.py`
- Modify: `tests/test_rookie_projection_model.py`

**Interfaces:**
- Produces `add_rookie_projected_usage(df)`.
- Consumes `rookie_baseline_projection`, veteran `touches`, veteran `fantasy_points_per_touch`, `position`, and `is_rookie`.
- Produces `rookie_projected_touches`, `rookie_projected_touches_per_game`, `rookie_projected_carries`, `rookie_projected_receptions`, `rookie_projected_fp_per_touch`, `rookie_usage_data_quality`.

- [ ] **Step 1: Add failing data-driven usage test**

Use a veteran RB peer with 180 carries, 40 receptions, and 220 custom fantasy points (220 touches, 1.0 FP/touch), plus a rookie RB with a 190-point rookie baseline. Assert the rookie receives 190 projected touches, carries + receptions equals touches, and projected FP/touch equals 1.0.

- [ ] **Step 2: Run RED**

- [ ] **Step 3: Implement peer-median usage derivation**

Call `add_touch_efficiency_metrics()` first. For each RB/WR/TE, compute non-rookie position median FP/touch from players with meaningful touches (> 0). For RBs compute median veteran reception share `receptions / touches`. Derive rookie touch totals from baseline / peer median. For WR/TE set projected receptions equal projected touches and projected carries to 0. If no valid peer median exists, leave projected fields at 0.0 and set `rookie_usage_data_quality = "F"`; otherwise `"D"`.

- [ ] **Step 4: Run GREEN**

---

### Task D: Wire projected usage into the projection pipeline and validation output

**Files:**
- Modify: `fantasy_draft_model/engines/projection_engine.py`
- Modify: `tests/test_rookie_projection_model.py`

After `add_rookie_baseline_projection(df)`, call `add_rookie_projected_usage(df)`. Extend the source-regression test to require this function name. Final live validation should print rookie role/ramp/touch fields when present.
