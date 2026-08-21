# Final 2026 Draft Snapshot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce one provenance-rich, checksum-verified Top 300 artifact that passes the full data-integrity audit and reloads offline through the production snapshot loader.

**Architecture:** Add a dedicated freeze validator/exporter around the existing production ranking pipeline. Keep model ranking inputs unchanged except for objectively verified normalization, schedule, injury, identity, or join defects proven by regression tests. Persist the immutable Top 300 CSV and a manifest that records pinned inputs, audit evidence, waivers, exclusions, and the CSV checksum.

**Tech Stack:** Python 3.14, pandas, nflreadpy, requests, pytest, SHA-256, JSON/CSV.

**Spec:** `C:/Users/Shawn Gutekunst/.codex/attachments/bca456ce-e9f5-4559-a680-65208349abe1/pasted-text.txt`

## Global Constraints

- Start from `origin/live-war-room-core` commit `af4db9cc1ac0da095b51dc97dbcf54badccfcf8b` on `codex/final-draft-snapshot-2026`.
- Do not change rankings to match consensus, ADP, or subjective player preference.
- Use strict RED/GREEN TDD for every production behavior change.
- Do not modify, stage, or commit unrelated cache, state, archive, or generated artifacts.
- Do not merge or push.

---

### Task 1: Freeze Contract and Structural Validator

**Files:**
- Create: `fantasy_draft_model/final_snapshot.py`
- Test: `tests/test_final_snapshot.py`

**Interfaces:**
- Consumes: full production rankings, canonical keepers, pinned input metadata, league key, source commit, configuration bytes.
- Produces: `select_top_300(board)`, `validate_top_300(board, ...)`, `build_freeze_manifest(...)`, `save_frozen_snapshot(...)`, and `load_frozen_snapshot_offline(...)`.

- [ ] Write tests requiring exactly 300 rows, integer ranks 1-300, unique GSIS IDs, exact and normalized names, canonical teams, supported positions, complete ranking inputs, valid team/bye pairs, and exactly-once keeper exclusion/reservation behavior.
- [ ] Run `python -m pytest tests/test_final_snapshot.py -q` and confirm RED because the freeze API is absent.
- [ ] Implement the smallest validator and deterministic Top 300 selection needed for GREEN.
- [ ] Run the targeted test and confirm GREEN.
- [ ] Commit only the validator and test.

### Task 2: Provenance, Schedule, Injury, Depth, and Rookie Evidence

**Files:**
- Modify: `fantasy_draft_model/final_snapshot.py`
- Modify only if a proven defect requires it: `fantasy_draft_model/models/schedule.py`, `fantasy_draft_model/integrations/current_injury_normalizer.py`, `fantasy_draft_model/engines/projection_engine.py`
- Create if needed for documented evidence: `fantasy_draft_model/data/frozen/2026/...`
- Test: `tests/test_final_snapshot.py`

**Interfaces:**
- Consumes: actual upstream retrieval timestamps/identifiers, authoritative 2026 schedule data, Sleeper status data, nflverse roster/depth data, and production rookie fields.
- Produces: per-player reconciliation records, source timestamps, explicit unresolved findings, exclusions, and waivers; freeze validation fails on unresolved required assertions.

- [ ] Run one live audit build and capture the complete production pool plus upstream evidence in memory.
- [ ] Add the smallest failing regression test for each confirmed production defect.
- [ ] Demonstrate RED before changing production behavior.
- [ ] Apply only objective data/normalization fixes; rerun each focused test to GREEN.
- [ ] Reconcile all Top 300 injuries, depth misses/conflicts, all 50 rookies, Audric Estime, and all team/bye pairs; mark any non-correctable required item as a blocker.
- [ ] Commit each tested defect family separately where practical.

### Task 3: Frozen Export and Offline Loader

**Files:**
- Modify: `fantasy_draft_model/final_snapshot.py`
- Modify: `fantasy_draft_model/rankings_snapshot.py` only if the exact frozen artifact cannot be accepted through its production path.
- Test: `tests/test_final_snapshot.py`
- Create: immutable CSV and JSON manifest under `fantasy_draft_model/data/frozen/2026/`.

**Interfaces:**
- Consumes: one already-built and validated Top 300 frame; no second live build.
- Produces: CSV bytes, SHA-256 checksum, provenance manifest, and offline-loaded validated frame.

- [ ] Write a failing round-trip test proving the exact frozen format reloads with all structural and keeper assertions while all live builders are unavailable.
- [ ] Confirm RED.
- [ ] Implement atomic export, manifest validation, checksum verification, and offline reload.
- [ ] Confirm GREEN and tamper rejection.
- [ ] Generate the production board once, validate it, and write the final artifacts only if no blocker remains.
- [ ] Commit the verified artifact and manifest with `chore: freeze verified 2026 draft-night snapshot`.

### Task 4: Final Verification and Report

**Files:**
- Update: `docs/DRAFT_NIGHT_RUNBOOK.md` only if required to identify the immutable artifact and offline load command.

**Interfaces:**
- Consumes: committed frozen artifact and manifest.
- Produces: fresh targeted/full-suite/offline evidence and the requested 23-item final report.

- [ ] Run targeted tests for every changed component.
- [ ] Run the complete test suite and require zero failures.
- [ ] Disable/block live upstream calls and load the exact committed artifact offline.
- [ ] Rerun the final snapshot validator against the offline frame.
- [ ] Verify artifact and manifest checksums from disk.
- [ ] Inspect `git diff --cached`, commits, and status; confirm unrelated generated files are unstaged.
- [ ] Report `READY FOR DRAFT NIGHT` only if every required assertion is proven; otherwise report `NOT READY` with exact blockers and do not create a misleading immutable marker.

## Self-review

- All 15 checklist items are covered by Tasks 1-4.
- Every possible behavior change has an explicit RED/GREEN gate.
- The board is generated once and reused for audit/export.
- Offline validation consumes the exact bytes intended for draft night.
- No subjective ranking adjustment, UI work, merge, or push is included.
