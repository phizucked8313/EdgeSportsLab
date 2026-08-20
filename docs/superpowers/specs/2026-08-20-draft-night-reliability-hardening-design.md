# EdgeIQ Draft-Night Reliability Hardening Design

**Date:** 2026-08-20

**Branch:** `live-war-room-core`

**League:** Drunk Sundays (`drunk_sundays`)

## Purpose

Make the live EdgeIQ War Room operationally safe and recoverable on draft night without changing projection formulas, VORP replacement ranks, tier calibration, ranking weights, player or position valuation, keeper rules, or the canonical Drunk Sundays draft order.

The War Room must never silently enter an old rehearsal, corrupt its only draft-state copy, accept a 181st pick, hang indefinitely during live data refresh, or conceal that it is using stale cached rankings.

## Existing Findings

The current implementation has these readiness gaps:

- Streamlit loads `live_war_room_state.json` automatically and therefore silently resumes whatever rehearsal or draft it contains.
- The current live artifact contains an in-progress 12-pick Drunk Sundays rehearsal and has no draft identity or timestamps.
- `save_war_room_state()` writes JSON directly to the authoritative path, so interruption can leave a truncated file.
- State is not structurally or semantically validated on save or load.
- There is no automatic last-known-good backup or visible corrupt-state recovery path.
- Draft completion is implicit; core logic can calculate pick 181 and the UI continues offering actions.
- Sleeper has a 30-second request timeout, but nflverse roster and depth-chart calls have no application-level bound.
- Rankings have no durable local snapshot, no startup fallback, and no displayed freshness or offline status.
- The repository has no conventional reproducible Python dependency manifest or consolidated draft-night recovery runbook.

## Chosen Architecture

Use layered, validated file persistence rather than introducing a database immediately before draft night. JSON state remains human-inspectable and fast. Atomic replacement, last-known-good backup, immutable archives, explicit lifecycle decisions, and strict validation provide transactional safety with a small change surface.

SQLite or a full event journal is out of scope. It would add migration, operational, and testing complexity without being necessary for a single local 180-slot draft.

## 1. Explicit Draft Lifecycle

Every new Streamlit browser session stops at a lifecycle gate before showing the War Room. A valid file is not sufficient authorization to resume it.

The gate displays:

- league name;
- draft identifier;
- lifecycle status (`active` or `complete`);
- completed slots out of 180;
- manual-pick and keeper counts;
- creation and last-update timestamps;
- state age;
- whether a valid backup is available;
- rankings source, creation time, and age when known.

It offers these actions:

### Resume Existing Draft

Resume is enabled only when the authoritative state or an explicitly recovered backup passes validation. The user must click it for the current Streamlit session. A stale or completed state remains resumable, but its age and status are visibly called out.

### Start New Draft

Starting fresh performs this ordered transaction:

1. Inspect and validate the current authoritative state and backup without modifying either.
2. Copy every existing state artifact into a new timestamped archive directory using non-overwriting names. Malformed files are archived as evidence too.
3. Verify that the archive copies exist and match their source bytes.
4. Load the current canonical Drunk Sundays league profile and keeper declarations.
5. Build and validate a fresh state with those keeper reservations.
6. Persist it through the atomic state writer.
7. Enter the new draft only after the new state reloads and validates.

If archiving or initialization fails, the current authoritative and backup files remain unchanged and the UI reports the failure. No reset, delete, or overwrite operation bypasses the archive step.

### Recover Last Known-Good State

When the authoritative file is missing, malformed, or invalid and a valid backup exists, the lifecycle screen explains the problem and offers an explicit recovery action. Recovery archives the bad authoritative artifact, atomically restores the validated backup as authoritative state, reloads it, and then returns to the lifecycle gate. It does not silently replace evidence.

If neither copy is valid, the UI offers Start New Draft after archiving the available artifacts and displays the archive location. It never invents or partially repairs picks.

## 2. State Schema and Validation

The state schema advances from version 1 to version 2 and adds:

- `draft_id`: locally generated unique identifier;
- `created_at`: UTC ISO-8601 timestamp;
- `updated_at`: UTC ISO-8601 timestamp;
- `status`: `active` or `complete`;
- `total_picks`: canonical `team_count * draft_rounds`, exactly 180 for Drunk Sundays.

Legacy schema-1 state is read-only migratable. Migration builds a schema-2 candidate in memory, validates all existing picks and reservations, then persists through the normal archive-and-atomic-write path only after an explicit Resume or Recover lifecycle action. Migration never mutates the old file in place.

Validation is centralized and runs before every accepted load and before every save. It verifies:

- required fields and supported schema version;
- canonical league key, name, user team, team count, rounds, total picks, and draft order-derived ownership;
- integer pick ranges from 1 through 180 for recorded slots;
- `current_pick` from 1 through 181;
- lifecycle consistency: active before 181 and complete at 181;
- unique manual pick numbers and unique processed keeper picks;
- no manual pick occupies a keeper reservation;
- no duplicated player across manual picks and keeper reservations, case-insensitively;
- manual pick round, draft slot, and fantasy team match canonical snake math;
- keeper reservation round, slot, overall pick, and owner match freshly derived canonical keeper declarations;
- processed keeper picks are declared reservations strictly before `current_pick`;
- every slot before `current_pick` is accounted for by exactly one manual pick or processed keeper reservation;
- no slot at or after `current_pick` is recorded as complete;
- JSON values needed by the UI have valid basic types.

Validation returns structured issues for the UI and raises a dedicated state-validation exception in core mutation paths. Invalid state is never accepted as the active in-memory draft.

## 3. Atomic Persistence and Backup

The persistence service owns all authoritative state mutations.

For each save:

1. Copy the proposed state and update its timestamp/status fields.
2. Validate and serialize the entire candidate before touching disk.
3. Write it to a uniquely named sibling temporary file.
4. Flush the file and request an OS-level sync.
5. Reload and validate the temporary file.
6. If the current authoritative file is valid, atomically replace the last-known-good backup with that current file through its own temporary path.
7. Atomically replace the authoritative file with the validated candidate.
8. Reload and validate the authoritative result.
9. Remove only the temporary file created by this attempted transaction when safe.

The authoritative path is never opened in truncate/write mode. A failure before replacement preserves the old authoritative state. A failure after replacement retains its previous validated version in the backup.

The state path has deterministic siblings for last-known-good backup and recovery metadata. Tests use temporary directories and inject replacement failures so no live artifact is exercised.

## 4. Hard Draft Completion

Drunk Sundays has exactly 12 teams and 15 rounds, for exactly 180 accounted slots including keepers.

Core behavior:

- `total_picks` is derived from canonical league configuration and validated as 180.
- Advancing keeper slots stops at 181 and marks the draft complete.
- Recording pick 180 advances to 181, marks the draft complete, and saves atomically.
- Any attempt to record a manual pick when `current_pick > total_picks` raises a dedicated draft-complete error before mutating state.
- Pick context refuses to generate metadata for pick 181.
- Completion remains based on accounted slots, not merely the count of manual selections.
- Undoing the last manual selection from a complete draft restores that pick, reopens any keeper slots crossed by the rewind, sets status to active, and persists.

Streamlit behavior:

- the context displays a clear `Draft Complete — 180 of 180 slots accounted for` state;
- Record Pick and other draft-advancing controls are disabled after completion;
- Undo remains available when manual history exists;
- recommendation and roster views remain readable after completion;
- stale client actions are rejected again in core logic, not only disabled in the UI.

## 5. Offline Rankings and Bounded Startup

Live rankings are treated as refreshable input, not a prerequisite for opening a recoverable draft.

### Bounded Sources

- Requests-based integrations use explicit connect and read timeouts.
- nflverse roster and depth-chart operations, whose library APIs do not expose a dependable timeout, execute behind an application-level bounded worker during startup refresh.
- A timed-out source is treated as a refresh failure. The UI proceeds to cache fallback; it does not wait indefinitely for the worker.
- Timeouts are centralized constants and remain short enough for draft-night startup. They are not applied to per-pick interactions because rankings are loaded once and reused in session memory.

### Last-Known-Good Rankings Snapshot

A successful complete Drunk Sundays ranking build is validated, then written as:

- a local tabular snapshot preserving the columns and scalar values required by the War Room; and
- JSON metadata containing schema version, league key, creation timestamp, row count, required-column list, and a content checksum.

Snapshot and metadata use temporary-file validation and atomic replacement. The previous valid snapshot remains available until the new pair is accepted. A partially written or mismatched pair is rejected.

The snapshot validator verifies league identity, checksum, row count, required columns, unique normalized player names, valid positions, and usable ranking values. It does not recalculate or alter rankings.

### Startup Policy and Freshness

Startup attempts a live build within the configured bound. On success it labels data `LIVE`, stores the snapshot, and records the build timestamp. On failure it loads the validated snapshot and labels data `CACHED/OFFLINE`.

The UI always displays:

- source (`LIVE` or `CACHED/OFFLINE`);
- snapshot/build timestamp;
- human-readable age;
- the live refresh failure reason when fallback occurred.

Cached data is never presented without freshness. A missing or invalid cache plus failed refresh produces an actionable startup error screen with retry and runbook guidance; it does not initialize an empty or misleading player board.

## 6. Streamlit Boundaries and Performance

Core lifecycle, persistence, validation, completion, and snapshot operations remain outside Streamlit. The UI calls these services and renders structured outcomes.

Session state records lifecycle authorization and caches one base-ranking DataFrame. Per-pick reruns load and validate the small JSON state and reuse rankings; they do not call upstream services or rebuild projections. Existing available-player filtering and assistant scoring remain unchanged.

UI failures are caught at service boundaries and rendered with an error message, relevant artifact paths, and safe actions. Tracebacks or validation detail may be placed in an expander, but the primary message states what happened and what the operator can do.

## 7. Dependencies and Runbook

Add a conventional dependency manifest suitable for a Python/Streamlit application. Versions are pinned to the verified draft-night environment, including direct runtime and test dependencies needed to reproduce the suite. The manifest does not alter ranking configuration.

The README or a dedicated draft-night runbook documents:

- supported Python version;
- environment creation and dependency installation;
- exact launch command from repository root;
- expected lifecycle screen and pre-draft checks;
- how to start, resume, archive, and recover a draft;
- archive, authoritative, backup, and rankings snapshot locations;
- what LIVE versus CACHED/OFFLINE means;
- recovery when live refresh times out;
- recovery when authoritative state is malformed;
- recovery when both authoritative and backup state are invalid;
- how to preserve artifacts for diagnosis;
- the verification command to run before draft night.

No instruction tells the operator to delete, reset, clean, stash, or manually overwrite live state.

## 8. Test Strategy

All behavior is developed with strict RED -> GREEN TDD. Each production change begins with a focused test that fails for the expected missing behavior, followed by the minimum implementation and focused green verification.

Coverage includes:

- lifecycle gate never silently resumes existing state;
- Start New Draft archives all old artifacts before creating fresh state;
- fresh initialization reloads canonical keeper reservations;
- archive or initialization failure preserves existing artifacts;
- schema migration requires explicit lifecycle action;
- valid state round-trips through atomic persistence;
- interrupted write/replacement preserves the last authoritative or backup copy;
- malformed authoritative state falls back only through visible explicit recovery;
- invalid backup is rejected;
- all structural and snake-ownership validation rules;
- pick 180 completion and core rejection of pick 181;
- completion UI and disabled draft actions;
- undo after completion reopens the draft;
- bounded live refresh and cached fallback;
- visible source, timestamp, age, and failure reason;
- invalid or absent cache yields an actionable startup error;
- existing War Room performance expectations remain green.

## 9. Full 180-Slot Drunk Sundays Proof

An end-to-end automated simulation uses the canonical Drunk Sundays league profile and actual keeper declarations. It:

1. Starts a fresh draft through the lifecycle service.
2. Confirms every keeper reservation matches canonical owner, round, slot, and overall pick.
3. Records a unique available player for every non-keeper slot.
4. Verifies ownership at every pick and both sides of every snake boundary.
5. Restarts from authoritative persisted state during the draft.
6. Simulates malformed authoritative state in an isolated temporary directory and explicitly recovers from last-known-good backup.
7. Exercises undo across a keeper boundary and resumes correctly.
8. Accounts for exactly 180 slots and exactly 15 rostered players per fantasy team.
9. Verifies all manual and keeper player names are unique.
10. Completes at `current_pick == 181` with status complete.
11. Proves a further pick is rejected without mutation.
12. Undoes the final manual pick, verifies active status and the reopened slot, then re-records it to complete again.

The simulation never writes to the repository's live state artifact.

## 10. Scope Boundaries

This work does not:

- change projection formulas;
- change VORP replacement ranks;
- change tier calibration or ranking weights;
- boost or penalize any position or player manually;
- modify the canonical Drunk Sundays draft order;
- change keeper declarations or keeper-cost rules;
- add Yahoo or Sleeper live draft synchronization;
- merge to main or push without explicit user direction;
- remove or overwrite existing rehearsal/live artifacts without the safe archive transaction.

## Acceptance Criteria

The hardening is complete only when:

- the original 205-test baseline remains green;
- all new lifecycle, persistence, completion, offline, UI, and simulation tests pass;
- the full suite passes with zero failures;
- the independent whole-branch review has no unresolved Critical or Important findings;
- the 180-slot simulation passes with canonical ownership and keepers;
- fresh verification shows pick 181 rejection and final-pick undo/recompletion;
- the runbook can launch the War Room and recover both network and state failures without deleting artifacts;
- the final report lists commits, exact test counts, simulation evidence, recovery scenarios, offline behavior, review findings and fixes, remaining risks, and a go/no-go recommendation.
