# EdgeIQ Live War Room UI Design

Date: 2026-08-19
Branch: `live-war-room-core`
Status: Approved design, pending implementation plan

## Goal

Build the smallest reliable laptop-first Streamlit War Room for live fantasy drafts. The UI must sit on top of the already-tested `fantasy_draft_model.live_war_room` state engine instead of reimplementing draft logic.

The first usable version is optimized for a laptop at the draft table: fast scanning, fast player entry, clear current-pick context, and a safe undo path.

## Scope

Task 5A includes:

- Current pick, round, on-the-clock fantasy team, and user team at the top.
- Searchable/filterable available-player board.
- EdgeIQ recommendation panel built from the existing draft-assistant ranking pipeline.
- Manual pick entry through the tested `record_manual_pick()` function.
- One-click undo through the tested `undo_last_manual_pick()` function.
- Recent-pick history.
- Automatic removal of drafted players and keepers from the available-player pool.
- Persistent JSON-backed War Room state that survives Streamlit reruns and browser refreshes.
- Desktop/laptop-first layout and controls.

Task 5A intentionally excludes:

- Full team-needs modeling.
- Run detector visualizations.
- "What If I Wait" simulation.
- Full player-card drilldowns.
- New pressure-meter logic.
- Mobile-first styling.
- Automatic Yahoo/Sleeper draft import.

Those can layer on after the manual-entry shell is proven reliable.

## Existing Components to Reuse

### `fantasy_draft_model/live_war_room.py`

This remains the single source of truth for live draft state and mutation. Streamlit must call the existing functions rather than duplicate their rules:

- `initialize_war_room()`
- `load_war_room_state()`
- `save_war_room_state()`
- `get_pick_context()`
- `record_manual_pick()`
- `undo_last_manual_pick()`
- keeper reservation/advancement helpers

### `fantasy_draft_model/draft_assistant.py`

Use `build_draft_assistant()` for the ranked EdgeIQ recommendation board. The UI may filter/display its DataFrame but must not create a competing ranking algorithm.

### Existing UI package

`fantasy_draft_model/ui/draft_war_room.py` and `fantasy_draft_model/ui/streamlit_app.py` are currently empty placeholders. They should become the user-facing Streamlit layer.

The older `draft_board.py` and `player_selection.py` terminal flows are reference behavior only; they should not remain the live interaction path.

## Architecture Options Considered

### Option A — Thin Streamlit shell over tested core (selected)

The Streamlit page owns only presentation, filtering, selection, and rerun control. All live state mutation goes through `live_war_room.py`.

Advantages:

- Lowest regression risk.
- Fastest route to a usable draft-day tool.
- Clear separation between UI and draft rules.
- Existing core tests continue to protect snake order, keeper behavior, duplicate protection, persistence, and undo.

Tradeoff:

- Some richer UI behavior waits until later tasks.

### Option B — Put draft logic directly inside Streamlit

Advantages:

- Fewer modules in the short term.

Rejected because:

- Duplicates tested backend logic.
- Streamlit rerun semantics make state mutation easier to get wrong.
- Raises regression risk under draft-day time pressure.

### Option C — Build a richer dashboard layer first

Advantages:

- More polished first impression.

Rejected because:

- Adds roster-needs, run detection, scenario tools, and larger UI state before the core manual-entry workflow is proven in-browser.
- Slower and riskier for the immediate draft deadline.

## Component Design

### 1. Streamlit entrypoint

`fantasy_draft_model/ui/streamlit_app.py`

Responsibilities:

- Configure the page for wide layout.
- Select/resolve the league.
- Initialize state if no persisted state exists.
- Load rankings once per appropriate Streamlit cache boundary.
- Call the War Room renderer.

It should not contain snake-draft math or direct JSON mutation.

### 2. War Room renderer

`fantasy_draft_model/ui/draft_war_room.py`

Responsibilities:

- Render top pick-context metrics.
- Build the current available-player view.
- Render search and position filters.
- Render the selected player and Record Pick control.
- Render Undo Last Pick control.
- Render EdgeIQ recommendations.
- Render recent history.
- Trigger a Streamlit rerun after successful state mutation.
- Convert backend `ValueError` messages into visible UI errors without corrupting state.

### 3. Available-player derivation

The UI derives unavailable names from:

- `state["manual_picks"]`
- `state["keeper_reservations"]`

Those names are normalized consistently with the backend and removed from the ranking DataFrame before filtering/display.

This derivation is read-only; it does not alter the ranking DataFrame or persisted state.

### 4. Recommendation derivation

The recommendation panel starts from `build_draft_assistant(league_key, draft_context=...)`.

For Task 5A, `draft_context` should contain only information already trustworthy and cheap to derive, especially current pick context / picks-until-user if available. Rich roster/run intelligence is deferred.

Drafted/keeper players are removed from the recommendation DataFrame using the same availability filter as the main board.

## Laptop-First Layout

Use Streamlit wide mode.

Top row:

- Overall Pick
- Round
- On the Clock
- Your Team

Main body:

- Left, approximately 65% width: Available Players
- Right, approximately 35% width: EdgeIQ Recommendations

Available Players controls:

- Search text box.
- Position filter with Overall, RB, WR, TE, QB, K, DEF.
- Compact table/dataframe showing the most important columns first.

Selection workflow:

1. Search/filter.
2. Select one player.
3. Show a compact confirmation summary.
4. Click Record Pick.
5. Backend records the pick and persists.
6. UI reruns and immediately advances to the next non-keeper pick.

Undo should remain visible near the top or directly under the pick-entry controls so a wrong click can be corrected quickly.

Recent Picks appears below the main panels and shows newest picks first.

## Display Columns

Available board should prefer these fields when present:

- `player_name_clean`
- `position`
- `team`
- `bye_week`
- `draft_rank`
- `position_rank_label`
- `tier`
- `vorp`
- `edgescore`
- `brain_score`

The renderer must tolerate missing optional columns rather than fail.

Recommendation panel should prefer:

- player name
- position
- NFL team
- tier
- VORP / EdgeScore
- brain score
- recommendation
- reasons/warnings where compact display is practical

## State and Rerun Rules

- Persisted JSON state remains authoritative across browser refreshes.
- Streamlit session state may hold ephemeral UI choices, but not authoritative draft state.
- Record and undo actions call backend functions exactly once per button event.
- After a successful mutation, call Streamlit rerun so all panels rebuild from persisted/current state.
- Do not mutate `current_pick`, `manual_picks`, keeper lists, or processed keeper picks directly in the UI.

## Error Handling

### Backend validation errors

Examples include duplicate draft attempts or undo with no manual history.

Behavior:

- Catch `ValueError` at the UI boundary.
- Display the message clearly.
- Do not rerun as though the mutation succeeded.

### State file missing

If no live state file exists, initialize a fresh War Room for the selected league.

### Rankings failure

If ranking construction fails, show a visible error and preserve the live state. The user should still be able to see state/history; pick recording should not silently proceed from a broken/empty player source.

### Optional-column absence

Hide unavailable display columns instead of crashing.

## Testing Strategy

Implementation follows TDD.

### Pure UI-helper tests

Prefer extracting small pure helpers from the renderer for testability, including:

- unavailable-player-name set construction
- available-player filtering
- position/search filtering
- display-column selection
- recent-history shaping/order

These tests should not require launching a browser.

### Integration boundary tests

Use monkeypatch/fakes where appropriate to verify that UI action helpers:

- call `record_manual_pick()` with the selected player and state path
- call `undo_last_manual_pick()`
- do not directly mutate protected backend state before those calls

### Regression gates

For each step:

1. New RED tests fail for the intended missing behavior.
2. Minimum GREEN implementation.
3. Targeted UI/War Room tests pass.
4. Existing `tests/test_live_war_room_core.py` remains green.
5. Full `python -m pytest -q` remains green before the task is considered complete.

## Implementation Sequence

Task 5A should be built in small slices:

1. Pure helper layer for availability/filtering/history.
2. Minimal Streamlit shell and top pick-context row.
3. Available-player board and selection control.
4. Record Pick integration.
5. Undo integration.
6. EdgeIQ recommendation panel.
7. Recent-pick history.
8. Local Streamlit launch and laptop-screen smoke test.
9. Full regression suite.

## Success Criteria

Task 5A is complete only when, on a laptop browser:

- The correct league and current pick context appear.
- A player can be found quickly by search or position.
- Recording a player assigns the correct fantasy team through the backend and advances the draft.
- Keepers are skipped automatically through the backend.
- Drafted players and keepers disappear from both available and recommendation boards.
- Duplicate recording is blocked safely.
- Undo restores the previous live position, including keeper-crossing behavior.
- Refreshing the browser does not erase draft progress.
- Recent picks are visible and accurate.
- Existing War Room core tests and the full project test suite remain green.

## Deferred Follow-On Work

After Task 5A is proven stable:

- Team roster panels and positional needs.
- Run monitor.
- "Managers before your pick."
- "What If I Wait."
- Tier pressure / scarcity visuals.
- Roster fit and bye fit.
- Player cards.
- Reach/steal alerts.
- Printable/PDF emergency board integration.
- Mobile polish.
