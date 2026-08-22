# EdgeIQ Draft-Night Runbook

This runbook is the supported Windows operating procedure for the 2026 Drunk Sundays War Room. Draft night uses the committed immutable player baseline plus the deterministic offline K/DEF supplement. It does **not** rebuild rankings from live data.

## Invariants

The application owns draft-state and frozen ranking artifacts. Operators **must not delete** state, backup, recovery, archive, frozen CSV, or manifest files. Operators **must not manually overwrite** JSON or CSV artifacts. Do not run cleanup commands against the repository while a draft is in progress.

The verified skill-position baseline is the committed **frozen snapshot**. The production startup **fails closed** if that snapshot or manifest is missing, malformed, or checksum-invalid. A mutable `war_room_rankings.csv/json` cache is not an authorized substitute.

K/DEF are deterministic offline supplemental entries. They are draftable, searchable, filterable, persistent, and undoable, but they do not receive fake frozen ranks. Until verified component projections are committed, K/DEF league-adjusted Draft Brain value is intentionally withheld rather than fabricated.

## Approved post-draft modeling follow-up

This frozen 2026 board uses verified current depth-chart roles and conservative role-cohort workload translation for material veteran RB role transitions. It does **not** yet model reliable team-level vacated workload, expected snap share, route participation, coaching/play-caller or scheme changes, team pace, or projected play volume. It also lacks a validated historical pre-season depth/roster calibration set for converting current backfield competition into a numerical RB opportunity-share forecast. Those inputs remain a post-draft architecture and data-quality project; no speculative bonuses are applied to the frozen board.

## Artifact locations

All paths are relative to the repository root.

| Artifact | Path |
| --- | --- |
| Authoritative draft state | `fantasy_draft_model/data/live_war_room_state.json` |
| Last-known-good backup | `fantasy_draft_model/data/live_war_room_state.backup.json` |
| Recovery metadata | `fantasy_draft_model/data/live_war_room_state.recovery.json` |
| Verified state archives | `fantasy_draft_model/data/archives/` |
| Frozen Top 300 CSV | `fantasy_draft_model/data/frozen/2026/edgeiq-top-300-2026.csv` |
| Frozen manifest | `fantasy_draft_model/data/frozen/2026/edgeiq-top-300-2026.manifest.json` |
| Offline K/DEF source | `fantasy_draft_model/models/special_teams.py` |

Verified frozen Top 300 SHA-256:

`e79f4ea672f5a08b81d3a89ac2ed1e8ac38f6b714127bf1df81b44d8e17d245b`

## Preflight

1. Open PowerShell at the repository root and confirm you are on the approved production commit/branch.
2. Confirm Python 3.14.6:

   ```powershell
   py -3.14 --version
   ```

3. Create the virtual environment only if it is missing, then confirm its version:

   ```powershell
   if (-not (Test-Path .venv\Scripts\python.exe)) { py -3.14 -m venv .venv }
   .\.venv\Scripts\python.exe --version
   ```

4. Install pinned dependencies and verify consistency:

   ```powershell
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   .\.venv\Scripts\python.exe -m pip check
   ```

5. Run the complete test suite before draft night:

   ```powershell
   .\.venv\Scripts\python.exe -m pytest -q
   ```

6. Do not regenerate player rankings or alter the frozen CSV/manifest during preflight.

## Start the War Room

Launch production with this exact command:

```powershell
.\.venv\Scripts\python.exe -m streamlit run fantasy_draft_model/ui/frozen_streamlit_app.py
```

The first screen is the lifecycle gate. Do not record a pick until you have chosen the correct lifecycle action and the authorized board reports `FROZEN/OFFLINE`.

After authorization, confirm:

- Rankings source is `FROZEN/OFFLINE`.
- The player baseline is the immutable Top 300.
- K and DEF are visible as supplemental offline entries when filtered/searched.
- K/DEF do not display a fake frozen rank.
- The current pick, next BLKWDW'S pick, and picks-until-user are sensible.

## Lifecycle gate

### Start New Draft

Choose **Start New Draft** only when beginning the real Drunk Sundays draft or after an explicitly authorized reset. The application archives any existing draft artifacts before creating a fresh canonical state with current keeper reservations. Verify the displayed archive path after the action completes.

### Resume

Choose **Resume Draft** after confirming the displayed draft identity, league, lifecycle status, accounted slot count, and update age. Resume uses the persisted authoritative draft state; the frozen player baseline and deterministic K/DEF supplement are reconstructed independently and offline.

### corrupt authoritative state with a valid backup

If the lifecycle gate reports a **corrupt authoritative** state and a validated backup is available, choose **Recover Backup**. Recovery archives the corrupt authoritative bytes before restoring the validated backup. Do not edit either file manually.

### both copies invalid

If **both copies invalid** is the situation (authoritative and backup both fail validation), the app must not invent selections or silently repair data. Preserve both files and the recovery metadata. Only use **Start New Draft** after the available evidence has been archived and a fresh draft is explicitly authorized.

## Frozen rankings and offline behavior

Draft-night production never requires `build_draft_rankings()` and never requires a live data refresh. Startup validates the committed frozen CSV and manifest, including the verified checksum, before authorizing the board.

If frozen validation fails, the War Room **fails closed**. Do not fall back to `war_room_rankings.csv`, `war_room_rankings.json`, a 635-player live cache, or a newly generated board. Restore the committed frozen files from the approved repository state before recording picks.

The K/DEF supplement is built from committed deterministic source data and valid bye weeks. These rows participate in availability, search, position filters, Record Pick, Undo, Save/Resume, and final draft history. They remain separate from frozen rank 1-300.

Because Drunk Sundays has unusually valuable DEF scoring, do not assume defense is a last-round-only position. However, the production assistant must also not invent DEF value. Until verified component projections are committed, the War Room shows defenses as supplemental draftable options without fabricated Draft Brain scores.

## During the draft

- Record the real Yahoo selection immediately after it happens.
- Confirm the selected player disappears from availability.
- Keeper slots advance automatically when encountered; do not manually draft a reserved keeper.
- Use **Undo Last Pick** only to correct the most recent manual entry.
- After any browser restart, use **Resume Draft** and verify current pick/history before continuing.
- Do not refresh player data or regenerate rankings during the draft.

## Completion

At the end of the draft, the UI must remain viewable after the final pick. `picks_until_user=None` after the user's final turn is valid endgame state and must not crash the assistant. Keep the final authoritative state and its backups/archive intact.

## artifact preservation and escalation

If a failure requires escalation, create a new uniquely named diagnostic folder outside the live artifact paths and **copy diagnostic artifacts** into it before trying another recovery action. Preserve, without editing:

- authoritative draft state;
- backup and recovery metadata;
- relevant archive directory;
- frozen CSV and manifest;
- terminal/test output;
- the exact UI error text;
- Python and dependency versions.

Do not copy over an existing diagnostic set. The operator must preserve evidence before a second action can change it.

Repository reference: https://github.com/phizucked8313/EdgeSportsLab
