# EdgeIQ Advanced Assistant Features Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existing EdgeIQ advanced draft-assistant engines operate as one reliable league-specific pipeline.

**Architecture:** Keep the existing ranking, pressure, wait, run, and Draft Brain engines unchanged in responsibility. Modify only `draft_assistant.py` orchestration so rankings are league-specific, pressure is computed before Draft Brain, context is passed through, and the final board exposes the resulting signals.

**Tech Stack:** Python 3, pandas, pytest

**Spec:** `docs/superpowers/specs/2026-08-19-advanced-assistant-features-design.md`

## Global Constraints

- Do not add new scoring math or calibrated probability models.
- Do not change Pressure Meter, What-If-I-Wait, Position Run Detector, or Draft Brain formulas unless a regression test exposes a separate defect.
- Require explicit `league_key` at the public assistant entry point.
- Preserve all existing league, keeper, QB, roster-completion, injury, rookie, and metadata behavior.

---

### Task 1: Lock down assistant orchestration with RED tests

**Files:**
- Create: `tests/test_advanced_assistant_pipeline.py`
- Read: `fantasy_draft_model/draft_assistant.py`

**Interfaces:**
- Consumes: `build_draft_rankings(league_key)`, `add_pressure_meter(df)`, `add_draft_brain(df, draft_context)`
- Produces: test contract for `build_draft_assistant(league_key, draft_context=None) -> pandas.DataFrame`

- [ ] **Step 1: Write failing tests**

Tests must monkeypatch the three orchestration dependencies and assert:

```python
board = draft_assistant.build_draft_assistant(
    "drunk_sundays",
    draft_context={"picks_until_user": 7},
)
```

- `build_draft_rankings` receives `"drunk_sundays"`.
- `add_pressure_meter` runs before `add_draft_brain`.
- `add_draft_brain` receives `{"picks_until_user": 7}`.
- final rows contain `pressure_score`, `pressure_label`, `pressure_bar`, `brain_score`, `brain_recommendation`, `brain_reasons`, and `brain_warnings`.
- final result is sorted descending by `brain_score`.

- [ ] **Step 2: Run test to verify RED**

Run:

```bash
python -m pytest tests/test_advanced_assistant_pipeline.py -v
```

Expected: FAIL because the current assistant does not accept/pass `league_key` and does not call `add_pressure_meter`.

- [ ] **Step 3: Commit RED tests**

Commit message:

```text
Add RED tests for advanced assistant orchestration
```

---

### Task 2: Implement minimal orchestration GREEN

**Files:**
- Modify: `fantasy_draft_model/draft_assistant.py`
- Test: `tests/test_advanced_assistant_pipeline.py`

**Interfaces:**
- Produces: `build_draft_assistant(league_key, draft_context=None)`

- [ ] **Step 1: Implement the minimal production change**

Use this orchestration shape:

```python
from fantasy_draft_model.engines.pressure_meter_engine import add_pressure_meter


def build_draft_assistant(league_key, draft_context=None):
    if draft_context is None:
        draft_context = {}

    rankings = build_draft_rankings(league_key).copy()
    rankings = add_pressure_meter(rankings)
    rankings = add_draft_brain(rankings, draft_context)
    return (
        rankings
        .sort_values("brain_score", ascending=False)
        .reset_index(drop=True)
    )
```

Update `main()` to call a concrete league key, `"drunk_sundays"`.

- [ ] **Step 2: Run targeted GREEN test**

Run:

```bash
python -m pytest tests/test_advanced_assistant_pipeline.py -v
```

Expected: PASS.

- [ ] **Step 3: Commit GREEN implementation**

Commit message:

```text
Wire advanced assistant pipeline
```

---

### Task 3: Regression and live-pipeline verification

**Files:**
- No planned production changes
- Test existing assistant/ranking/CPU/league suites

**Interfaces:**
- Verifies the integrated assistant does not regress previously completed recovery items.

- [ ] **Step 1: Run assistant-focused regression tests**

Run:

```bash
python -m pytest \
  tests/test_advanced_assistant_pipeline.py \
  tests/test_cpu_mock_qb_behavior.py \
  tests/test_cpu_roster_completion.py \
  tests/test_manager_tendencies_audit.py \
  tests/test_player_metadata_audit.py \
  -v
```

Expected: all selected tests pass.

- [ ] **Step 2: Run full suite**

Run:

```bash
python -m pytest -q
```

Expected: zero failures.

- [ ] **Step 3: Run one live assistant smoke check**

Run:

```bash
python - <<'PY'
from fantasy_draft_model.draft_assistant import build_draft_assistant

board = build_draft_assistant(
    "drunk_sundays",
    draft_context={"picks_until_user": 8},
)

required = [
    "player_name_clean",
    "position",
    "team",
    "bye_week",
    "pressure_score",
    "pressure_label",
    "pressure_bar",
    "brain_score",
    "brain_recommendation",
    "brain_reasons",
    "brain_warnings",
]

print("rows", len(board))
print("missing required columns", [c for c in required if c not in board.columns])
print("brain score nulls", board["brain_score"].isna().sum())
print("pressure score nulls", board["pressure_score"].isna().sum())
print(board[required].head(10).to_string(index=False))
PY
```

Expected: non-empty board, no missing required columns, zero null pressure/brain scores.

- [ ] **Step 4: Review branch diff and integrate only after fresh verification**

Compare `advanced-assistant-features` against `EdgeIQ`; require behind count `0` and a clean fast-forward before integration.
