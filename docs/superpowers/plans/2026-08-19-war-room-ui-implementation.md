# EdgeIQ Live War Room UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reliable laptop-first Streamlit War Room that displays current draft context, filters the EdgeIQ board, records/undoes manual picks through the tested backend, removes unavailable players, shows recommendations, and preserves draft progress across reruns.

**Architecture:** Keep Streamlit as a thin presentation layer. `fantasy_draft_model/live_war_room.py` remains the sole authority for draft-state mutation, while `fantasy_draft_model/ui/draft_war_room.py` owns pure UI helpers plus rendering and `fantasy_draft_model/ui/streamlit_app.py` owns page setup, league/state bootstrapping, and cached ranking construction. Pure helpers are tested without launching a browser; Streamlit itself is verified with a local smoke test after targeted and full pytest gates.

**Tech Stack:** Python 3, pandas, pytest, Streamlit, existing EdgeIQ ranking/draft-assistant pipeline.

**Spec:** `docs/superpowers/specs/2026-08-19-war-room-ui-design.md`

## Global Constraints

- Optimize Task 5A for a laptop/desktop browser in Streamlit wide mode.
- Do not duplicate snake order, keeper advancement, duplicate protection, persistence, or undo logic in the UI.
- All authoritative mutation must go through `fantasy_draft_model.live_war_room`.
- The first version must prioritize fast search/filter/select/record/undo over visual polish.
- Drafted players and keeper-reserved players must disappear from both available and recommendation views.
- Persisted JSON state is authoritative; Streamlit session state is only for ephemeral widget state.
- Optional ranking columns must be tolerated rather than treated as required.
- Do not add roster-needs modeling, run detection, What-If-I-Wait, player cards, mobile-first styling, or automatic Yahoo/Sleeper draft import in Task 5A.
- No Python dependency manifest exists on this branch as of this plan. Do not introduce packaging work in Task 5A; verify Streamlit in the active venv during the smoke-test task and install it locally only if import verification fails.

---

## File Structure

- `fantasy_draft_model/ui/draft_war_room.py`
  - Pure helper functions for unavailable names, filtering, display columns, and recent history.
  - Thin action wrappers that delegate record/undo to `live_war_room.py`.
  - Streamlit renderer for the top metrics, player board, actions, recommendation panel, and history.
- `fantasy_draft_model/ui/streamlit_app.py`
  - Streamlit page configuration.
  - League selector.
  - Per-league state-file path selection and initialize/load behavior.
  - Cached `build_draft_assistant()` call.
  - Calls `render_war_room()`.
- `tests/test_war_room_ui_helpers.py`
  - Browser-free tests for pure helpers and backend delegation wrappers.
- `tests/test_streamlit_war_room_bootstrap.py`
  - Browser-free tests for per-league state-path selection and state bootstrap behavior.

---

### Task 1: Available-player and history helper layer

**Files:**
- Modify: `fantasy_draft_model/ui/draft_war_room.py`
- Create: `tests/test_war_room_ui_helpers.py`

**Interfaces:**
- Consumes: pandas `DataFrame`; War Room `state: dict` with `manual_picks` and `keeper_reservations`.
- Produces:
  - `normalize_player_name(value) -> str`
  - `get_unavailable_player_names(state: dict) -> set[str]`
  - `filter_available_players(rankings: pd.DataFrame, state: dict) -> pd.DataFrame`
  - `apply_player_filters(players: pd.DataFrame, search_text: str = "", position: str = "Overall") -> pd.DataFrame`
  - `select_display_columns(frame: pd.DataFrame, preferred_columns: list[str]) -> list[str]`
  - `build_recent_history(state: dict, limit: int = 12) -> pd.DataFrame`

- [ ] **Step 1: Write RED tests for unavailable-player removal**

Add to `tests/test_war_room_ui_helpers.py`:

```python
import pandas as pd

from fantasy_draft_model.ui import draft_war_room


def _rankings():
    return pd.DataFrame(
        [
            {"player_name_clean": "Alpha WR", "position": "WR", "team": "CLE", "draft_rank": 1},
            {"player_name_clean": "Beta RB", "position": "RB", "team": "DET", "draft_rank": 2},
            {"player_name_clean": "Keeper TE", "position": "TE", "team": "KC", "draft_rank": 3},
        ]
    )


def test_filter_available_players_removes_manual_picks_and_keepers():
    state = {
        "manual_picks": [{"player_name": " alpha wr "}],
        "keeper_reservations": [{"player_name": "KEEPER TE"}],
    }

    available = draft_war_room.filter_available_players(_rankings(), state)

    assert available["player_name_clean"].tolist() == ["Beta RB"]
```

- [ ] **Step 2: Run the unavailable-player test and verify RED**

Run:

```bash
python -m pytest tests/test_war_room_ui_helpers.py::test_filter_available_players_removes_manual_picks_and_keepers -v
```

Expected: FAIL because `filter_available_players` does not exist.

- [ ] **Step 3: Implement normalization and unavailable-player filtering**

Add to `fantasy_draft_model/ui/draft_war_room.py`:

```python
import pandas as pd


def normalize_player_name(value):
    return str(value).strip().casefold()


def get_unavailable_player_names(state):
    names = {
        normalize_player_name(pick.get("player_name", ""))
        for pick in state.get("manual_picks", [])
        if pick.get("player_name")
    }
    names.update(
        normalize_player_name(reservation.get("player_name", ""))
        for reservation in state.get("keeper_reservations", [])
        if reservation.get("player_name")
    )
    return names


def filter_available_players(rankings, state):
    unavailable = get_unavailable_player_names(state)
    if not unavailable:
        return rankings.copy().reset_index(drop=True)

    mask = ~rankings["player_name_clean"].map(normalize_player_name).isin(unavailable)
    return rankings.loc[mask].copy().reset_index(drop=True)
```

- [ ] **Step 4: Run the unavailable-player test and verify GREEN**

Run:

```bash
python -m pytest tests/test_war_room_ui_helpers.py::test_filter_available_players_removes_manual_picks_and_keepers -v
```

Expected: PASS.

- [ ] **Step 5: Write RED tests for search/position filters, optional columns, and recent history**

Append:

```python
def test_apply_player_filters_combines_search_and_position():
    filtered = draft_war_room.apply_player_filters(
        _rankings(),
        search_text="beta",
        position="RB",
    )
    assert filtered["player_name_clean"].tolist() == ["Beta RB"]


def test_select_display_columns_ignores_missing_optional_columns():
    columns = draft_war_room.select_display_columns(
        _rankings(),
        ["player_name_clean", "position", "tier", "vorp", "draft_rank"],
    )
    assert columns == ["player_name_clean", "position", "draft_rank"]


def test_build_recent_history_returns_newest_manual_picks_first():
    state = {
        "manual_picks": [
            {"pick_number": 1, "round": 1, "fantasy_team": "A", "player_name": "One", "position": "WR"},
            {"pick_number": 2, "round": 1, "fantasy_team": "B", "player_name": "Two", "position": "RB"},
        ]
    }
    history = draft_war_room.build_recent_history(state, limit=10)
    assert history["pick_number"].tolist() == [2, 1]
```

- [ ] **Step 6: Run the three helper tests and verify RED**

Run:

```bash
python -m pytest \
  tests/test_war_room_ui_helpers.py::test_apply_player_filters_combines_search_and_position \
  tests/test_war_room_ui_helpers.py::test_select_display_columns_ignores_missing_optional_columns \
  tests/test_war_room_ui_helpers.py::test_build_recent_history_returns_newest_manual_picks_first -v
```

Expected: FAIL because the helpers do not exist.

- [ ] **Step 7: Implement the three helpers**

Add:

```python
def apply_player_filters(players, search_text="", position="Overall"):
    filtered = players.copy()

    search_text = str(search_text).strip().casefold()
    if search_text:
        filtered = filtered[
            filtered["player_name_clean"]
            .fillna("")
            .astype(str)
            .str.casefold()
            .str.contains(search_text, regex=False)
        ]

    if position and position != "Overall":
        filtered = filtered[filtered["position"] == position]

    return filtered.reset_index(drop=True)


def select_display_columns(frame, preferred_columns):
    return [column for column in preferred_columns if column in frame.columns]


def build_recent_history(state, limit=12):
    picks = list(state.get("manual_picks", []))[-limit:]
    picks.reverse()
    return pd.DataFrame(picks)
```

- [ ] **Step 8: Run the full helper test file**

Run:

```bash
python -m pytest tests/test_war_room_ui_helpers.py -v
```

Expected: all Task 1 tests PASS.

- [ ] **Step 9: Commit Task 1**

```bash
git add fantasy_draft_model/ui/draft_war_room.py tests/test_war_room_ui_helpers.py
git commit -m "Add War Room UI data helpers"
```

---

### Task 2: Safe backend delegation wrappers

**Files:**
- Modify: `fantasy_draft_model/ui/draft_war_room.py`
- Modify: `tests/test_war_room_ui_helpers.py`

**Interfaces:**
- Consumes: `state: dict`, selected pandas row/Series, `state_path`.
- Produces:
  - `record_selected_player(state, player_row, state_path)` -> backend pick dict.
  - `undo_last_pick(state, state_path)` -> removed backend pick dict.
- Delegates to:
  - `fantasy_draft_model.live_war_room.record_manual_pick(state, player_row, state_path=...)`
  - `fantasy_draft_model.live_war_room.undo_last_manual_pick(state, state_path=...)`

- [ ] **Step 1: Write RED delegation tests**

Append:

```python
def test_record_selected_player_delegates_to_war_room_core(monkeypatch, tmp_path):
    state = {"current_pick": 1}
    player = pd.Series({"player_name_clean": "Alpha WR"})
    called = {}

    def fake_record(fake_state, fake_player, state_path):
        called["state"] = fake_state
        called["player"] = fake_player
        called["state_path"] = state_path
        return {"player_name": "Alpha WR"}

    monkeypatch.setattr(draft_war_room.war_room_core, "record_manual_pick", fake_record)

    result = draft_war_room.record_selected_player(state, player, tmp_path / "state.json")

    assert result["player_name"] == "Alpha WR"
    assert called["state"] is state
    assert called["player"] is player


def test_undo_last_pick_delegates_to_war_room_core(monkeypatch, tmp_path):
    state = {"manual_picks": [{"player_name": "Alpha WR"}]}

    def fake_undo(fake_state, state_path):
        assert fake_state is state
        return {"player_name": "Alpha WR"}

    monkeypatch.setattr(draft_war_room.war_room_core, "undo_last_manual_pick", fake_undo)

    removed = draft_war_room.undo_last_pick(state, tmp_path / "state.json")
    assert removed["player_name"] == "Alpha WR"
```

- [ ] **Step 2: Run delegation tests and verify RED**

Run:

```bash
python -m pytest tests/test_war_room_ui_helpers.py -k "record_selected_player or undo_last_pick" -v
```

Expected: FAIL because the wrapper functions/module alias do not exist.

- [ ] **Step 3: Implement thin delegation wrappers**

At the top of `draft_war_room.py` import:

```python
from fantasy_draft_model import live_war_room as war_room_core
```

Add:

```python
def record_selected_player(state, player_row, state_path):
    return war_room_core.record_manual_pick(
        state,
        player_row,
        state_path=state_path,
    )


def undo_last_pick(state, state_path):
    return war_room_core.undo_last_manual_pick(
        state,
        state_path=state_path,
    )
```

- [ ] **Step 4: Run delegation tests and verify GREEN**

Run:

```bash
python -m pytest tests/test_war_room_ui_helpers.py -k "record_selected_player or undo_last_pick" -v
```

Expected: PASS.

- [ ] **Step 5: Run core + helper regression tests**

Run:

```bash
python -m pytest tests/test_live_war_room_core.py tests/test_war_room_ui_helpers.py -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit Task 2**

```bash
git add fantasy_draft_model/ui/draft_war_room.py tests/test_war_room_ui_helpers.py
git commit -m "Delegate War Room UI actions to core"
```

---

### Task 3: Per-league Streamlit state bootstrap

**Files:**
- Modify: `fantasy_draft_model/ui/streamlit_app.py`
- Create: `tests/test_streamlit_war_room_bootstrap.py`

**Interfaces:**
- Consumes: `league_key: str`, optional base directory for tests.
- Produces:
  - `get_state_path(league_key: str, data_dir=None) -> Path`
  - `load_or_initialize_state(league_key: str, state_path: Path) -> dict`
- Delegates to `live_war_room.load_war_room_state()` and `live_war_room.initialize_war_room()`.

- [ ] **Step 1: Write RED bootstrap tests**

Create `tests/test_streamlit_war_room_bootstrap.py`:

```python
from fantasy_draft_model.ui import streamlit_app


def test_get_state_path_is_scoped_by_league(tmp_path):
    drunk = streamlit_app.get_state_path("drunk_sundays", data_dir=tmp_path)
    related = streamlit_app.get_state_path("somewhat_related", data_dir=tmp_path)

    assert drunk.name == "live_war_room_state_drunk_sundays.json"
    assert related.name == "live_war_room_state_somewhat_related.json"
    assert drunk != related


def test_load_or_initialize_state_initializes_missing_file(monkeypatch, tmp_path):
    state_path = tmp_path / "state.json"
    called = {}

    def fake_initialize(league_key, state_path):
        called["league_key"] = league_key
        called["state_path"] = state_path
        return {"league_key": league_key, "current_pick": 1}

    monkeypatch.setattr(streamlit_app.war_room_core, "initialize_war_room", fake_initialize)

    state = streamlit_app.load_or_initialize_state("drunk_sundays", state_path)

    assert state["league_key"] == "drunk_sundays"
    assert called["state_path"] == state_path


def test_load_or_initialize_state_loads_existing_matching_file(monkeypatch, tmp_path):
    state_path = tmp_path / "state.json"
    state_path.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        streamlit_app.war_room_core,
        "load_war_room_state",
        lambda path: {"league_key": "drunk_sundays", "current_pick": 7},
    )

    state = streamlit_app.load_or_initialize_state("drunk_sundays", state_path)
    assert state["current_pick"] == 7
```

- [ ] **Step 2: Run bootstrap tests and verify RED**

Run:

```bash
python -m pytest tests/test_streamlit_war_room_bootstrap.py -v
```

Expected: FAIL because bootstrap helpers do not exist.

- [ ] **Step 3: Implement bootstrap helpers without importing Streamlit at module import time**

Add to `streamlit_app.py`:

```python
from pathlib import Path

from fantasy_draft_model import live_war_room as war_room_core


DEFAULT_DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def get_state_path(league_key, data_dir=None):
    base = Path(data_dir) if data_dir is not None else DEFAULT_DATA_DIR
    return base / f"live_war_room_state_{league_key}.json"


def load_or_initialize_state(league_key, state_path):
    state_path = Path(state_path)
    if not state_path.exists():
        return war_room_core.initialize_war_room(
            league_key,
            state_path=state_path,
        )

    state = war_room_core.load_war_room_state(state_path)
    if state.get("league_key") != league_key:
        raise ValueError(
            f"State file belongs to {state.get('league_key')!r}, not {league_key!r}"
        )
    return state
```

Keep `import streamlit as st` inside `main()` for now so bootstrap tests remain independent of Streamlit installation.

- [ ] **Step 4: Run bootstrap tests and verify GREEN**

Run:

```bash
python -m pytest tests/test_streamlit_war_room_bootstrap.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit Task 3**

```bash
git add fantasy_draft_model/ui/streamlit_app.py tests/test_streamlit_war_room_bootstrap.py
git commit -m "Add per-league War Room state bootstrap"
```

---

### Task 4: Laptop-first War Room renderer

**Files:**
- Modify: `fantasy_draft_model/ui/draft_war_room.py`
- Modify: `tests/test_war_room_ui_helpers.py`

**Interfaces:**
- Consumes:
  - `state: dict`
  - `rankings: pd.DataFrame`
  - `state_path: Path`
  - optional injected `st_module` for smoke/unit testing
- Produces:
  - `render_war_room(state, rankings, state_path, st_module=None) -> None`
- Uses existing helpers from Tasks 1-2.

- [ ] **Step 1: Write RED tests for pick-context display and renderer action wiring using a small fake Streamlit object**

Append a deliberately small fake to `tests/test_war_room_ui_helpers.py`:

```python
class FakeColumn:
    def __init__(self, owner):
        self.owner = owner

    def metric(self, label, value):
        self.owner.metrics.append((label, value))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeStreamlit:
    def __init__(self):
        self.metrics = []
        self.errors = []
        self.successes = []
        self.rerun_called = False
        self.session_state = {}

    def columns(self, spec):
        count = spec if isinstance(spec, int) else len(spec)
        return [FakeColumn(self) for _ in range(count)]

    def subheader(self, *args, **kwargs):
        pass

    def text_input(self, *args, **kwargs):
        return ""

    def selectbox(self, label, options, **kwargs):
        if label == "Position":
            return "Overall"
        return options[0] if options else None

    def dataframe(self, *args, **kwargs):
        pass

    def button(self, *args, **kwargs):
        return False

    def caption(self, *args, **kwargs):
        pass

    def info(self, *args, **kwargs):
        pass

    def error(self, message):
        self.errors.append(str(message))

    def success(self, message):
        self.successes.append(str(message))

    def rerun(self):
        self.rerun_called = True


def test_render_war_room_shows_current_pick_metrics(tmp_path):
    state = {
        "league_key": "drunk_sundays",
        "league_name": "Drunk Sundays",
        "user_team": "BLKWDW'S",
        "team_count": 12,
        "draft_rounds": 15,
        "current_pick": 16,
        "manual_picks": [],
        "keeper_reservations": [],
        "processed_keeper_picks": [],
    }
    fake_st = FakeStreamlit()

    draft_war_room.render_war_room(
        state,
        _rankings(),
        tmp_path / "state.json",
        st_module=fake_st,
    )

    assert ("Overall Pick", 16) in fake_st.metrics
    assert ("Round", 2) in fake_st.metrics
    assert ("On the Clock", "BLKWDW'S") in fake_st.metrics
    assert ("Your Team", "BLKWDW'S") in fake_st.metrics
```

- [ ] **Step 2: Run renderer metric test and verify RED**

Run:

```bash
python -m pytest tests/test_war_room_ui_helpers.py::test_render_war_room_shows_current_pick_metrics -v
```

Expected: FAIL because `render_war_room` does not exist.

- [ ] **Step 3: Implement the first renderer slice: top metrics + two-column shell + available table + selection widgets**

Add constants and renderer skeleton:

```python
AVAILABLE_COLUMNS = [
    "player_name_clean",
    "position",
    "team",
    "bye_week",
    "draft_rank",
    "position_rank_label",
    "tier",
    "vorp",
    "edgescore",
    "brain_score",
]

RECOMMENDATION_COLUMNS = [
    "player_name_clean",
    "position",
    "team",
    "tier",
    "vorp",
    "edgescore",
    "brain_score",
    "brain_recommendation",
    "brain_reasons",
    "brain_warnings",
]


def render_war_room(state, rankings, state_path, st_module=None):
    if st_module is None:
        import streamlit as st_module

    st = st_module
    context = war_room_core.get_pick_context(state)

    metric_columns = st.columns(4)
    metric_columns[0].metric("Overall Pick", context["pick_number"])
    metric_columns[1].metric("Round", context["round"])
    metric_columns[2].metric("On the Clock", context["fantasy_team"])
    metric_columns[3].metric("Your Team", state["user_team"])

    available = filter_available_players(rankings, state)

    left, right = st.columns([2, 1])
    with left:
        st.subheader("Available Players")
        search_text = st.text_input("Search player", key="war_room_search")
        position = st.selectbox(
            "Position",
            ["Overall", "RB", "WR", "TE", "QB", "K", "DEF"],
            key="war_room_position",
        )
        filtered = apply_player_filters(available, search_text, position)
        display_columns = select_display_columns(filtered, AVAILABLE_COLUMNS)
        st.dataframe(filtered[display_columns].head(50), use_container_width=True, hide_index=True)

        player_options = filtered["player_name_clean"].tolist()
        selected_name = st.selectbox(
            "Select player to record",
            player_options,
            index=None,
            placeholder="Choose a player",
            key="war_room_selected_player",
        ) if player_options else None

        if selected_name:
            selected_row = filtered.loc[
                filtered["player_name_clean"] == selected_name
            ].iloc[0]
            st.caption(
                f"{selected_row['player_name_clean']} | "
                f"{selected_row.get('position', '')} | "
                f"{selected_row.get('team', '')}"
            )

    with right:
        st.subheader("EdgeIQ Recommendations")
        recommendation_columns = select_display_columns(available, RECOMMENDATION_COLUMNS)
        st.dataframe(
            available[recommendation_columns].head(12),
            use_container_width=True,
            hide_index=True,
        )
```

Do not wire buttons yet; that is Step 5 after the initial renderer test passes.

- [ ] **Step 4: Run renderer metric test and helper regression tests**

Run:

```bash
python -m pytest tests/test_war_room_ui_helpers.py -v
```

Expected: PASS.

- [ ] **Step 5: Add record/undo controls with backend error handling and recent history**

Extend `render_war_room()` after selection is built:

```python
        if selected_name and st.button("Record Pick", type="primary", use_container_width=True):
            try:
                record_selected_player(state, selected_row, state_path)
            except ValueError as error:
                st.error(str(error))
            else:
                st.success(f"Recorded {selected_name}")
                st.rerun()

        if st.button("Undo Last Pick", use_container_width=True):
            try:
                removed = undo_last_pick(state, state_path)
            except ValueError as error:
                st.error(str(error))
            else:
                st.success(f"Undid {removed['player_name']}")
                st.rerun()
```

After the two main columns:

```python
    st.subheader("Recent Picks")
    history = build_recent_history(state)
    if history.empty:
        st.info("No manual picks recorded yet.")
    else:
        history_columns = select_display_columns(
            history,
            ["pick_number", "round", "fantasy_team", "player_name", "position", "nfl_team"],
        )
        st.dataframe(
            history[history_columns],
            use_container_width=True,
            hide_index=True,
        )
```

- [ ] **Step 6: Run UI helper + core tests**

Run:

```bash
python -m pytest tests/test_war_room_ui_helpers.py tests/test_live_war_room_core.py -v
```

Expected: all tests PASS.

- [ ] **Step 7: Commit Task 4**

```bash
git add fantasy_draft_model/ui/draft_war_room.py tests/test_war_room_ui_helpers.py
git commit -m "Build laptop War Room renderer"
```

---

### Task 5: Streamlit app entrypoint and EdgeIQ recommendation source

**Files:**
- Modify: `fantasy_draft_model/ui/streamlit_app.py`
- Modify: `tests/test_streamlit_war_room_bootstrap.py`

**Interfaces:**
- Consumes:
  - canonical league keys from `fantasy_draft_model.models.league_profile.LEAGUES`
  - `build_draft_assistant(league_key, draft_context={}) -> pd.DataFrame`
  - `render_war_room(state, rankings, state_path)`
- Produces:
  - `get_league_options() -> dict[str, str]` mapping display name to league key.
  - `main() -> None` Streamlit app.

- [ ] **Step 1: Write RED test for canonical league options**

Append to `tests/test_streamlit_war_room_bootstrap.py`:

```python
def test_get_league_options_uses_canonical_profiles():
    options = streamlit_app.get_league_options()
    assert options["Drunk Sundays"] == "drunk_sundays"
    assert options["Somewhat Related"] == "somewhat_related"
```

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
python -m pytest tests/test_streamlit_war_room_bootstrap.py::test_get_league_options_uses_canonical_profiles -v
```

Expected: FAIL because `get_league_options` does not exist.

- [ ] **Step 3: Implement canonical options and `main()`**

Update imports:

```python
from fantasy_draft_model.draft_assistant import build_draft_assistant
from fantasy_draft_model.models.league_profile import LEAGUES
from fantasy_draft_model.ui.draft_war_room import render_war_room
```

Add:

```python
def get_league_options():
    return {
        league["name"]: league["league_key"]
        for league in LEAGUES.values()
    }


def main():
    import streamlit as st

    st.set_page_config(
        page_title="EdgeIQ Live War Room",
        page_icon="🏈",
        layout="wide",
    )

    st.title("🏈 EdgeIQ Live War Room")

    league_options = get_league_options()
    display_name = st.sidebar.selectbox(
        "League",
        list(league_options.keys()),
        index=0,
    )
    league_key = league_options[display_name]
    state_path = get_state_path(league_key)

    try:
        state = load_or_initialize_state(league_key, state_path)
    except (OSError, ValueError) as error:
        st.error(f"Unable to load War Room state: {error}")
        st.stop()

    @st.cache_data(show_spinner="Building EdgeIQ rankings...")
    def load_rankings(selected_league_key):
        return build_draft_assistant(
            selected_league_key,
            draft_context={},
        )

    try:
        rankings = load_rankings(league_key)
    except Exception as error:
        st.error(f"Unable to build EdgeIQ rankings: {error}")
        st.stop()

    render_war_room(
        state,
        rankings,
        state_path,
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run bootstrap tests and verify GREEN**

Run:

```bash
python -m pytest tests/test_streamlit_war_room_bootstrap.py -v
```

Expected: PASS.

- [ ] **Step 5: Run all War Room targeted tests**

Run:

```bash
python -m pytest \
  tests/test_live_war_room_core.py \
  tests/test_war_room_ui_helpers.py \
  tests/test_streamlit_war_room_bootstrap.py -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit Task 5**

```bash
git add fantasy_draft_model/ui/streamlit_app.py tests/test_streamlit_war_room_bootstrap.py
git commit -m "Add EdgeIQ Streamlit War Room entrypoint"
```

---

### Task 6: Local laptop smoke test and full regression gate

**Files:**
- Modify only if the smoke test exposes a concrete bug covered by a new failing test first.

**Interfaces:**
- Verifies the complete Task 5A browser workflow.

- [ ] **Step 1: Verify Streamlit is available in the active venv**

Run:

```bash
python -c "import streamlit; print(streamlit.__version__)"
```

Expected: prints a Streamlit version and exits 0.

If import fails, install locally into the active venv:

```bash
python -m pip install streamlit
```

Then rerun the import verification command.

- [ ] **Step 2: Launch the app locally**

Run:

```bash
python -m streamlit run fantasy_draft_model/ui/streamlit_app.py
```

Expected: Streamlit starts successfully and provides a local browser URL.

- [ ] **Step 3: Perform laptop smoke test**

Verify in the browser, in this order:

1. Page opens in wide layout.
2. Drunk Sundays can be selected.
3. Overall pick, round, on-the-clock team, and user team are visible.
4. Search finds a known player.
5. Position filter narrows the board.
6. Keeper-reserved players do not appear in available/recommendation results.
7. Record a safe test player and verify the displayed current pick advances.
8. Refresh the browser and verify the recorded pick remains.
9. Verify the drafted player no longer appears in available/recommendation results.
10. Click Undo Last Pick and verify the pick number/player availability returns correctly.
11. Recent Picks updates correctly before and after undo.
12. No traceback is visible in Streamlit or the terminal.

- [ ] **Step 4: If a smoke-test bug appears, create one failing automated test before changing production code**

Use the existing closest test file:

```bash
python -m pytest tests/test_war_room_ui_helpers.py -v
```

or:

```bash
python -m pytest tests/test_streamlit_war_room_bootstrap.py -v
```

Add the smallest test reproducing the observed bug, confirm RED, make the minimum fix, then confirm GREEN before resuming the smoke test.

- [ ] **Step 5: Run the full project regression suite**

Run:

```bash
python -m pytest -q
```

Expected: zero failures.

- [ ] **Step 6: Commit any smoke-test fix, or make a completion checkpoint commit if implementation changes are already committed**

If a fix was required:

```bash
git add <changed files>
git commit -m "Fix War Room laptop smoke issue"
```

If no additional code changes were required, do not create an empty commit.

---

## Plan Self-Review

### Spec coverage

- Laptop-first wide layout: Task 5 + Task 6.
- Current pick/round/on-the-clock/user team: Task 4.
- Searchable/filterable available-player board: Tasks 1 + 4.
- EdgeIQ recommendations from existing pipeline: Task 5, displayed by Task 4.
- Record Pick through tested backend: Task 2 + Task 4.
- Undo through tested backend: Task 2 + Task 4.
- Recent history: Tasks 1 + 4.
- Remove manual picks and keepers from both boards: Task 1, reused by Task 4.
- JSON persistence across reruns/refreshes: Task 3 + backend delegation + Task 6 smoke test.
- Duplicate protection: backend remains authoritative; verified through existing core regression tests and browser smoke path.
- Optional columns tolerated: Task 1.
- Error handling at UI boundary: Tasks 4 + 5.
- Rankings failure preserves state and stops unsafe entry: Task 5.
- TDD + targeted + full regression: every task + Task 6.

### Placeholder scan

No TBD/TODO/"implement later" placeholders are present. Every production-code task names exact files, functions, commands, and expected test outcomes.

### Type/interface consistency

- `state` remains a mutable `dict` owned by the backend core.
- ranking/available/history tabular data remains pandas `DataFrame`.
- player selection passes the original pandas row/Series to `record_manual_pick`.
- `state_path` is path-like and converted to `Path` where bootstrap logic owns filesystem checks.
- renderer calls the wrapper functions defined in Task 2 and the helper functions defined in Task 1.
