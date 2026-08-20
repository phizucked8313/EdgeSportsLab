# Position Tier Engine Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace descriptive tier-status scoring with numbered, position-local progressive tiers and one shared numeric live scarcity signal used consistently by Rankings, Pressure, Draft Brain, and the War Room explanation UI.

**Architecture:** Keep base tier identity stable in `tier_engine.py`, but compute live tier availability/scarcity only after drafted players and keepers are removed. Rankings will consume the numeric scarcity signal, Pressure will reuse it directly, Draft Brain will reuse it directly, and the War Room will format position-local numeric tier labels for display/explanations. The migration preserves baseline `draft_rank` while allowing live Draft Score and Brain ordering to react to the available board.

**Tech Stack:** Python 3.14, pandas, pytest, Streamlit, existing EdgeIQ engines/helpers.

**Spec:** `docs/superpowers/specs/2026-08-19-position-tier-engine-redesign.md`

## Global Constraints

- Tier numbering restarts independently for QB, RB, WR, and TE.
- Existing base thresholds remain QB=18, RB=14, WR=14, TE=12.
- Progressive multipliers are exactly 1.00x for Tier 1, 1.25x for Tier 2, 1.50x for Tier 3, and 1.75x for Tier 4 and later.
- Either projected-point drop or VORP drop may create a new tier.
- Do not manually boost RB, penalize TE, move individual players, tune to consensus ADP, or change projection formulas, VORP replacement ranks, EdgeScore weights, league scoring, or existing Draft Score/Pressure/Brain weights.
- Base tier identity remains stable during the draft; only `tier_remaining` and live `tier_scarcity_score` change.
- Drafted players and keeper-reserved players must be removed before live Draft Score, Pressure, and Draft Brain run.
- Baseline `draft_rank` remains preserved as a reference column; live War Room ordering remains `brain_score` descending.
- No production ranking decision may depend on descriptive `tier_status` once migration is complete.
- The War Room explanation must use the same tier/scarcity fields used by scoring.
- Draft completion must not crash when `picks_until_user` is `None`.
- Every production change follows RED -> GREEN -> regression verification.

---

## File Map

- `fantasy_draft_model/engines/tier_engine.py` — progressive position-local tier assignment, tier boundary metadata, live tier counts, numeric scarcity.
- `fantasy_draft_model/rankings.py` — Draft Score consumes numeric scarcity; helper for live score recomputation while preserving baseline rank.
- `fantasy_draft_model/engines/pressure_meter_engine.py` — uses numeric tier scarcity directly.
- `fantasy_draft_model/engines/draft_brain_engine.py` — uses numeric tier scarcity directly, emits numbered-tier reasons, safely handles draft completion.
- `fantasy_draft_model/draft_assistant.py` — applies live scarcity and live Draft Score before Pressure/Brain.
- `fantasy_draft_model/ui/draft_war_room.py` — availability filtering stays canonical; display/explanation tier formatting becomes numeric and position-local.
- `fantasy_draft_model/ui/streamlit_app.py` — ensures filtering happens before live scoring and displays numbered tier identity.
- `fantasy_draft_model/audit_war_room_rankings.py` — diagnostic migration from `tier_status` to numeric tier fields.
- `tests/test_progressive_position_tiers.py` — progressive tier assignment.
- `tests/test_numeric_tier_scarcity.py` — live tier remaining/scarcity math.
- `tests/test_numeric_tier_consumers.py` — Rankings/Pressure/Brain consume one numeric scarcity signal.
- `tests/test_live_available_scoring_order.py` — unavailable players removed before live scoring.
- `tests/test_war_room_numeric_tier_display.py` — numeric display/explanation behavior.
- Existing regression files — updated only where old `tier_status` assertions are obsolete.

---

### Task 1: Progressive Position-Local Tier Assignment

**Files:**
- Modify: `fantasy_draft_model/engines/tier_engine.py`
- Create: `tests/test_progressive_position_tiers.py`

**Interfaces:**
- Consumes: DataFrame with `position`, `projected_points`, and `vorp`.
- Produces: `get_tier_threshold(position: str, current_tier: int) -> float` and `assign_position_tiers(df: pd.DataFrame) -> pd.DataFrame` with `tier`, `tier_drop`, `tier_vorp_drop`, and `tier_threshold`.

- [ ] **Step 1: Write failing tests for per-position numbering and progressive thresholds**

```python
import pandas as pd

from fantasy_draft_model.engines.tier_engine import (
    assign_position_tiers,
    get_tier_threshold,
)


def test_tier_threshold_progression_uses_position_base_and_depth_multiplier():
    assert get_tier_threshold("RB", 1) == 14.0
    assert get_tier_threshold("RB", 2) == 17.5
    assert get_tier_threshold("RB", 3) == 21.0
    assert get_tier_threshold("RB", 4) == 24.5
    assert get_tier_threshold("RB", 8) == 24.5
    assert get_tier_threshold("TE", 1) == 12.0
    assert get_tier_threshold("QB", 2) == 22.5


def test_position_tiers_restart_at_one_and_use_progressive_boundary():
    df = pd.DataFrame([
        {"player_name_clean": "RB A", "position": "RB", "projected_points": 300.0, "vorp": 140.0},
        {"player_name_clean": "RB B", "position": "RB", "projected_points": 287.0, "vorp": 127.0},
        {"player_name_clean": "RB C", "position": "RB", "projected_points": 273.0, "vorp": 113.0},
        {"player_name_clean": "RB D", "position": "RB", "projected_points": 256.0, "vorp": 96.0},
        {"player_name_clean": "RB E", "position": "RB", "projected_points": 238.5, "vorp": 78.5},
        {"player_name_clean": "WR A", "position": "WR", "projected_points": 320.0, "vorp": 150.0},
        {"player_name_clean": "WR B", "position": "WR", "projected_points": 306.0, "vorp": 136.0},
    ])

    result = assign_position_tiers(df)
    tiers = dict(zip(result["player_name_clean"], result["tier"]))

    assert tiers["RB A"] == 1
    assert tiers["RB B"] == 1
    assert tiers["RB C"] == 2
    assert tiers["RB D"] == 2
    assert tiers["RB E"] == 3
    assert tiers["WR A"] == 1
    assert tiers["WR B"] == 2


def test_vorp_gap_can_create_tier_even_when_projection_gap_does_not():
    df = pd.DataFrame([
        {"player_name_clean": "TE A", "position": "TE", "projected_points": 280.0, "vorp": 120.0},
        {"player_name_clean": "TE B", "position": "TE", "projected_points": 271.0, "vorp": 107.0},
    ])
    result = assign_position_tiers(df)
    te_b = result[result["player_name_clean"] == "TE B"].iloc[0]
    assert te_b["tier"] == 2
    assert te_b["tier_drop"] == 9.0
    assert te_b["tier_vorp_drop"] == 13.0
    assert te_b["tier_threshold"] == 12.0
```

- [ ] **Step 2: Run the new tests and verify RED**

Run:

```bash
python -m pytest tests/test_progressive_position_tiers.py -v
```

Expected: failures because `get_tier_threshold`, `tier_vorp_drop`, and progressive assignment do not exist yet.

- [ ] **Step 3: Implement threshold helper and progressive assignment**

Use these exact constants/semantics:

```python
POSITION_TIER_THRESHOLDS = {"QB": 18, "RB": 14, "WR": 14, "TE": 12}
TIER_THRESHOLD_MULTIPLIERS = {1: 1.00, 2: 1.25, 3: 1.50}


def get_tier_threshold(position, current_tier):
    base = float(POSITION_TIER_THRESHOLDS.get(position, 15))
    multiplier = TIER_THRESHOLD_MULTIPLIERS.get(int(current_tier), 1.75)
    return base * multiplier
```

In `assign_position_tiers`, compute both `points_drop` and `vorp_drop`, capture the threshold used before deciding the boundary, and create a new tier when either drop is at least the threshold. Do not generate or depend on `tier_status` for scoring.

- [ ] **Step 4: Run the targeted tests and verify GREEN**

```bash
python -m pytest tests/test_progressive_position_tiers.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add fantasy_draft_model/engines/tier_engine.py tests/test_progressive_position_tiers.py
git commit -m "feat: add progressive position tiers"
```

---

### Task 2: Tier Boundary Metadata and Numeric Scarcity

**Files:**
- Modify: `fantasy_draft_model/engines/tier_engine.py`
- Create: `tests/test_numeric_tier_scarcity.py`

**Interfaces:**
- Consumes: tiered DataFrame from Task 1.
- Produces: `add_tier_boundary_metadata(df)`, `add_live_tier_scarcity(df)`, and columns `tier_size`, `tier_next_threshold`, `tier_next_projection_drop`, `tier_next_vorp_drop`, `tier_remaining`, `tier_scarcity_score`.

- [ ] **Step 1: Write failing tests for boundary metadata and scarcity**

```python
import pandas as pd

from fantasy_draft_model.engines.tier_engine import add_live_tier_scarcity


def test_late_singleton_is_capped_by_tier_depth():
    df = pd.DataFrame([
        {"player_name_clean": "RB Tier1", "position": "RB", "tier": 1, "tier_size": 1,
         "tier_next_threshold": 14.0, "tier_next_projection_drop": 14.0, "tier_next_vorp_drop": 10.0},
        {"player_name_clean": "RB Tier5", "position": "RB", "tier": 5, "tier_size": 1,
         "tier_next_threshold": 24.5, "tier_next_projection_drop": 24.5, "tier_next_vorp_drop": 20.0},
    ])
    result = add_live_tier_scarcity(df)
    scores = dict(zip(result["player_name_clean"], result["tier_scarcity_score"]))
    assert scores["RB Tier1"] == 80.0
    assert scores["RB Tier5"] == 32.0


def test_tier_remaining_uses_only_rows_still_on_available_board():
    df = pd.DataFrame([
        {"player_name_clean": "RB A", "position": "RB", "tier": 2, "tier_size": 3,
         "tier_next_threshold": 17.5, "tier_next_projection_drop": 17.5, "tier_next_vorp_drop": 0.0},
        {"player_name_clean": "RB B", "position": "RB", "tier": 2, "tier_size": 3,
         "tier_next_threshold": 17.5, "tier_next_projection_drop": 17.5, "tier_next_vorp_drop": 0.0},
    ])
    result = add_live_tier_scarcity(df.iloc[[0]].copy())
    row = result.iloc[0]
    assert row["tier_remaining"] == 1
    assert row["tier"] == 2
    assert row["tier_scarcity_score"] == 68.0


def test_drop_pressure_uses_larger_of_projection_and_vorp_signal():
    df = pd.DataFrame([
        {"player_name_clean": "TE A", "position": "TE", "tier": 2, "tier_size": 2,
         "tier_next_threshold": 15.0, "tier_next_projection_drop": 6.0, "tier_next_vorp_drop": 15.0},
        {"player_name_clean": "TE B", "position": "TE", "tier": 2, "tier_size": 2,
         "tier_next_threshold": 15.0, "tier_next_projection_drop": 6.0, "tier_next_vorp_drop": 15.0},
    ])
    result = add_live_tier_scarcity(df)
    assert set(result["tier_remaining"]) == {2}
    assert set(result["tier_scarcity_score"]) == {42.5}
```

- [ ] **Step 2: Run and verify RED**

```bash
python -m pytest tests/test_numeric_tier_scarcity.py -v
```

Expected: fail because live numeric scarcity helpers do not exist.

- [ ] **Step 3: Implement boundary metadata and live scarcity**

Use these depth factors:

```python
TIER_DEPTH_FACTORS = {1: 1.00, 2: 0.85, 3: 0.70, 4: 0.55}


def _tier_depth_factor(tier):
    return TIER_DEPTH_FACTORS.get(int(tier), 0.40)
```

For each row in `add_live_tier_scarcity`:

```python
remaining_pressure = min(100.0, 100.0 / max(1, tier_remaining))
projection_drop_pressure = clip(50.0 * tier_next_projection_drop / tier_next_threshold, 0.0, 100.0)
vorp_drop_pressure = clip(50.0 * tier_next_vorp_drop / tier_next_threshold, 0.0, 100.0)
drop_pressure = max(projection_drop_pressure, vorp_drop_pressure)
tier_scarcity_score = clip(depth_factor * (0.60 * remaining_pressure + 0.40 * drop_pressure), 0.0, 100.0)
```

Store `tier_next_threshold` from the current position/tier rather than reusing the boundary row's `tier_threshold`. A gap equal to that threshold maps to 50 drop-pressure points and a gap at least twice the threshold maps to 100. Negative and non-finite pressures map to zero. Round to two decimals. `tier_remaining` must be recomputed from the rows currently present, while `tier_size` remains base-tier size.

- [ ] **Step 4: Run and verify GREEN**

```bash
python -m pytest tests/test_numeric_tier_scarcity.py -v
```

- [ ] **Step 5: Commit**

```bash
git add fantasy_draft_model/engines/tier_engine.py tests/test_numeric_tier_scarcity.py
git commit -m "feat: add numeric live tier scarcity"
```

---

### Task 3: Rankings Consume Numeric Scarcity

**Files:**
- Modify: `fantasy_draft_model/rankings.py`
- Create: `tests/test_numeric_tier_consumers.py`

**Interfaces:**
- Consumes: DataFrame already containing `tier_scarcity_score`.
- Produces: `calculate_draft_score(df)` with no `tier_status` mapping and `recalculate_live_draft_score(df)` preserving `draft_rank`.

- [ ] **Step 1: Add RED tests for Rankings**

```python
import pandas as pd

from fantasy_draft_model.rankings import calculate_draft_score, recalculate_live_draft_score


def _row(scarcity):
    return {
        "player_name_clean": "Player A",
        "position": "RB",
        "vorp": 100.0,
        "vorp_score": 50.0,
        "edgescore": 80.0,
        "projection_score": 70.0,
        "projection_confidence": 90.0,
        "tier_scarcity_score": scarcity,
        "draft_rank": 7,
    }


def test_draft_score_consumes_existing_numeric_scarcity():
    low = calculate_draft_score(pd.DataFrame([_row(20.0)])).iloc[0]
    high = calculate_draft_score(pd.DataFrame([_row(80.0)])).iloc[0]
    assert round(high["draft_score"] - low["draft_score"], 2) == 6.0


def test_live_draft_score_recompute_preserves_baseline_rank():
    result = recalculate_live_draft_score(pd.DataFrame([_row(75.0)]))
    assert result.iloc[0]["draft_rank"] == 7
```

- [ ] **Step 2: Run and verify RED**

```bash
python -m pytest tests/test_numeric_tier_consumers.py::test_draft_score_consumes_existing_numeric_scarcity tests/test_numeric_tier_consumers.py::test_live_draft_score_recompute_preserves_baseline_rank -v
```

- [ ] **Step 3: Remove `tier_status` mapping from `calculate_draft_score`**

`calculate_draft_score` must use an existing numeric `tier_scarcity_score`, defaulting to 0 only if the column is genuinely absent. Preserve all existing weights exactly.

Implement:

```python
def recalculate_live_draft_score(df):
    result = df.copy()
    baseline_rank = result["draft_rank"].copy() if "draft_rank" in result.columns else None
    result = calculate_draft_score(result)
    if baseline_rank is not None:
        result["draft_rank"] = baseline_rank
    return result
```

- [ ] **Step 4: Run and verify GREEN**

```bash
python -m pytest tests/test_numeric_tier_consumers.py -v
```

- [ ] **Step 5: Commit**

```bash
git add fantasy_draft_model/rankings.py tests/test_numeric_tier_consumers.py
git commit -m "refactor: use numeric scarcity in draft score"
```

---

### Task 4: Pressure and Draft Brain Share the Same Numeric Scarcity Signal

**Files:**
- Modify: `fantasy_draft_model/engines/pressure_meter_engine.py`
- Modify: `fantasy_draft_model/engines/draft_brain_engine.py`
- Test: `tests/test_numeric_tier_consumers.py`

**Interfaces:**
- Consumes: `tier`, `tier_remaining`, `tier_scarcity_score`.
- Produces: `tier_pressure == tier_scarcity_score`; Brain scarcity component uses the same numeric value; numbered-tier reasons.

- [ ] **Step 1: Add RED tests for Pressure and Brain**

```python
from fantasy_draft_model.engines.draft_brain_engine import build_draft_brain_for_player
from fantasy_draft_model.engines.pressure_meter_engine import calculate_pressure_score


def test_pressure_uses_numeric_tier_scarcity_directly():
    df = pd.DataFrame([{
        "draft_rank": 1, "tier_scarcity_score": 42.0,
        "vorp": 0.0, "draft_score": 50.0,
    }])
    result = calculate_pressure_score(df)
    assert result.iloc[0]["tier_pressure"] == 42.0


def test_brain_uses_numeric_tier_scarcity_and_numbered_tier_reason():
    df = pd.DataFrame([{
        "player_name_clean": "RB A", "position": "RB", "tier": 2,
        "tier_remaining": 1, "tier_scarcity_score": 85.0,
        "pressure_score": 50.0, "draft_score": 60.0, "edgescore": 70.0,
        "vorp": 80.0, "vorp_score": 50.0, "projection_confidence": 90.0,
        "injury_risk_score": 10.0,
    }])
    report = build_draft_brain_for_player(
        df,
        df.iloc[0],
        {"picks_until_user": 3},
        wait_report={"survival_score": 50, "projection_drop": 0},
        position_run={"run_score": 0, "run_label": "NORMAL"},
    )
    assert "Last player remaining in RB Tier 2" in report["reasons"]
```

Also add:

```python
def test_brain_handles_completed_draft_context():
    # same row fixture
    report = build_draft_brain_for_player(
        df,
        df.iloc[0],
        {"picks_until_user": None},
        wait_report={"survival_score": 50, "projection_drop": 0},
        position_run={"run_score": 0, "run_label": "NORMAL"},
    )
    assert report["brain_score"] >= 0
```

- [ ] **Step 2: Run and verify RED**

```bash
python -m pytest tests/test_numeric_tier_consumers.py -v
```

Expected: old `tier_status` mappings and `int(None)` handling fail.

- [ ] **Step 3: Implement shared numeric scarcity use**

Pressure:

```python
df["tier_pressure"] = pd.to_numeric(
    df.get("tier_scarcity_score", 0.0), errors="coerce"
).fillna(0.0).clip(0, 100)
```

Draft Brain:

```python
scarcity_score = clamp(player_row.get("tier_scarcity_score", 0.0))
picks_until_raw = draft_context.get("picks_until_user", 1)
picks_until_next = 1 if picks_until_raw is None else max(1, int(picks_until_raw))
```

Reasons must derive from numeric tier identity and remaining count, not descriptive labels.

- [ ] **Step 4: Run and verify GREEN**

```bash
python -m pytest tests/test_numeric_tier_consumers.py -v
```

- [ ] **Step 5: Commit**

```bash
git add fantasy_draft_model/engines/pressure_meter_engine.py fantasy_draft_model/engines/draft_brain_engine.py tests/test_numeric_tier_consumers.py
git commit -m "refactor: unify numeric tier scarcity signals"
```

---

### Task 5: Remove Unavailable Players Before Live Scoring

**Files:**
- Modify: `fantasy_draft_model/draft_assistant.py`
- Modify: `fantasy_draft_model/ui/streamlit_app.py`
- Reuse: `fantasy_draft_model/ui/draft_war_room.py::filter_available_players`
- Create: `tests/test_live_available_scoring_order.py`

**Interfaces:**
- Consumes: base rankings + persisted War Room state.
- Produces: `build_draft_assistant_from_rankings(rankings, draft_context=None)` applied only to an already-available board; live assistant recalculates tier scarcity and Draft Score before Pressure/Brain.

- [ ] **Step 1: Write RED test proving a drafted same-tier player changes scarcity before Brain runs**

```python
import pandas as pd

from fantasy_draft_model.draft_assistant import build_draft_assistant_from_rankings
from fantasy_draft_model.ui.draft_war_room import filter_available_players


def test_unavailable_players_are_removed_before_live_tier_scarcity_and_brain():
    rankings = pd.DataFrame([
        {"player_name_clean": "RB A", "position": "RB", "tier": 2, "tier_size": 2,
         "tier_threshold": 17.5, "tier_next_threshold": 17.5, "tier_next_projection_drop": 17.5, "tier_next_vorp_drop": 0.0,
         "draft_rank": 5, "vorp": 100.0, "edgescore": 80.0, "projection_score": 80.0,
         "projection_confidence": 90.0, "injury_risk_score": 10.0},
        {"player_name_clean": "RB B", "position": "RB", "tier": 2, "tier_size": 2,
         "tier_threshold": 17.5, "tier_next_threshold": 17.5, "tier_next_projection_drop": 17.5, "tier_next_vorp_drop": 0.0,
         "draft_rank": 6, "vorp": 95.0, "edgescore": 79.0, "projection_score": 79.0,
         "projection_confidence": 90.0, "injury_risk_score": 10.0},
    ])
    state = {
        "manual_picks": [{"player_name": "RB A"}],
        "keeper_reservations": [],
    }
    available = filter_available_players(rankings, state)
    board = build_draft_assistant_from_rankings(
        available,
        draft_context={"picks_until_user": 3, "drafted_picks": state["manual_picks"]},
    )
    assert board["player_name_clean"].tolist() == ["RB B"]
    assert board.iloc[0]["tier_remaining"] == 1
```

- [ ] **Step 2: Run and verify RED**

```bash
python -m pytest tests/test_live_available_scoring_order.py -v
```

- [ ] **Step 3: Update assistant live scoring order**

Inside `build_draft_assistant_from_rankings`:

```python
live_rankings = add_live_tier_scarcity(rankings.copy())
live_rankings = recalculate_live_draft_score(live_rankings)
live_rankings = add_pressure_meter(live_rankings)
live_rankings = add_draft_brain(live_rankings, draft_context)
```

Inside `streamlit_app.build_live_view`, call the existing `filter_available_players(base_rankings, state)` before passing the board into `build_draft_assistant_from_rankings`. The final snapshot may still call filtering defensively, but no unavailable player may participate in live scoring.

- [ ] **Step 4: Run targeted tests**

```bash
python -m pytest tests/test_live_available_scoring_order.py tests/test_war_room_interaction_performance.py tests/test_war_room_performance_cache.py -v
```

Expected: all pass and no performance regression.

- [ ] **Step 5: Commit**

```bash
git add fantasy_draft_model/draft_assistant.py fantasy_draft_model/ui/streamlit_app.py tests/test_live_available_scoring_order.py
git commit -m "fix: score only available draft players"
```

---

### Task 6: Numeric Tier Display and Explanation

**Files:**
- Modify: `fantasy_draft_model/ui/draft_war_room.py`
- Modify: `fantasy_draft_model/ui/streamlit_app.py`
- Create: `tests/test_war_room_numeric_tier_display.py`

**Interfaces:**
- Produces: `format_position_tier(position, tier) -> str` and explanation fields based on `tier`, `tier_remaining`, and `tier_scarcity_score`.

- [ ] **Step 1: Write RED tests**

```python
from fantasy_draft_model.ui.draft_war_room import (
    build_available_player_display,
    build_player_ranking_explanation,
    format_position_tier,
)


def test_position_tier_label_is_numeric_and_position_local():
    assert format_position_tier("RB", 1) == "RB Tier 1"
    assert format_position_tier("TE", 3) == "TE Tier 3"


def test_available_board_replaces_old_status_with_numeric_tier_label():
    board = pd.DataFrame([{
        "draft_rank": 1, "player_name_clean": "RB A", "position": "RB", "team": "CLE",
        "position_rank_label": "RB1", "tier": 2, "tier_remaining": 1,
        "tier_scarcity_score": 85.0, "projected_points": 300.0, "vorp": 120.0,
        "edgescore": 90.0, "draft_score": 85.0, "pressure_score": 80.0,
        "brain_score": 84.0, "brain_recommendation": "DRAFT NOW", "injury_risk_score": 10.0,
    }])
    display = build_available_player_display(board)
    assert display.iloc[0]["tier_label"] == "RB Tier 2"
    assert "tier_status" not in display.columns


def test_explanation_uses_same_numeric_tier_fields_as_scoring():
    board = pd.DataFrame([{
        "draft_rank": 1, "player_name_clean": "RB A", "position": "RB", "position_rank_label": "RB1",
        "tier": 2, "tier_remaining": 1, "tier_scarcity_score": 85.0,
        "brain_score": 84.0, "brain_recommendation": "DRAFT NOW", "brain_reasons": [], "brain_warnings": [],
        "projected_points": 300.0, "vorp": 120.0, "edgescore": 90.0,
        "projection_confidence": 95.0, "injury_risk_score": 10.0,
    }])
    explanation = build_player_ranking_explanation(board, "RB A")
    assert explanation["tier_label"] == "RB Tier 2"
    assert explanation["tier_remaining"] == 1
    assert explanation["tier_scarcity_score"] == 85.0
```

- [ ] **Step 2: Run and verify RED**

```bash
python -m pytest tests/test_war_room_numeric_tier_display.py -v
```

- [ ] **Step 3: Implement display-only numeric tier label**

Add:

```python
def format_position_tier(position, tier):
    return f"{str(position).strip().upper()} Tier {int(tier)}"
```

Add `tier_label` only to display/explanation output; keep integer `tier` as canonical model data. Update the Streamlit explanation text to show tier label, remaining count, and scarcity score without referring to old descriptive tier statuses.

- [ ] **Step 4: Run and verify GREEN**

```bash
python -m pytest tests/test_war_room_numeric_tier_display.py tests/test_war_room_ranking_explanations.py tests/test_war_room_static_available_board.py -v
```

- [ ] **Step 5: Commit**

```bash
git add fantasy_draft_model/ui/draft_war_room.py fantasy_draft_model/ui/streamlit_app.py tests/test_war_room_numeric_tier_display.py
git commit -m "feat: show numbered position tiers in war room"
```

---

### Task 7: Migrate Diagnostics and Remove `tier_status` From Production Scoring

**Files:**
- Modify: `fantasy_draft_model/audit_war_room_rankings.py`
- Modify: `fantasy_draft_model/draft_assistant.py`
- Modify: `fantasy_draft_model/engines/tier_engine.py`
- Modify obsolete tier-status tests identified by `grep -R "tier_status" tests fantasy_draft_model -n`

**Interfaces:**
- No production scoring consumer may read `tier_status`.
- Diagnostics display `tier`, `tier_remaining`, `tier_scarcity_score`, `tier_next_projection_drop`, and `tier_next_vorp_drop`.

- [ ] **Step 1: Find every remaining dependency**

Run:

```bash
grep -R "tier_status" fantasy_draft_model tests -n
```

Classify each result as scoring, diagnostic, compatibility test, or dead display code. The completion condition for this task is zero production scoring references.

- [ ] **Step 2: Add or update RED assertions that old labels are absent from ranking decisions**

Update the current tier consistency/diagnostic tests so they assert numeric scarcity behavior instead of old labels. Do not delete coverage; migrate it.

- [ ] **Step 3: Remove the old descriptive scoring path**

`calculate_tiers` should no longer require `add_tier_status` for production scoring. If a temporary compatibility column remains during this task, it must be display/diagnostic-only and removed by task completion.

- [ ] **Step 4: Run migrated targeted suites**

```bash
python -m pytest \
  tests/test_progressive_position_tiers.py \
  tests/test_numeric_tier_scarcity.py \
  tests/test_numeric_tier_consumers.py \
  tests/test_live_available_scoring_order.py \
  tests/test_war_room_numeric_tier_display.py \
  tests/test_tier_signal_consistency.py \
  tests/test_draft_order_and_te_audit.py \
  tests/test_rb_te_value_audit.py \
  tests/test_projection_and_singleton_tier_audit.py \
  -v
```

Expected: 0 failed.

- [ ] **Step 5: Commit**

```bash
git add fantasy_draft_model tests
git commit -m "refactor: retire descriptive tier status scoring"
```

---

### Task 8: Regression, Performance, and Draft-Night Verification

**Files:**
- No new production behavior unless a regression reveals a defect.
- Update tests only when an assertion is obsolete because of the approved tier redesign.

**Interfaces:**
- Produces: verified draft-night tier system with no regression in keepers, manual picks, undo, explanations, performance, or live safety.

- [ ] **Step 1: Run the full War Room regression set**

```bash
python -m pytest \
  tests/test_live_war_room_core.py \
  tests/test_war_room_ui_helpers.py \
  tests/test_streamlit_war_room_shell.py \
  tests/test_streamlit_war_room_startup.py \
  tests/test_war_room_draft_night_display.py \
  tests/test_war_room_performance_cache.py \
  tests/test_war_room_interaction_performance.py \
  tests/test_war_room_keeper_metadata.py \
  tests/test_war_room_static_available_board.py \
  tests/test_tier_signal_consistency.py \
  tests/test_war_room_ranking_explanations.py \
  tests/test_live_ui_core_safety.py \
  tests/test_draft_order_and_te_audit.py \
  tests/test_rb_te_value_audit.py \
  tests/test_projection_and_singleton_tier_audit.py \
  tests/test_progressive_position_tiers.py \
  tests/test_numeric_tier_scarcity.py \
  tests/test_numeric_tier_consumers.py \
  tests/test_live_available_scoring_order.py \
  tests/test_war_room_numeric_tier_display.py \
  -q
```

Expected: 0 failed.

- [ ] **Step 2: Run the complete repository suite**

```bash
python -m pytest -q
```

Expected: 0 failed.

- [ ] **Step 3: Run ranking audit and inspect key players**

```bash
python -m fantasy_draft_model.audit_war_room_rankings
```

Verify that McBride/top RBs are explained by projection/VORP/tier depth rather than old singleton labels, and that later singleton tiers no longer receive 100 scarcity solely because they contain one player.

- [ ] **Step 4: Launch Streamlit and verify draft-night behavior**

```bash
python -m streamlit run fantasy_draft_model/ui/streamlit_app.py
```

Verify:

- Available board shows `RB Tier N`, `WR Tier N`, `TE Tier N`, `QB Tier N`.
- Drafting/removing a player changes `tier_remaining` and live urgency but not base tier number.
- Draft Player and Explain Player interactions remain fast.
- Explanation reasons reference numbered position tiers.
- Draft completion does not crash.

- [ ] **Step 5: Commit any verification-only test migrations, if required**

```bash
git add tests fantasy_draft_model
git commit -m "test: verify numbered live tier system"
```

Do not create an empty commit if no files changed.

---

## Plan Self-Review

- Spec coverage: progressive thresholds, per-position numbering, either projection/VORP boundary trigger, stable base tiers, live tier remaining, numeric scarcity, Rankings/Pressure/Brain reuse, availability-before-scoring, numeric UI/explanation, migration, draft-completion safety, regression/performance coverage are all assigned to tasks.
- Placeholder scan: no TBD/TODO/"implement later" instructions remain.
- Type/name consistency: `get_tier_threshold`, `add_live_tier_scarcity`, `tier_next_threshold`, `tier_remaining`, `tier_scarcity_score`, `recalculate_live_draft_score`, `format_position_tier`, and the next-drop column names are consistent across tasks.
- Scope: one coherent subsystem redesign; no unrelated projection, VORP, EdgeScore, keeper, or league-scoring work is included.
