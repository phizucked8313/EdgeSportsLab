# EdgeIQ Live War Room Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reliable manual-entry live War Room core that tracks a real in-person snake draft, keepers, rosters, available players, EdgeIQ recommendations, undo/reset, and persistent state.

**Architecture:** Create a new `fantasy_draft_model/live_war_room.py` service that consumes the already-verified league profile, keeper engine, snake-draft helpers, and Draft Assistant. Keep persistence and draft-state logic out of Streamlit; the later UI will call this service. Do not use the stale `league_manager.py` or legacy `draft_state.py` as dependencies.

**Tech Stack:** Python 3, pandas, JSON, pathlib, pytest

**Spec:** `docs/superpowers/specs/2026-08-19-live-war-room-core-design.md`

## Global Constraints

- Manual in-person draft entry only; no Yahoo live-sync dependency.
- `league_profile.py` is the canonical league configuration.
- `build_draft_assistant()` remains the only recommendation/ranking source.
- Keepers are unavailable from the start and appear on owner rosters from the start.
- Keeper-reserved draft slots auto-advance; the user never manually enters keeper picks.
- Normal manual pick entry derives the fantasy team from snake order.
- State must survive process/browser reruns through atomic JSON persistence.
- Undo removes one manual pick and reopens any keeper slots auto-processed after it.
- No Streamlit code in this plan.
- Preserve all existing EdgeIQ behavior and tests.

---

### Task 1: Canonical user-team identity and initial War Room state

**Files:**
- Modify: `fantasy_draft_model/models/league_profile.py`
- Create: `fantasy_draft_model/live_war_room.py`
- Create: `tests/test_live_war_room_core.py`

**Interfaces:**
- Produces: `resolve_league(league_name_or_key)`, `initialize_war_room(league_name_or_key, state_path=None)`, `load_war_room_state(state_path)`, `save_war_room_state(state, state_path)`

- [ ] **Step 1: Write RED tests**

Tests assert:

```python
league = resolve_league("drunk_sundays")
assert league["name"] == "Drunk Sundays"
assert league["user_team"] == "BLKWDW'S"

state = initialize_war_room("drunk_sundays", state_path=tmp_path / "state.json")
assert state["league_key"] == "drunk_sundays"
assert state["current_pick"] == 1
assert state["manual_picks"] == []
assert state["user_team"] == "BLKWDW'S"
```

Also assert reload returns the same state.

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_live_war_room_core.py -v`

Expected: FAIL because `live_war_room.py` and canonical `user_team` do not exist.

- [ ] **Step 3: Implement minimal GREEN**

Add canonical `user_team` fields:

```python
"Drunk Sundays": {"user_team": "BLKWDW'S", ...}
"Somewhat Related": {"user_team": "Phizucked", ...}
```

Implement league resolution by display name or `league_key`, default league-specific state path, atomic JSON save via `.tmp` + `Path.replace`, and initialization.

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest tests/test_live_war_room_core.py -v`

Expected: initial state tests pass.

- [ ] **Step 5: Commit**

Commit message: `Build live War Room state foundation`

---

### Task 2: Keeper reservations and automatic reserved-pick advancement

**Files:**
- Modify: `fantasy_draft_model/live_war_room.py`
- Modify: `tests/test_live_war_room_core.py`

**Interfaces:**
- Produces: `build_keeper_reservations(league, keepers_df)`, `advance_keeper_slots(state)`, `get_draft_history(state)`

- [ ] **Step 1: Write RED tests**

Use synthetic keeper data and assert snake reservation math, including Drunk Sundays slot 9 round 3 -> overall pick 33. Assert all keepers are stored on initialization, and setting `current_pick` to a reserved slot causes `advance_keeper_slots()` to increment past it and record the pick number in `processed_keeper_picks`.

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_live_war_room_core.py -v`

Expected: new keeper tests fail.

- [ ] **Step 3: Implement minimal GREEN**

Build reservation records containing `pick_number`, `round`, `draft_slot`, `fantasy_team`, `player_name`, `keeper_type`, and `keeper_round`. Load declared keepers during initialization. Implement a loop that advances through consecutive reserved picks and never duplicates a processed keeper slot.

- [ ] **Step 4: Run GREEN**

Expected: keeper tests pass.

- [ ] **Step 5: Commit**

Commit message: `Add War Room keeper reservations`

---

### Task 3: Current-pick context and manual pick recording

**Files:**
- Modify: `fantasy_draft_model/live_war_room.py`
- Modify: `tests/test_live_war_room_core.py`

**Interfaces:**
- Produces: `get_pick_context(state)`, `record_manual_pick(state, player_row, state_path=None)`

- [ ] **Step 1: Write RED tests**

Assert pick 1 belongs to slot 1, pick 12 to slot 12, pick 13 to slot 12, and pick 16 belongs to slot 9 / `BLKWDW'S`. Assert recording a player at pick 16 assigns `BLKWDW'S` automatically, records round/slot/team metadata, increments current pick, and rejects duplicate player names.

- [ ] **Step 2: Run RED**

Expected: context/recording tests fail.

- [ ] **Step 3: Implement minimal GREEN**

Use `get_draft_context()` and the canonical list draft order. Store player name, position, NFL team, bye, draft rank, fantasy team, pick number, round, and draft slot. After each pick, increment then call `advance_keeper_slots()`.

- [ ] **Step 4: Run GREEN**

Expected: tests pass.

- [ ] **Step 5: Commit**

Commit message: `Record live War Room picks`

---

### Task 4: Available EdgeIQ board and roster snapshot

**Files:**
- Modify: `fantasy_draft_model/live_war_room.py`
- Modify: `tests/test_live_war_room_core.py`

**Interfaces:**
- Produces: `build_available_board(state, assistant_builder=build_draft_assistant)`, `build_rosters(state)`, `build_war_room_snapshot(state, assistant_builder=build_draft_assistant)`

- [ ] **Step 1: Write RED tests**

Monkeypatch the assistant builder with a deterministic DataFrame. Assert:

- it receives the state's `league_key`;
- it receives current `picks_until_user`;
- all keepers are filtered from the board before any manual picks;
- manually drafted players are also filtered;
- roster output includes keepers plus manual picks without duplication;
- snapshot exposes context, available board, all rosters, user roster, and recent history.

- [ ] **Step 2: Run RED**

Expected: snapshot tests fail.

- [ ] **Step 3: Implement minimal GREEN**

Filter names case-insensitively. Keep assistant columns intact so Pressure, Draft Brain, injuries, tiers, and What-If-I-Wait survive for the front end.

- [ ] **Step 4: Run GREEN**

Expected: tests pass.

- [ ] **Step 5: Commit**

Commit message: `Expose live War Room snapshot`

---

### Task 5: Undo, reset, and persistence recovery

**Files:**
- Modify: `fantasy_draft_model/live_war_room.py`
- Modify: `tests/test_live_war_room_core.py`

**Interfaces:**
- Produces: `undo_last_pick(state, state_path=None)`, `reset_war_room(state, state_path=None)`

- [ ] **Step 1: Write RED tests**

Create a manual pick immediately before a keeper reservation. Assert undo removes the manual pick, restores `current_pick` to that manual pick number, and clears processed keeper slots at or after the rewind point. Assert reset removes all manual picks/processed slots but preserves keeper reservations and league identity. Assert saved state reloads identically.

- [ ] **Step 2: Run RED**

Expected: recovery tests fail.

- [ ] **Step 3: Implement minimal GREEN**

Undo only manual selections. Keep keeper declarations immutable in normal recovery. Persist every successful mutation atomically.

- [ ] **Step 4: Run GREEN**

Expected: tests pass.

- [ ] **Step 5: Commit**

Commit message: `Add War Room recovery controls`

---

### Task 6: Complete-draft simulation and regression gate

**Files:**
- Create: `tests/test_live_war_room_full_draft.py`
- No planned production changes unless the simulation exposes a root-cause defect.

**Interfaces:**
- Verifies the complete core API.

- [ ] **Step 1: Write simulation test**

Use a synthetic board with enough unique players plus the real Drunk Sundays profile/keepers. Loop until the draft finishes, automatically allowing keeper slots to advance and recording one unique manual player at every live slot.

Assert:

```python
assert state["current_pick"] == 181
assert len(state["manual_picks"]) + len(state["keeper_reservations"]) == 180
assert len(all_selected_names) == len(set(all_selected_names))
```

Also assert each fantasy team has exactly 15 rostered players when keepers + manual picks are combined.

- [ ] **Step 2: Run simulation test**

Expected after prior tasks: PASS. If it fails, use systematic debugging before changing production code.

- [ ] **Step 3: Run focused War Room suite**

Run: `python -m pytest tests/test_live_war_room_core.py tests/test_live_war_room_full_draft.py -v`

Expected: all pass.

- [ ] **Step 4: Run full EdgeIQ suite**

Run: `python -m pytest -q`

Expected: zero failures.

- [ ] **Step 5: Run one live Drunk Sundays smoke check**

Build a real snapshot from the live assistant and verify non-empty board, valid current team, no keeper names in available players, no duplicate player names, and zero missing core recommendation columns.

- [ ] **Step 6: Review branch and integrate only after fresh verification**

Require branch `behind_by == 0` and a clean fast-forward into `EdgeIQ`.
