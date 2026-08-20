# EdgeIQ Draft-Night Runbook

This runbook is for the Windows operator running the Drunk Sundays War Room
from a clean checkout. It describes the supported, evidence-preserving path
through startup, draft lifecycle choices, rankings refresh, and recovery.

## Invariants

The application owns draft-state and rankings artifacts. Operators must not delete,
reset, clean, stash, or manually overwrite those artifacts. Operators must not manually overwrite
repair JSON or CSV by hand. Every recovery action must leave the original
bytes available for diagnosis. If escalation is needed, copy diagnostic
artifacts into a new, uniquely named folder before asking for help.

## Artifact locations

All paths below are relative to the repository root:

| Artifact | Path |
| --- | --- |
| Authoritative draft state | `fantasy_draft_model/data/live_war_room_state.json` |
| Last-known-good state backup | `fantasy_draft_model/data/live_war_room_state.backup.json` |
| Recovery metadata | `fantasy_draft_model/data/live_war_room_state.recovery.json` |
| Verified state archives | `fantasy_draft_model/data/archives/` |
| Rankings snapshot pointer/metadata | `fantasy_draft_model/data/war_room_rankings.json` |
| Rankings snapshot generations | `fantasy_draft_model/data/war_room_rankings.<generation>.csv` |

The archive path is shown by the UI after **Start New Draft** and in lifecycle
errors. Archives are timestamped and use non-overwriting names. Keep the
authoritative file, backup, recovery metadata, snapshot metadata, and every
snapshot generation together when collecting diagnostics.

## Preflight

1. Open PowerShell at the repository root and confirm that the checkout is
   the intended version.
2. Confirm Python 3.14.6:

   ```powershell
   py -3.14 --version
   ```

3. Create the virtual environment only when `.venv\Scripts\python.exe` is
   absent. If it exists, inspect its version rather than recreating it:

   ```powershell
   if (-not (Test-Path .venv\Scripts\python.exe)) { py -3.14 -m venv .venv }
   .\.venv\Scripts\python.exe --version
   ```

   The expected version is `Python 3.14.6`.

4. Install the exact pinned direct dependencies and verify consistency:

   ```powershell
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   .\.venv\Scripts\python.exe -m pip check
   ```

   `requirements.txt` is intentionally pinned. Do not loosen a version to
   work around a draft-night failure; record the error and escalate it.

5. Before draft night, run the full suite from the repository root:

   ```powershell
   .\.venv\Scripts\python.exe -m pytest -q
   ```

## Start the War Room

Launch the application with this exact command from the repository root:

```powershell
.\.venv\Scripts\python.exe -m streamlit run fantasy_draft_model/ui/streamlit_app.py
```

The first screen is the lifecycle gate. It must show a draft identity,
status, accounted slots, timestamps, and the state artifact path before the
player board is authorized. Do not record a pick until the lifecycle choice
and rankings source are understood.

## Lifecycle gate

### Start New Draft

Choose **Start New Draft** when the displayed draft is not the intended draft
or when both state copies are unusable and a fresh canonical draft is needed.
The application inspects the authoritative state, backup, and recovery
metadata, copies any present artifacts into a verified timestamped archive,
loads the canonical Drunk Sundays league and keepers, atomically creates a
fresh validated state, and reloads it before authorization. Check the success
message for the verified archive path. If initialization fails, leave every
artifact in place and preserve the displayed error for escalation.

### Resume

Choose **Resume Draft** only after checking the displayed draft identifier,
league, status, slot count, and update age. Resume is enabled only for a
validated authoritative state (or an explicitly recovered state). A stale or
complete draft can still be resumed for review; the UI must visibly show its
age/status. Never infer that an old state is the correct draft merely because
it exists.

### Corrupt authoritative state with a valid backup

If the gate reports a corrupt authoritative state and says a validated backup
is available, choose **Recover Backup**. The application archives the corrupt
authoritative bytes under `fantasy_draft_model/data/archives/`, atomically
restores the validated backup, verifies it, and returns to the lifecycle gate.
Do not touch either state file. If recovery fails, keep both copies and copy
the diagnostics before escalation.

### both copies invalid

If both the authoritative state and its backup are invalid, the app must not
invent picks or silently repair either copy. Keep both files unchanged, copy
them and the recovery metadata into a new diagnostic folder, and record the
errors shown for each copy. After the evidence is preserved, use **Start New
Draft** only if the league owner authorizes a fresh draft; its archive step
preserves the available malformed bytes before creating a new canonical
state. If a prior draft must be recovered, stop and escalate with the copied
artifacts instead.

## Rankings network and offline cache recovery

At startup the app bounds live rankings refresh. A successful refresh is
labelled `LIVE` and writes a validated CSV generation plus JSON metadata. If
the live source times out or is unavailable, the app loads the latest
checksum-verified snapshot and labels it `CACHED/OFFLINE`; it also displays
the live failure reason. Wait for the startup result rather than restarting
the browser repeatedly.

Before the first pick, confirm the displayed rankings source, creation
timestamp, and age. Treat cache freshness as an explicit operator check:
`LIVE` is the current refresh, while `CACHED/OFFLINE` is the timestamped
last-known-good snapshot. Do not present an old cache as live data or change
the snapshot timestamp by hand.

If the live refresh fails and a valid offline cache exists, continue only
after recording the `CACHED/OFFLINE` status and failure reason. Restore network
connectivity and use the UI **Retry** control when a current refresh is
required. If the live source fails and the cache is missing, malformed, or
checksum-invalid, the UI reports that no usable rankings are available; do
not record picks until connectivity or a validated cache is restored.

## artifact preservation and escalation

When a failure needs escalation, first create a new uniquely named diagnostic
folder outside the repository's live artifact paths. Copy, without editing,
the authoritative state, backup, recovery metadata, rankings JSON pointer,
the referenced rankings CSV generation, the UI error text, and the relevant
terminal output. Preserve the archive directory if recovery or Start New
Draft already created one. Copy into a new destination and confirm the copied
files are readable; do not copy over an existing diagnostic set. Include the
Python version, `pip check` output, rankings source/age, and the draft ID in
the report. The operator must copy diagnostic artifacts before escalation, not after a second
attempt has changed the evidence.

Only after those copies are secured should the operator contact the maintainer
or decide whether an authorized **Start New Draft** is appropriate. Never
delete or manually overwrite live state/cache artifacts while investigating.
