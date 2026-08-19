# EdgeIQ Live War Room Core Design

## Goal

Build a reliable manual-entry live draft state engine for an in-person fantasy draft. The War Room core must track the real snake draft, keepers, every team's roster, available players, EdgeIQ recommendations, undo/reset, and persistent local state without introducing a second ranking system.

## Source of truth

- League identity, team count, draft rounds, roster size, and draft order come from `fantasy_draft_model/models/league_profile.py`.
- Keeper declarations come from `fantasy_draft_model/keepers.py`.
- Player rankings and live recommendations come from `fantasy_draft_model/draft_assistant.py::build_draft_assistant(league_key, draft_context)`.
- Snake-pick math comes from `fantasy_draft_model/engines/snake_draft_engine.py`.
- The stale `models/league_manager.py` and legacy `draft_state.py` are not dependencies of the new War Room core.

## State model

The state is league-specific JSON and contains:

- schema version
- league name and league key
- user team
- current overall pick
- manual draft picks
- keeper reservations
- processed keeper-slot pick numbers

All declared keepers are unavailable from the beginning and appear on their fantasy team's roster from the beginning. When the live draft reaches a keeper's reserved pick, the engine automatically advances past that pick and records the keeper slot as processed; the user never manually enters a keeper selection.

## Manual pick flow

For each non-keeper pick:

1. Determine round, snake slot, and fantasy team on the clock from the current overall pick.
2. Build the available EdgeIQ board using the current `picks_until_user` context.
3. Validate that the selected player is still available.
4. Record player name, NFL position/team/bye, fantasy team, overall pick, round, and draft slot.
5. Increment the current pick.
6. Automatically advance through any keeper-reserved picks that immediately follow.
7. Persist state atomically.

The fantasy team is derived from draft order; normal live entry does not ask the user to choose an owner.

## Board and roster snapshot

The War Room exposes a front-end-safe snapshot containing:

- current pick banner data
- team on the clock
- next user pick and picks until user
- available EdgeIQ board with Draft Brain / Pressure outputs
- recent draft history
- all team rosters
- user roster
- keeper indicators

Available players exclude both all keepers and all manually drafted players.

## Recovery behavior

`undo_last_pick()` removes the most recent manual selection, rolls the current pick back to that pick number, and un-processes keeper slots after that point so they can replay correctly. Keepers themselves are never deleted by undo.

`reset_war_room()` restores an empty manual draft while retaining the league's declared keepers and correct first live pick.

State writes use a temporary file followed by replace so a partial write does not corrupt the draft.

## User team identity

The canonical league profile will include `user_team` for both leagues so the War Room does not depend on the older duplicate league-manager configuration.

## Scope boundary

This project builds the live War Room **core only**. It does not build Streamlit yet. Once this engine survives targeted tests, the full regression suite, and a complete simulated draft, the Streamlit UI will consume this API without owning draft logic.

## Success criteria

- Drunk Sundays starts with the verified 12-team order and `BLKWDW'S` as the user team.
- Keeper players are unavailable immediately and appear on owner rosters immediately.
- Keeper pick slots auto-advance at the correct snake pick numbers.
- Manual selections always attach to the correct fantasy team.
- Every manual pick disappears from the available board exactly once.
- Undo and reset recover correctly.
- State survives reload from disk.
- A complete 15-round Drunk Sundays simulation reaches the end with all 180 draft slots accounted for (manual picks plus keeper slots), no duplicate players, and valid team rosters.
- Existing EdgeIQ tests remain green.
