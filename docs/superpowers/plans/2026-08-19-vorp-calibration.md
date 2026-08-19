# EdgeIQ VORP Calibration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make EdgeIQ VORP replacement levels derive from the configured league lineup and dynamically allocate RB/WR FLEX demand using projected points.

**Architecture:** `vorp_engine.py` will own replacement-rank calculation. A pure helper will accept a projection DataFrame plus optional league settings, derive mandatory starter demand, allocate FLEX slots to the best remaining RB/WR candidates, and return QB/RB/WR/TE replacement ranks. `calculate_vorp()` will consume those ranks without changing its existing replacement-points/VORP mechanics.

**Tech Stack:** Python 3.14, pandas, pytest, existing EdgeIQ config loader.

**Spec:** `docs/superpowers/specs/2026-08-19-vorp-calibration-design.md`

## Global Constraints

- Use `fantasy_draft_model/config/league_settings.json` as the authoritative league structure.
- FLEX eligibility in this task is RB/WR only.
- Do not manually force an RB/WR FLEX split.
- Do not change projections, #4 QB scoring, keepers, ADP, or manager behavior.
- Preserve current VORP fallback behavior when a position has fewer players than the derived replacement rank.
- TDD red-green cycle for every production behavior change.

---

### Task 1: Dynamic Replacement-Rank Helper

**Files:**
- Modify: `fantasy_draft_model/engines/vorp_engine.py`
- Create: `tests/test_vorp_calibration.py`

**Interfaces:**
- Consumes: projection DataFrame with `position` and `projected_points`; league settings dict containing `teams` and `lineup`.
- Produces: `calculate_replacement_ranks(df, league_settings=None) -> dict[str, int]`.

- [ ] **Step 1: Write the failing test**

```python
import pandas as pd

from fantasy_draft_model.engines import vorp_engine


def test_replacement_ranks_allocate_flex_to_best_remaining_rb_wr():
    df = pd.DataFrame(
        {
            "player_name_clean": [
                "QB1", "QB2",
                "RB1", "RB2", "RB3", "RB4",
                "WR1", "WR2", "WR3", "WR4",
                "TE1", "TE2",
            ],
            "position": [
                "QB", "QB",
                "RB", "RB", "RB", "RB",
                "WR", "WR", "WR", "WR",
                "TE", "TE",
            ],
            "projected_points": [
                300, 290,
                250, 240, 230, 180,
                245, 235, 220, 210,
                190, 180,
            ],
        }
    )

    settings = {
        "teams": 2,
        "lineup": {
            "QB": 1,
            "RB": 1,
            "WR": 1,
            "TE": 1,
            "FLEX": 1,
        },
    }

    helper = getattr(vorp_engine, "calculate_replacement_ranks", None)
    assert helper is not None, "calculate_replacement_ranks helper is not implemented yet"

    result = helper(df, settings)

    # Mandatory: QB2/RB2/WR2/TE2. Two FLEX slots go to RB3 (230)
    # and WR3 (220), so final ranks are RB3 and WR3.
    assert result == {
        "QB": 2,
        "RB": 3,
        "WR": 3,
        "TE": 2,
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest tests/test_vorp_calibration.py::test_replacement_ranks_allocate_flex_to_best_remaining_rb_wr -v
```

Expected: FAIL because `calculate_replacement_ranks` does not exist.

- [ ] **Step 3: Write minimal implementation**

In `vorp_engine.py`:

```python
from fantasy_draft_model.config import load_league_settings

FLEX_ELIGIBLE_POSITIONS = ("RB", "WR")
VORP_POSITIONS = ("QB", "RB", "WR", "TE")


def calculate_replacement_ranks(df, league_settings=None):
    settings = league_settings or load_league_settings()
    teams = int(settings["teams"])
    lineup = settings["lineup"]

    replacement_ranks = {
        position: teams * int(lineup.get(position, 0))
        for position in VORP_POSITIONS
    }

    flex_slots = teams * int(lineup.get("FLEX", 0))
    flex_candidates = []

    for position in FLEX_ELIGIBLE_POSITIONS:
        mandatory = replacement_ranks[position]
        players = (
            df[df["position"] == position]
            .sort_values("projected_points", ascending=False)
            .copy()
        )
        flex_candidates.append(players.iloc[mandatory:])

    if flex_slots > 0 and flex_candidates:
        candidate_pool = pd.concat(flex_candidates, ignore_index=True)
        selected = (
            candidate_pool
            .sort_values("projected_points", ascending=False)
            .head(flex_slots)
        )

        for position in FLEX_ELIGIBLE_POSITIONS:
            replacement_ranks[position] += int(
                (selected["position"] == position).sum()
            )

    return replacement_ranks
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
python -m pytest tests/test_vorp_calibration.py::test_replacement_ranks_allocate_flex_to_best_remaining_rb_wr -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_vorp_calibration.py fantasy_draft_model/engines/vorp_engine.py
git commit -m "feat: derive VORP replacement ranks from lineup demand"
```

---

### Task 2: Prove Settings Drive Replacement Demand

**Files:**
- Modify: `tests/test_vorp_calibration.py`

**Interfaces:**
- Consumes: `calculate_replacement_ranks(df, league_settings)` from Task 1.
- Produces: regression coverage that changing teams/lineup changes replacement ranks without changing code constants.

- [ ] **Step 1: Write the failing/behavior test**

```python
def test_replacement_ranks_change_with_league_lineup():
    df = pd.DataFrame(
        {
            "position": ["QB"] * 6 + ["RB"] * 8 + ["WR"] * 8 + ["TE"] * 6,
            "projected_points": list(range(300, 272, -1)),
        }
    )

    small = {
        "teams": 2,
        "lineup": {"QB": 1, "RB": 1, "WR": 1, "TE": 1, "FLEX": 0},
    }
    larger = {
        "teams": 3,
        "lineup": {"QB": 1, "RB": 1, "WR": 1, "TE": 1, "FLEX": 0},
    }

    assert vorp_engine.calculate_replacement_ranks(df, small) == {
        "QB": 2, "RB": 2, "WR": 2, "TE": 2
    }
    assert vorp_engine.calculate_replacement_ranks(df, larger) == {
        "QB": 3, "RB": 3, "WR": 3, "TE": 3
    }
```

- [ ] **Step 2: Run the test**

Run:

```bash
python -m pytest tests/test_vorp_calibration.py::test_replacement_ranks_change_with_league_lineup -v
```

Expected: PASS if Task 1 is correct. If it fails, fix only the settings-derived rank logic.

- [ ] **Step 3: Commit regression coverage**

```bash
git add tests/test_vorp_calibration.py
git commit -m "test: verify VORP demand follows league settings"
```

---

### Task 3: Wire Dynamic Ranks Into VORP

**Files:**
- Modify: `fantasy_draft_model/engines/vorp_engine.py`
- Modify: `tests/test_vorp_calibration.py`

**Interfaces:**
- Consumes: `calculate_replacement_ranks(df, league_settings=None)`.
- Produces: `calculate_vorp(df, league_settings=None)` using dynamic ranks.

- [ ] **Step 1: Write the failing integration test**

```python
def test_calculate_vorp_uses_dynamic_flex_replacement_ranks():
    df = pd.DataFrame(
        {
            "player_name_clean": [
                "RB1", "RB2", "RB3", "RB4",
                "WR1", "WR2", "WR3", "WR4",
                "QB1", "QB2",
                "TE1", "TE2",
            ],
            "position": [
                "RB", "RB", "RB", "RB",
                "WR", "WR", "WR", "WR",
                "QB", "QB",
                "TE", "TE",
            ],
            "projected_points": [
                250, 240, 230, 180,
                245, 235, 220, 210,
                300, 290,
                190, 180,
            ],
        }
    )

    settings = {
        "teams": 2,
        "lineup": {"QB": 1, "RB": 1, "WR": 1, "TE": 1, "FLEX": 1},
    }

    result = vorp_engine.calculate_vorp(df, settings)

    rb3 = result[result["player_name_clean"] == "RB3"].iloc[0]
    wr3 = result[result["player_name_clean"] == "WR3"].iloc[0]

    assert rb3["position_rank"] == 3
    assert rb3["replacement_points"] == 230
    assert rb3["vorp"] == 0

    assert wr3["position_rank"] == 3
    assert wr3["replacement_points"] == 220
    assert wr3["vorp"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest tests/test_vorp_calibration.py::test_calculate_vorp_uses_dynamic_flex_replacement_ranks -v
```

Expected: FAIL because current `calculate_vorp()` still uses hardcoded `REPLACEMENT_RANKS` and does not accept settings.

- [ ] **Step 3: Implement dynamic VORP wiring**

Change the signature and loop in `vorp_engine.py`:

```python
def calculate_vorp(df: pd.DataFrame, league_settings=None):
    df = df.copy()
    replacement_ranks = calculate_replacement_ranks(df, league_settings)

    df["position_rank"] = 0
    df["vorp"] = 0.0
    df["replacement_points"] = 0.0

    for position, replacement_rank in replacement_ranks.items():
        ...
```

Keep the existing replacement-point lookup, fallback, position-rank assignment, VORP subtraction, and `overall_rank` behavior unchanged.

Remove the hardcoded `REPLACEMENT_RANKS` constant after the integration test is green.

- [ ] **Step 4: Run focused tests**

Run:

```bash
python -m pytest tests/test_vorp_calibration.py tests/test_qb_1qb_economics.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_vorp_calibration.py fantasy_draft_model/engines/vorp_engine.py
git commit -m "feat: apply flex-aware replacement ranks to VORP"
```

---

### Task 4: Live 2026 Calibration Verification

**Files:**
- No production file changes expected.

**Interfaces:**
- Consumes: live `build_2026_projections()` output and dynamic VORP engine.
- Produces: verification evidence for the actual 2026 draft pool.

- [ ] **Step 1: Run focused regression suite**

```bash
python -m pytest tests/test_vorp_calibration.py tests/test_qb_1qb_economics.py tests/test_rookie_player_pool.py tests/test_rookie_projection_model.py tests/test_current_injury_normalizer.py tests/test_current_injury_pipeline.py -v
```

Expected: all focused tests PASS.

- [ ] **Step 2: Run live replacement diagnostic**

```bash
python -c "from fantasy_draft_model.engines.projection_engine import build_2026_projections; from fantasy_draft_model.engines.vorp_engine import calculate_replacement_ranks; d=build_2026_projections(); ranks=calculate_replacement_ranks(d); print('REPLACEMENT RANKS =',ranks); print(); cols=['player_name_clean','position','position_rank','projected_points','replacement_points','vorp']; x=d[d['position'].isin(['QB','RB','WR','TE'])]; print(x.sort_values(['position','position_rank'])[cols].groupby('position').apply(lambda g: g[g['position_rank'].isin([ranks[g.name]-1,ranks[g.name],ranks[g.name]+1])]).to_string(index=False))"
```

Expected:
- QB remains 12 for the current 12-team, 1-QB configuration.
- TE remains 12 for the current 12-team, 1-TE configuration.
- RB + WR replacement-rank increases above 24 sum to exactly 24 FLEX allocations, subject only to insufficient available candidate rows.
- The player at each derived replacement rank has VORP 0.

- [ ] **Step 3: Run full suite**

```bash
python -m pytest -q
```

Expected: all tests PASS.

- [ ] **Step 4: Compare live ranking economics**

Run a ranking diagnostic after VORP calibration and record QB/RB/WR/TE counts in Top 25/50/100. Do not manually tune the ranks based on the result; use the output only to verify no obvious regression occurred.

- [ ] **Step 5: Finish branch**

If live verification and full tests are green, fast-forward `EdgeIQ` to `vorp-calibration`, then create the next recovery branch for #6 league scoring audit.
