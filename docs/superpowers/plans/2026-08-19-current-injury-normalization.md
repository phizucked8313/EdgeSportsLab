# Current Injury Normalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Sleeper the working 2026 current-injury source, normalize its fields into a stable EdgeIQ schema, flag unresolved injuries for research, and feed those records through the existing team injury ripple and projection pipeline.

**Architecture:** Keep `sleeper_api.py` responsible only for downloading/filtering Sleeper player data. Add `current_injury_normalizer.py` as the vendor-to-EdgeIQ boundary. Update `projection_engine.py` to consume the normalized loader while leaving historical injury risk separate.

**Tech Stack:** Python 3.14, pandas, requests, pytest, existing EdgeIQ engines.

**Spec:** `docs/superpowers/specs/2026-08-19-current-injury-normalization-design.md`

## Global Constraints

- Do not guess undisclosed diagnoses.
- Preserve Sleeper's original injury body-part value separately from EdgeIQ's normalized/enriched value.
- Specific Sleeper injury data starts at quality grade `D`; unresolved/non-specific injury data starts at `F`.
- Current 2026 injuries must not call `nflreadpy.load_injuries(seasons=[2026])`.
- Do not recalibrate Version 1 injury-impact/ripple weights in this change.
- Historical injury risk remains separate from current injury status.
- First enrichment/research scope is Top 300 + keepers + meaningful handcuffs/backups + injuries materially affecting that group.

---

## File Structure

- Create `fantasy_draft_model/integrations/current_injury_normalizer.py` — normalize Sleeper current injury records into the stable EdgeIQ schema.
- Modify `fantasy_draft_model/engines/projection_engine.py` — import normalized current injuries instead of the broken historical loader path.
- Modify `fantasy_draft_model/models/team_injury_impact_engine.py` — make depth-chart role resolution safe when a caller supplies a role column and recognize IR/PUP/DNR current statuses conservatively.
- Create `tests/test_current_injury_normalizer.py` — unit tests for field mapping, quality grades, unresolved injuries, and healthy-player filtering.
- Create `tests/test_current_injury_pipeline.py` — integration tests for normalized injury -> team impact -> ripple.

---

### Task 1: Normalize Sleeper Current Injuries

**Files:**
- Create: `fantasy_draft_model/integrations/current_injury_normalizer.py`
- Create: `tests/test_current_injury_normalizer.py`

**Interfaces:**
- Consumes: `load_sleeper_players() -> pandas.DataFrame` from `fantasy_draft_model.integrations.sleeper_api`.
- Produces: `normalize_current_injuries(players_df: pandas.DataFrame) -> pandas.DataFrame` and `load_normalized_current_injuries() -> pandas.DataFrame`.

- [ ] **Step 1: Write failing normalization tests**

```python
import pandas as pd

from fantasy_draft_model.integrations.current_injury_normalizer import (
    normalize_current_injuries,
)


def sample_players():
    return pd.DataFrame([
        {
            "sleeper_id": "1",
            "espn_id": 101,
            "yahoo_id": 201,
            "player_name": "IR Player",
            "team": "AAA",
            "position": "RB",
            "status": "Inactive",
            "injury_status": "IR",
            "injury_body_part": "Knee - ACL",
            "injury_start_date": "2026-08-01",
            "practice_participation": None,
        },
        {
            "sleeper_id": "2",
            "espn_id": 102,
            "yahoo_id": 202,
            "player_name": "Questionable Player",
            "team": "BBB",
            "position": "WR",
            "status": "Active",
            "injury_status": "Questionable",
            "injury_body_part": "Hamstring",
            "injury_start_date": None,
            "practice_participation": "Limited Participation in Practice",
        },
        {
            "sleeper_id": "3",
            "espn_id": 103,
            "yahoo_id": 203,
            "player_name": "Mystery Player",
            "team": "CCC",
            "position": "WR",
            "status": "Active",
            "injury_status": "Questionable",
            "injury_body_part": "Undisclosed",
            "injury_start_date": None,
            "practice_participation": None,
        },
        {
            "sleeper_id": "4",
            "espn_id": 104,
            "yahoo_id": 204,
            "player_name": "Healthy Player",
            "team": "DDD",
            "position": "TE",
            "status": "Active",
            "injury_status": None,
            "injury_body_part": None,
            "injury_start_date": None,
            "practice_participation": None,
        },
    ])


def test_normalizer_maps_current_statuses_and_filters_healthy_players():
    result = normalize_current_injuries(sample_players())

    assert set(result["player_name"]) == {
        "IR Player",
        "Questionable Player",
        "Mystery Player",
    }
    assert result.set_index("player_name").loc["IR Player", "report_status"] == "IR"
    assert result.set_index("player_name").loc["Questionable Player", "report_status"] == "Questionable"


def test_undisclosed_is_flagged_for_research():
    result = normalize_current_injuries(sample_players()).set_index("player_name")

    assert bool(result.loc["Mystery Player", "needs_research"]) is True
    assert result.loc["Mystery Player", "injury_data_quality"] == "F"
    assert result.loc["Mystery Player", "source_injury_body_part"] == "Undisclosed"


def test_specific_sleeper_injury_starts_at_quality_d():
    result = normalize_current_injuries(sample_players()).set_index("player_name")

    assert bool(result.loc["IR Player", "needs_research"]) is False
    assert result.loc["IR Player", "injury_data_quality"] == "D"
    assert result.loc["IR Player", "edgeiq_injury_body_part"] == "Knee - ACL"
```

- [ ] **Step 2: Run tests and verify they fail because the normalizer does not exist**

Run:

```bash
python -m pytest tests/test_current_injury_normalizer.py -v
```

Expected: collection/import failure for `current_injury_normalizer`.

- [ ] **Step 3: Implement the minimal normalizer**

Create `fantasy_draft_model/integrations/current_injury_normalizer.py`:

```python
from datetime import datetime, timezone

import pandas as pd

from fantasy_draft_model.integrations.sleeper_api import load_sleeper_players


NON_SPECIFIC_BODY_PARTS = {
    "",
    "nan",
    "none",
    "unknown",
    "undisclosed",
    "lower body",
    "upper body",
}


def _clean(value):
    if pd.isna(value):
        return ""
    return str(value).strip()


def _is_non_specific_body_part(value):
    return _clean(value).lower() in NON_SPECIFIC_BODY_PARTS


def normalize_current_injuries(players_df):
    df = players_df.copy()

    required = [
        "sleeper_id", "espn_id", "yahoo_id", "player_name",
        "team", "position", "status", "injury_status",
        "injury_body_part", "injury_start_date",
        "practice_participation",
    ]
    for column in required:
        if column not in df.columns:
            df[column] = None

    injury_mask = (
        df["injury_status"].notna()
        | df["injury_body_part"].notna()
        | df["practice_participation"].notna()
        | df["injury_start_date"].notna()
    )
    df = df.loc[injury_mask].copy().reset_index(drop=True)

    df["report_status"] = df["injury_status"].apply(_clean)
    df["practice_status"] = df["practice_participation"].apply(_clean)
    df["source_injury_body_part"] = df["injury_body_part"].apply(_clean)
    df["edgeiq_injury_body_part"] = df["source_injury_body_part"]

    df["needs_research"] = df["source_injury_body_part"].apply(
        _is_non_specific_body_part
    )
    df["injury_data_quality"] = df["needs_research"].map(
        {True: "F", False: "D"}
    )
    df["injury_source"] = "Sleeper"
    df["injury_source_timestamp"] = datetime.now(timezone.utc).isoformat()

    return df[
        [
            "sleeper_id", "espn_id", "yahoo_id", "player_name",
            "team", "position", "status", "report_status",
            "practice_status", "source_injury_body_part",
            "edgeiq_injury_body_part", "injury_start_date",
            "needs_research", "injury_data_quality",
            "injury_source", "injury_source_timestamp",
        ]
    ]


def load_normalized_current_injuries():
    return normalize_current_injuries(load_sleeper_players())
```

- [ ] **Step 4: Run normalization tests**

Run:

```bash
python -m pytest tests/test_current_injury_normalizer.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add fantasy_draft_model/integrations/current_injury_normalizer.py tests/test_current_injury_normalizer.py
git commit -m "Add normalized Sleeper current injury feed"
```

---

### Task 2: Make Team Injury Impact Compatible with Normalized Current Statuses

**Files:**
- Modify: `fantasy_draft_model/models/team_injury_impact_engine.py`
- Create: `tests/test_current_injury_pipeline.py`

**Interfaces:**
- Consumes: normalized dataframe from `normalize_current_injuries()`.
- Produces: dataframe containing `edgeiq_role`, `injury_unit`, and `player_injury_impact`, suitable for `build_team_offensive_ripple()`.

- [ ] **Step 1: Write failing status and role tests**

```python
import pandas as pd

from fantasy_draft_model.models.team_injury_impact_engine import (
    add_team_injury_impact,
    get_status_multiplier,
)


def test_ir_and_pup_are_not_treated_as_generic_unknown_statuses():
    assert get_status_multiplier("IR") == 1.00
    assert get_status_multiplier("PUP") == 1.00
    assert get_status_multiplier("DNR") == 1.00


def test_supplied_role_column_does_not_require_depth_chart_lookup():
    injuries = pd.DataFrame([
        {
            "team": "AAA",
            "position": "WR",
            "report_status": "Questionable",
            "practice_status": "",
            "test_role": "STARTER",
        }
    ])

    result = add_team_injury_impact(injuries, role_column="test_role")

    assert result.loc[0, "edgeiq_role"] == "STARTER"
    assert result.loc[0, "injury_unit"] == "PASS_CATCHERS"
    assert result.loc[0, "player_injury_impact"] > 0
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
python -m pytest tests/test_current_injury_pipeline.py -v
```

Expected: IR/PUP/DNR currently return the generic fallback multiplier; supplied-role path may reference `depth_df` before assignment.

- [ ] **Step 3: Apply minimal compatibility fix**

In `STATUS_MULTIPLIER`, add:

```python
    "IR": 1.00,
    "PUP": 1.00,
    "DNR": 1.00,
```

Then structure role resolution so the supplied role path exits depth-chart lookup cleanly:

```python
    if role_column and role_column in df.columns:
        df["edgeiq_role"] = (
            df[role_column]
            .fillna("UNKNOWN")
            .astype(str)
            .str.upper()
        )
    else:
        depth_df = load_depth_charts()

        if "gsis_id" in df.columns and "gsis_id" in depth_df.columns:
            role_lookup = (
                depth_df[["gsis_id", "edgeiq_role"]]
                .dropna(subset=["gsis_id"])
                .drop_duplicates(subset=["gsis_id"])
                .set_index("gsis_id")["edgeiq_role"]
                .to_dict()
            )
            df["edgeiq_role"] = (
                df["gsis_id"]
                .map(role_lookup)
                .fillna("UNKNOWN")
            )
        else:
            df["edgeiq_role"] = "UNKNOWN"
```

- [ ] **Step 4: Run tests**

Run:

```bash
python -m pytest tests/test_current_injury_pipeline.py -v
```

Expected: 2 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add fantasy_draft_model/models/team_injury_impact_engine.py tests/test_current_injury_pipeline.py
git commit -m "Support normalized current injury statuses"
```

---

### Task 3: Verify Normalized Injury -> Ripple Flow

**Files:**
- Modify: `tests/test_current_injury_pipeline.py`

**Interfaces:**
- Consumes: `normalize_current_injuries()`, `add_team_injury_impact()`, `build_team_offensive_ripple()`, `add_fantasy_ripple_scores()`, `add_projection_multipliers()`.
- Produces: regression coverage proving the normalized schema reaches projection multipliers without schema errors.

- [ ] **Step 1: Add the failing end-to-end engine test**

Append:

```python
from fantasy_draft_model.integrations.current_injury_normalizer import (
    normalize_current_injuries,
)
from fantasy_draft_model.engines.injury_ripple_engine import (
    build_team_offensive_ripple,
    add_fantasy_ripple_scores,
    add_projection_multipliers,
)


def test_normalized_current_injury_flows_into_ripple_multiplier():
    sleeper_rows = pd.DataFrame([
        {
            "sleeper_id": "10",
            "player_name": "Starting WR",
            "team": "AAA",
            "position": "WR",
            "status": "Active",
            "injury_status": "Out",
            "injury_body_part": "Hamstring",
            "practice_participation": "Did Not Participate in Practice",
            "injury_start_date": "2026-08-18",
        }
    ])

    normalized = normalize_current_injuries(sleeper_rows)
    normalized["test_role"] = "STARTER"
    impacted = add_team_injury_impact(normalized, role_column="test_role")
    ripple = build_team_offensive_ripple(impacted)
    ripple = add_fantasy_ripple_scores(ripple)
    ripple = add_projection_multipliers(ripple)

    assert ripple.loc[0, "team"] == "AAA"
    assert ripple.loc[0, "pass_catcher_injury_impact"] > 0
    assert ripple.loc[0, "wr_ripple_multiplier"] > 1.0
```

- [ ] **Step 2: Run the integration test**

Run:

```bash
python -m pytest tests/test_current_injury_pipeline.py::test_normalized_current_injury_flows_into_ripple_multiplier -v
```

Expected: PASS after Tasks 1-2; if it fails, the failure identifies the exact schema boundary to repair before projection integration.

- [ ] **Step 3: Run both injury test modules together**

Run:

```bash
python -m pytest tests/test_current_injury_normalizer.py tests/test_current_injury_pipeline.py -v
```

Expected: all tests PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/test_current_injury_pipeline.py
git commit -m "Test current injury ripple pipeline"
```

---

### Task 4: Switch Projection Engine to Normalized Sleeper Current Injuries

**Files:**
- Modify: `fantasy_draft_model/engines/projection_engine.py`
- Modify: `tests/test_current_injury_pipeline.py`

**Interfaces:**
- Consumes: `load_normalized_current_injuries() -> pandas.DataFrame`.
- Produces: the existing `build_2026_projections()` output, with current injury ripple sourced from Sleeper normalization rather than `injury_history_loader.load_current_injuries()`.

- [ ] **Step 1: Add a source-regression test**

```python
from pathlib import Path


def test_projection_engine_uses_normalized_current_injury_loader():
    source = Path(
        "fantasy_draft_model/engines/projection_engine.py"
    ).read_text(encoding="utf-8")

    assert "current_injury_normalizer" in source
    assert "load_normalized_current_injuries" in source
    assert "integrations.injury_history_loader" not in source
```

- [ ] **Step 2: Run the regression test and verify it fails**

Run:

```bash
python -m pytest tests/test_current_injury_pipeline.py::test_projection_engine_uses_normalized_current_injury_loader -v
```

Expected: FAIL because `projection_engine.py` still imports `injury_history_loader.load_current_injuries`.

- [ ] **Step 3: Change the projection import and call**

Replace:

```python
from fantasy_draft_model.integrations.injury_history_loader import (
    load_current_injuries,
)
```

with:

```python
from fantasy_draft_model.integrations.current_injury_normalizer import (
    load_normalized_current_injuries,
)
```

Replace:

```python
current_injuries = load_current_injuries()
```

with:

```python
current_injuries = load_normalized_current_injuries()
```

Do not change historical `add_injury_scores()` logic in this task.

- [ ] **Step 4: Run the regression and injury pipeline tests**

Run:

```bash
python -m pytest tests/test_current_injury_normalizer.py tests/test_current_injury_pipeline.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Run the current injury loader manually**

Run:

```bash
python -c "from fantasy_draft_model.integrations.current_injury_normalizer import load_normalized_current_injuries; d=load_normalized_current_injuries(); print(d[['player_name','team','position','report_status','edgeiq_injury_body_part','needs_research','injury_data_quality']].head(30).to_string(index=False)); print('injuries=',len(d),'research_queue=',int(d['needs_research'].sum()))"
```

Expected: current Sleeper injury rows print successfully; no `Season must be between 2009 and 2025` exception.

- [ ] **Step 6: Commit**

```bash
git add fantasy_draft_model/engines/projection_engine.py tests/test_current_injury_pipeline.py
git commit -m "Use normalized Sleeper injuries in projections"
```

---

### Task 5: Full Verification and Research Queue Smoke Test

**Files:**
- No production-file changes expected unless verification exposes a concrete defect.

**Interfaces:**
- Consumes: completed current injury pipeline.
- Produces: verified current-injury foundation ready for the separate diagnosis-enrichment pass.

- [ ] **Step 1: Compile changed production modules**

Run:

```bash
python -m py_compile fantasy_draft_model/integrations/current_injury_normalizer.py fantasy_draft_model/models/team_injury_impact_engine.py fantasy_draft_model/engines/injury_ripple_engine.py fantasy_draft_model/engines/projection_engine.py
```

Expected: command exits with no traceback.

- [ ] **Step 2: Run all injury tests**

Run:

```bash
python -m pytest tests/test_current_injury_normalizer.py tests/test_current_injury_pipeline.py -v
```

Expected: all tests PASS.

- [ ] **Step 3: Print unresolved injury research queue**

Run:

```bash
python -c "from fantasy_draft_model.integrations.current_injury_normalizer import load_normalized_current_injuries; d=load_normalized_current_injuries(); q=d[d['needs_research']]; print(q[['player_name','team','position','report_status','source_injury_body_part']].to_string(index=False)); print('needs_research=',len(q))"
```

Expected: unresolved/undisclosed records are visible and explicitly flagged rather than silently treated as healthy.

- [ ] **Step 4: Confirm Git state**

Run:

```bash
git status --short
```

Expected: only intentional uncommitted runtime/cache artifacts, if any. Production/test changes from this plan are committed.

- [ ] **Step 5: Push EdgeIQ branch**

Run:

```bash
git push origin EdgeIQ
```

Expected: remote EdgeIQ advances to the completed injury-pipeline commits.

---

## Self-Review

- Spec coverage: Sleeper sourcing, normalized schema, undisclosed handling, data-quality grades, current-vs-historical separation, downstream team/ripple integration, and projection import replacement are all assigned to tasks.
- Scope: X/ESPN diagnosis enrichment remains intentionally separate; this plan creates the `needs_research` queue that enrichment will consume.
- Type consistency: all pipeline stages use pandas DataFrames; normalized field names are consistent across Tasks 1-5.
- Safety against false healthy data: unresolved injuries are retained and flagged `F`; network errors remain raised by `requests.raise_for_status()` rather than converted into empty healthy data.
