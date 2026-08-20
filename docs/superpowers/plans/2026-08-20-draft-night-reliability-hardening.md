# EdgeIQ Draft-Night Reliability Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Drunk Sundays Streamlit War Room explicit, atomic, recoverable, bounded at 180 picks, and usable from a freshness-labeled local rankings snapshot when upstream data is unavailable.

**Architecture:** Add focused state-schema, lifecycle, and rankings-snapshot services around the existing War Room core. Keep canonical league/keeper logic and all ranking calculations unchanged; Streamlit becomes a thin renderer of validated lifecycle, recovery, completion, and data-source outcomes. Every mutable artifact uses validate-before-replace persistence, and every implementation task follows focused RED -> GREEN TDD with its own commit and review gate.

**Tech Stack:** Python 3.14.6, pandas 3.0.5, NumPy 2.5.2, requests 2.34.2, nflreadpy 0.1.5, Streamlit 1.61.1, pytest 9.1.1, JSON/CSV, pathlib

**Spec:** `docs/superpowers/specs/2026-08-20-draft-night-reliability-hardening-design.md`

## Global Constraints

- Work from the current `live-war-room-core` lineage; create commits there or on an isolated child branch, but do not merge to main.
- Do not reset, clean, stash, delete, or overwrite existing rehearsal/live-state or cache artifacts.
- Existing artifacts may move only through the explicit verified archive/recovery transaction defined by the spec; automated tests use `tmp_path` exclusively.
- Do not change projection formulas, VORP replacement ranks, tier calibration, ranking weights, manual player adjustments, league settings, keeper declarations, keeper rules, or the canonical Drunk Sundays draft order.
- Drunk Sundays must account for exactly 180 total slots, including keeper reservations, and core logic must reject pick 181.
- Existing ranking generation remains authoritative; snapshots preserve output and never recalculate it.
- Per-pick actions perform no upstream network calls and reuse session-cached rankings.
- Every production behavior starts with a focused failing test that fails for the expected missing behavior.
- Preserve all existing tests and performance expectations.

---

### Task 1: Validated Versioned Draft State and Hard Completion

**Files:**
- Create: `fantasy_draft_model/war_room_state.py`
- Modify: `fantasy_draft_model/live_war_room.py`
- Modify: `fantasy_draft_model/ui/draft_war_room.py`
- Create: `tests/test_war_room_state_validation.py`
- Modify: `tests/test_live_war_room_core.py`

**Interfaces:**
- Produces: `StateValidationError`, `DraftCompleteError`, `utc_now_iso()`, `new_draft_id()`, `total_picks_for(league)`, `derive_draft_status(state)`, `validate_war_room_state(state, *, keeper_reservations=None) -> dict`, `migrate_legacy_state(state) -> dict`.
- Updates: `initialize_war_room()` emits schema 2; `advance_keeper_slots()`, `get_pick_context()`, `record_manual_pick()`, and `undo_last_manual_pick()` enforce completion.
- Preserves: existing public pick dictionaries and keeper reservation dictionaries.

- [ ] **Step 1: Write failing schema and validation tests**

Add tests whose wished-for API is:

```python
state = initialize_war_room("drunk_sundays", state_path=tmp_path / "state.json")
assert state["schema_version"] == 2
assert state["total_picks"] == 180
assert state["status"] == "active"
assert state["draft_id"]
assert state["created_at"].endswith("+00:00")
assert validate_war_room_state(state) == state

bad = copy.deepcopy(state)
bad["team_count"] = 10
with pytest.raises(StateValidationError, match="team_count"):
    validate_war_room_state(bad)
```

Parameterize invalid states for missing required fields, duplicate manual pick numbers, duplicate player names, a manual pick in a keeper slot, wrong snake team/round/slot metadata, invalid processed keeper picks, gaps before `current_pick`, future recorded picks, invalid status, and `current_pick` outside 1..181. Use a small helper that creates valid canonical states before each single mutation.

- [ ] **Step 2: Run RED and record the expected failures**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_war_room_state_validation.py tests/test_live_war_room_core.py -q
```

Expected: collection/import fails because `war_room_state.py` and schema-2 behavior do not exist.

- [ ] **Step 3: Implement the minimal schema and validator**

Create dedicated exceptions and pure validation helpers. Resolve canonical league data with `resolve_league`; derive expected snake metadata with the existing snake function; compare keeper reservations against canonical structure supplied by initialization/lifecycle callers. Return the input state unchanged on success and raise one exception containing structured issue text on failure.

`migrate_legacy_state()` must copy schema-1 input, add schema-2 metadata, derive status/total, and validate without touching disk. Do not migrate implicitly in `load_war_room_state()`.

- [ ] **Step 4: Add failing completion tests**

```python
state = valid_state_at_pick_180(tmp_path)
record_manual_pick(state, player_row("Final Player"), state_path)
assert state["current_pick"] == 181
assert state["status"] == "complete"

before = copy.deepcopy(state)
with pytest.raises(DraftCompleteError, match="180"):
    record_manual_pick(state, player_row("Pick 181"), state_path)
assert state == before

removed = undo_last_manual_pick(state, state_path)
assert removed["pick_number"] == 180
assert state["current_pick"] == 180
assert state["status"] == "active"
```

Also test that `get_pick_context()` at 181 raises `DraftCompleteError`, and `build_live_draft_context()` reports `draft_complete=True`, `total_picks=180`, and `accounted_picks=180`.

- [ ] **Step 5: Run the completion tests RED**

Expected: pick 181 is currently accepted or context is generated, and status fields are absent.

- [ ] **Step 6: Implement completion guards and status transitions**

Guard before any mutation. Bound keeper auto-advancement at 181. Update status and `updated_at` before persistence. Undo derives active status after rewinding. Keep completion logic in core, with the UI context only reflecting it.

- [ ] **Step 7: Run focused GREEN and regression tests**

Run the Step 2 command plus:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_live_ui_core_safety.py tests/test_war_room_ui_helpers.py -q
```

Expected: all selected tests pass with no warnings introduced by this task.

- [ ] **Step 8: Commit**

Stage only the five task files and commit:

```text
feat: validate draft state and enforce completion
```

---

### Task 2: Atomic Persistence, Last-Known-Good Backup, and Explicit Recovery

**Files:**
- Create: `fantasy_draft_model/state_persistence.py`
- Modify: `fantasy_draft_model/live_war_room.py`
- Create: `tests/test_war_room_atomic_persistence.py`
- Create: `tests/test_war_room_recovery.py`

**Interfaces:**
- Produces: `StateLoadResult`, `state_backup_path(path)`, `atomic_write_json(path, payload, validator)`, `save_validated_state(state, path)`, `inspect_state_files(path) -> StateLoadResult`, `recover_state_from_backup(path, archive_root) -> dict`.
- `StateLoadResult` contains `state`, `source`, `authoritative_error`, `backup_error`, and paths; it never silently recovers.
- Updates: `save_war_room_state()` delegates to `save_validated_state()`; `load_war_room_state()` accepts only valid authoritative state and raises a typed load error containing inspection results.

- [ ] **Step 1: Write failing atomic-write tests**

Test with `tmp_path` and injected `replace_func`/`fsync_func` seams:

```python
save_validated_state(state_one, path)
save_validated_state(state_two, path)
assert load_json(path) == state_two
assert load_json(state_backup_path(path)) == state_one
assert not list(tmp_path.glob("*.tmp-*"))
```

Inject failure before authoritative replacement and assert the authoritative bytes remain exactly `state_one`. Inject candidate validation failure and assert neither authoritative nor backup changes. Assert `Path.write_text()` is not used on the authoritative path by exercising the public service.

- [ ] **Step 2: Run atomic tests RED**

Expected: imports fail and current direct writes provide no backup.

- [ ] **Step 3: Implement minimal atomic persistence**

Serialize fully before opening files. Write a unique sibling temp with `open("x", encoding="utf-8", newline="\n")`, flush, `os.fsync`, reload, validate, and use `Path.replace`. Back up only a currently validated authoritative file through a second validated temporary copy. Clean up only temps created by the current attempt.

- [ ] **Step 4: Write failing inspection and recovery tests**

```python
path.write_text("{broken", encoding="utf-8")
result = inspect_state_files(path)
assert result.state == valid_backup_state
assert result.source == "backup"
assert result.authoritative_error

restored = recover_state_from_backup(path, tmp_path / "archives")
assert restored == valid_backup_state
assert json.loads(path.read_text(encoding="utf-8")) == valid_backup_state
assert archived_corrupt_bytes == b"{broken"
```

Also cover missing authoritative, invalid backup, both invalid, byte-verified archive failure, and recovery replacement failure. Assert recovery never occurs from `inspect_state_files()` alone.

- [ ] **Step 5: Run recovery tests RED**

Expected: typed inspection/recovery APIs do not exist.

- [ ] **Step 6: Implement explicit recovery**

Archive corrupt evidence with non-overwriting timestamp/draft-safe names, verify SHA-256 and byte length, restore the validated backup through atomic persistence, and revalidate the authoritative result. On failure preserve both original artifacts.

- [ ] **Step 7: Run focused GREEN and existing core tests**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_war_room_atomic_persistence.py tests/test_war_room_recovery.py tests/test_live_war_room_core.py -q
```

- [ ] **Step 8: Commit**

```text
feat: persist and recover draft state atomically
```

---

### Task 3: Explicit Start, Resume, Archive, and Legacy Migration Lifecycle

**Files:**
- Create: `fantasy_draft_model/draft_lifecycle.py`
- Modify: `fantasy_draft_model/live_war_room.py`
- Create: `tests/test_draft_lifecycle.py`

**Interfaces:**
- Produces: `LifecycleInspection`, `inspect_draft_lifecycle(state_path)`, `archive_state_artifacts(state_path, archive_root)`, `start_new_draft(league_key, state_path, archive_root)`, `resume_existing_draft(state_path)`, `recover_existing_draft(state_path, archive_root)`.
- `start_new_draft()` always archives existing authoritative, backup, and recovery metadata before initialization.
- `resume_existing_draft()` validates and explicitly migrates a legacy schema-1 candidate through archive + atomic save.

- [ ] **Step 1: Write failing lifecycle tests**

Cover:

```python
inspection = inspect_draft_lifecycle(path)
assert inspection.requires_choice is True
assert inspection.completed_slots == 12
assert inspection.state_age_seconds >= 0

fresh = start_new_draft("drunk_sundays", path, archive_root)
assert fresh["current_pick"] == first_non_keeper_pick
assert fresh["manual_picks"] == []
assert fresh["keeper_reservations"] == build_keeper_reservations(
    resolve_league("drunk_sundays"), load_keepers("Drunk Sundays")
)
assert archived_source_bytes == original_source_bytes
```

Assert archive names never overwrite, all source artifacts are copied and checksum-verified, archive failure leaves the source bytes unchanged, initialization failure leaves the source bytes unchanged, resume never calls initialize, and a legacy state is archived and migrated only after explicit resume.

- [ ] **Step 2: Run lifecycle tests RED**

Expected: module/API missing.

- [ ] **Step 3: Implement the lifecycle service**

Use dependency injection for clock/ID and keeper loading in tests. Make lifecycle inspection read-only. Archive by copying, not moving. Write a manifest with source path, archive path, SHA-256, byte length, and timestamp atomically inside the unique archive directory. Start fresh only after manifest verification.

- [ ] **Step 4: Add a regression for the current 12-pick rehearsal shape**

Construct a schema-1 fixture matching the existing artifact's 12 manual picks and 15 keepers. Prove inspection reports it but does not resume or mutate it; explicit start archives it and reloads all canonical keepers.

- [ ] **Step 5: Run focused GREEN**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_draft_lifecycle.py tests/test_war_room_recovery.py tests/test_live_war_room_core.py -q
```

- [ ] **Step 6: Commit**

```text
feat: add explicit draft lifecycle controls
```

---

### Task 4: Bounded Live Refresh and Validated Rankings Snapshot

**Files:**
- Create: `fantasy_draft_model/rankings_snapshot.py`
- Modify: `fantasy_draft_model/integrations/sleeper_api.py`
- Modify: `fantasy_draft_model/integrations/roster_loader.py`
- Modify: `fantasy_draft_model/integrations/depth_chart_loader.py`
- Modify: `fantasy_draft_model/ui/streamlit_app.py`
- Create: `tests/test_rankings_snapshot.py`
- Create: `tests/test_war_room_offline_startup.py`
- Modify: `tests/test_current_injury_pipeline.py`
- Modify: `tests/test_depth_chart_freshness.py`

**Interfaces:**
- Produces: `RankingDataStatus`, `RankingRefreshError`, `save_rankings_snapshot(rankings, league_key, data_path, metadata_path)`, `load_rankings_snapshot(league_key, data_path, metadata_path)`, `run_with_timeout(callable_, timeout_seconds)`, `load_rankings_with_fallback(league_key, builder, paths, timeout_seconds) -> tuple[pd.DataFrame, RankingDataStatus]`.
- Snapshot format: UTF-8 CSV plus JSON metadata with schema, league, UTC creation time, row count, required columns, CSV SHA-256, and source.
- Sleeper exposes `(connect_timeout, read_timeout)` constants; nflverse loader functions accept no semantic changes but are bounded by the startup coordinator.

- [ ] **Step 1: Write failing snapshot round-trip and validation tests**

```python
save_rankings_snapshot(board, "drunk_sundays", csv_path, meta_path)
loaded, status = load_rankings_snapshot("drunk_sundays", csv_path, meta_path)
pd.testing.assert_frame_equal(normalize(loaded), normalize(board))
assert status.source == "CACHED/OFFLINE"
assert status.created_at
assert status.age_seconds >= 0
```

Assert tampered CSV checksum, wrong league, mismatched row count, missing required column, duplicate normalized name, invalid position, and mismatched metadata are rejected. Assert a failed save preserves the previous valid pair.

- [ ] **Step 2: Run snapshot tests RED**

Expected: module/API missing.

- [ ] **Step 3: Implement atomic snapshot pair persistence**

CSV must preserve every War Room-required scalar column and use JSON-safe strings for list-valued explanation columns if present. Validate the candidate pair before replacing either live file. Use generation-specific filenames referenced by one atomically replaced metadata pointer so readers never observe a mixed pair. Retain the previous referenced generation as last known good; do not delete older cache artifacts in this task.

- [ ] **Step 4: Write failing bounded fallback tests**

```python
board, status = load_rankings_with_fallback(
    "drunk_sundays",
    builder=lambda _: raise_(TimeoutError("upstream exceeded 15s")),
    paths=paths,
    timeout_seconds=15,
)
assert status.source == "CACHED/OFFLINE"
assert "exceeded" in status.failure_reason
assert status.created_at == cached_created_at
```

Also assert live success writes/returns `LIVE`; builder timeout returns within a fake-clock/executor seam; live failure plus absent/invalid cache raises `RankingRefreshError`; `requests.get` receives a connect/read timeout tuple; and no builder runs during cached per-pick UI calls.

- [ ] **Step 5: Run bounded fallback tests RED**

Expected: current startup calls `build_draft_rankings()` directly and no status is available.

- [ ] **Step 6: Implement bounded refresh and fallback**

Use a daemon-thread-compatible bounded executor abstraction that does not block application exit on a timed-out worker. Centralize draft-night timeout constants. Do not modify ranking/projection calculations. Return the original live DataFrame unchanged on success and the validated cached DataFrame on fallback.

- [ ] **Step 7: Run focused GREEN and performance regression**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_rankings_snapshot.py tests/test_war_room_offline_startup.py tests/test_current_injury_pipeline.py tests/test_depth_chart_freshness.py tests/test_war_room_performance_cache.py tests/test_war_room_interaction_performance.py -q
```

- [ ] **Step 8: Commit**

```text
feat: add bounded offline rankings fallback
```

---

### Task 5: Lifecycle, Recovery, Completion, and Freshness UI

**Files:**
- Modify: `fantasy_draft_model/ui/streamlit_app.py`
- Modify: `fantasy_draft_model/ui/draft_war_room.py`
- Create: `tests/test_war_room_lifecycle_ui.py`
- Create: `tests/test_war_room_completion_ui.py`
- Modify: `tests/test_streamlit_war_room_startup.py`
- Modify: `tests/test_streamlit_war_room_shell.py`

**Interfaces:**
- Produces: `render_lifecycle_gate(st, inspection) -> str | None`, `render_state_recovery(st, inspection)`, `render_rankings_status(st, status)`, `render_draft_complete(st, context)`.
- Updates: `run_war_room_ui()` requires session authorization before loading the live board; `render_draft_actions()` disables recording at completion and preserves undo.

- [ ] **Step 1: Write failing lifecycle UI tests with the existing fake Streamlit pattern**

Assert first launch with valid state renders state metadata and Start/Resume buttons but does not call `build_live_view()`. Clicking Resume sets a session authorization keyed by `draft_id`. Starting calls only `start_new_draft()`, shows the verified archive path, and authorizes the new draft. A changed on-disk `draft_id` invalidates old session authorization and returns to the gate.

- [ ] **Step 2: Run lifecycle UI RED**

Expected: current UI silently loads/builds the War Room.

- [ ] **Step 3: Implement the thin lifecycle gate**

Use service return objects; do not duplicate validation in Streamlit. Catch typed lifecycle/state exceptions and render recovery actions and exact artifact paths. No automatic initialize-on-missing behavior remains.

- [ ] **Step 4: Write failing completion and freshness UI tests**

```python
render_war_room_snapshot(fake_st, complete_snapshot)
assert ("success", "Draft Complete — 180 of 180 slots accounted for") in fake_st.messages

render_draft_actions(fake_st, complete_snapshot)
assert fake_st.button_calls["Record Pick"]["disabled"] is True
assert fake_st.button_calls["Undo Last Pick"]["disabled"] is False

render_rankings_status(fake_st, cached_status)
assert "CACHED/OFFLINE" in fake_st.rendered_text
assert cached_status.created_at in fake_st.rendered_text
assert cached_status.failure_reason in fake_st.rendered_text
```

Also assert LIVE status is visible, cached age is visible, and failed live+cache startup renders Retry plus runbook guidance without a player board.

- [ ] **Step 5: Run UI tests RED**

Expected: completion copy/status banner missing and Record Pick remains enabled when players exist.

- [ ] **Step 6: Implement UI states and stale-action handling**

Core exceptions from record/undo are displayed without losing lifecycle authorization. Completion removes player explanation/actions that advance state but keeps roster/history and Undo. Render data source above the board on every authorized session.

- [ ] **Step 7: Run focused GREEN and all existing UI tests**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_war_room_lifecycle_ui.py tests/test_war_room_completion_ui.py tests/test_streamlit_war_room_startup.py tests/test_streamlit_war_room_shell.py tests/test_war_room_*.py tests/test_live_ui_core_safety.py -q
```

- [ ] **Step 8: Commit**

```text
feat: expose safe draft lifecycle and recovery UI
```

---

### Task 6: Reproducible Dependencies and Draft-Night Runbook

**Files:**
- Create: `requirements.txt`
- Create: `docs/DRAFT_NIGHT_RUNBOOK.md`
- Modify: `README.md`
- Create: `tests/test_draft_night_runbook.py`

**Interfaces:**
- Produces: pinned direct dependencies for the verified Python 3.14 environment and an operator procedure with exact commands and artifact locations.

- [ ] **Step 1: Write failing manifest/runbook contract tests**

Read the files as text and assert exact required entries and commands:

```python
assert "pandas==3.0.5" in requirements
assert "numpy==2.5.2" in requirements
assert "requests==2.34.2" in requirements
assert "nflreadpy==0.1.5" in requirements
assert "streamlit==1.61.1" in requirements
assert "pytest==9.1.1" in requirements
assert ".\\.venv\\Scripts\\python.exe -m streamlit run fantasy_draft_model/ui/streamlit_app.py" in runbook
```

Assert runbook headings/text cover preflight, Start New Draft, Resume, corrupt authoritative recovery, both copies invalid, offline cache, cache freshness, artifact preservation, archive paths, and the full-suite command. Assert README links to it.

- [ ] **Step 2: Run documentation tests RED**

Expected: files/links missing.

- [ ] **Step 3: Create the pinned manifest and operational runbook**

Document Python 3.14.6, virtual environment creation, install command, exact launch command, expected lifecycle gate, and safe recovery steps. State explicitly that operators must not delete or manually overwrite state/cache artifacts and must copy diagnostic artifacts before escalation.

- [ ] **Step 4: Validate dependency installation syntax without mutating the environment**

Run:

```powershell
.\.venv\Scripts\python.exe -m pip install --dry-run -r requirements.txt
```

If network resolution is unavailable, validate installed versions with `pip check` and record the dry-run limitation; do not broaden dependency versions silently.

- [ ] **Step 5: Run documentation GREEN**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_draft_night_runbook.py -q
```

- [ ] **Step 6: Commit**

```text
docs: add reproducible draft-night runbook
```

---

### Task 7: Full 180-Pick Drunk Sundays Restart and Recovery Simulation

**Files:**
- Create: `tests/test_live_war_room_full_draft.py`
- Modify production only if a new RED simulation exposes a root-cause defect; any fix must remain within Tasks 1-5 interfaces and receive its own regression assertion.

**Interfaces:**
- Verifies: canonical league profile, real keeper declarations, lifecycle service, validated atomic persistence, recovery, completion, and undo.

- [ ] **Step 1: Write the end-to-end simulation test**

Build a deterministic synthetic ranking pool with more unique non-keeper players than needed. Use the real `resolve_league("drunk_sundays")` and `load_keepers("Drunk Sundays")`. Start through `start_new_draft()` in `tmp_path`.

For each live slot:

```python
context = get_pick_context(state)
expected = expected_snake_owner(context["pick_number"], canonical_order)
assert context["fantasy_team"] == expected
record_manual_pick(state, next_unique_player(), state_path)
state = load_war_room_state(state_path)
```

At fixed checkpoints after rounds 2, 7, and 14, reload from disk and revalidate. Immediately before a keeper boundary, record/undo/re-record and assert keeper processing reopens correctly. At mid-draft, corrupt only a temporary-copy authoritative file, inspect, explicitly recover from backup, and continue.

- [ ] **Step 2: Add final invariants**

Assert:

```python
assert state["current_pick"] == 181
assert state["status"] == "complete"
assert len(state["manual_picks"]) + len(state["keeper_reservations"]) == 180
assert accounted_pick_numbers == set(range(1, 181))
assert all(len(rosters[team]) == 15 for team in canonical_order)
assert len(all_player_keys) == len(set(all_player_keys))
```

Verify every keeper's canonical round/pick/owner, all round boundaries (12/13, 24/25, through 168/169), and every manual pick's canonical owner. Assert pick 181 raises `DraftCompleteError` without byte changes. Undo the final manual pick, assert active at 180, then re-record and complete again.

- [ ] **Step 3: Run simulation RED or GREEN**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_live_war_room_full_draft.py -vv
```

If RED, invoke systematic debugging, identify the earliest violated invariant, add/retain its focused assertion, implement only the minimal root-cause fix, and rerun. If it passes immediately because Tasks 1-5 fully provide the behavior, record that the simulation is proof rather than a production change.

- [ ] **Step 4: Run the focused reliability suite**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_war_room_state_validation.py tests/test_war_room_atomic_persistence.py tests/test_war_room_recovery.py tests/test_draft_lifecycle.py tests/test_rankings_snapshot.py tests/test_war_room_offline_startup.py tests/test_war_room_lifecycle_ui.py tests/test_war_room_completion_ui.py tests/test_live_war_room_full_draft.py -q
```

- [ ] **Step 5: Commit**

```text
test: prove complete recoverable Drunk Sundays draft
```

---

### Task 8: Full Regression, Performance, Artifact Safety, and Final Review

**Files:**
- Modify only files required by verified review findings, using a new failing regression test for every behavior fix.
- Do not modify repository live/cache artifacts.

**Interfaces:**
- Verifies all plan and spec acceptance criteria.

- [ ] **Step 1: Capture artifact hashes before verification**

Record SHA-256, length, and modification time for existing repository state/cache artifacts, including `fantasy_draft_model/data/live_war_room_state.json` and any discovered backup/snapshot artifacts. Do not stage them.

- [ ] **Step 2: Run the full suite fresh**

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
.\.venv\Scripts\python.exe -m pytest -q
```

Expected: original 205 tests plus all new tests pass, zero failures.

- [ ] **Step 3: Run the 180-pick simulation separately with evidence**

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
.\.venv\Scripts\python.exe -m pytest tests/test_live_war_room_full_draft.py -vv
```

Capture exact assertions/counts from the test output or a deterministic summary emitted by the simulation fixture.

- [ ] **Step 4: Run performance and dependency checks**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_war_room_interaction_performance.py tests/test_war_room_performance_cache.py -q
.\.venv\Scripts\python.exe -m pip check
```

- [ ] **Step 5: Verify artifact preservation and diff hygiene**

Recompute hashes/length/mtime and prove existing repository state/cache artifacts are unchanged. Run `git diff --check`, inspect `git status --short`, and confirm no pycache/live/cache artifact is staged.

- [ ] **Step 6: Dispatch independent whole-branch review**

Provide the approved spec, this plan, progress ledger, merge-base-to-HEAD review package, exact verification output, and artifact-preservation evidence to a fresh most-capable reviewer. Require explicit spec-compliance and code-quality verdicts, security/recovery analysis, and remaining-risk assessment.

- [ ] **Step 7: Fix review findings through one reviewed RED -> GREEN wave**

For each Critical or Important finding, add a focused failing test first, verify RED, implement the minimal fix, verify GREEN, and commit. Dispatch one scoped re-review of the entire fix wave. Record Minor findings and rulings for final reporting.

- [ ] **Step 8: Repeat final verification after review fixes**

Repeat Steps 1-5 on final HEAD. No completion claim may use pre-fix evidence.

- [ ] **Step 9: Keep the branch as-is**

Do not merge or push. Report the branch/worktree path and all requested evidence, risks, rulings, and final go/no-go recommendation.
