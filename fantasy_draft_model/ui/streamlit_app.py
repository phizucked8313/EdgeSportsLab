"""EdgeIQ Streamlit War Room shell."""

from pathlib import Path

from fantasy_draft_model.draft_assistant import build_draft_assistant_from_rankings
from fantasy_draft_model.rankings import build_draft_rankings
from fantasy_draft_model.config import DATA_DIR
from fantasy_draft_model.rankings_snapshot import (
    DRAFT_NIGHT_RANKINGS_REFRESH_TIMEOUT_SECONDS,
    load_rankings_with_fallback,
)
from fantasy_draft_model.live_war_room import (
    DEFAULT_STATE_PATH,
    initialize_war_room,
    load_war_room_state,
    record_manual_pick,
    undo_last_manual_pick,
)
from fantasy_draft_model.draft_lifecycle import (
    inspect_draft_lifecycle,
    recover_existing_draft,
    resume_existing_draft,
    start_new_draft,
)
from fantasy_draft_model.rankings_snapshot import RankingRefreshError
from fantasy_draft_model.state_persistence import StateLoadError
from fantasy_draft_model.war_room_state import DraftCompleteError, StateValidationError
from fantasy_draft_model.ui.draft_war_room import (
    AVAILABLE_PLAYERS_ONLY_ATTR,
    build_live_draft_context,
    build_player_ranking_explanation,
    build_static_available_board_html,
    build_war_room_snapshot,
    enrich_user_roster_metadata,
    filter_available_players,
)


POSITION_OPTIONS = ["ALL", "QB", "RB", "WR", "TE", "K", "DEF"]
BASE_RANKINGS_CACHE_KEY = "_edgeiq_base_rankings_cache"
RANKINGS_STATUS_CACHE_KEY = "_edgeiq_rankings_status_cache"
RANKINGS_SNAPSHOT_PATHS = {
    "data_path": DATA_DIR / "war_room_rankings.csv",
    "metadata_path": DATA_DIR / "war_room_rankings.json",
}
DRAFT_ARCHIVE_ROOT = Path(DEFAULT_STATE_PATH).parent / "archives"
DRAFT_AUTHORIZATION_KEY = "_edgeiq_authorized_draft_id"
RECOVERY_REQUEST_KEY = "_edgeiq_recovery_requested"


class DraftAuthorizationError(RuntimeError):
    """Raised when the authoritative draft changed after UI authorization."""


def _require_authorized_draft(state, expected_draft_id):
    if expected_draft_id is None:
        return
    if state.get("draft_id") != expected_draft_id:
        raise DraftAuthorizationError(
            "Draft state changed on disk. Return to the lifecycle gate before continuing."
        )


def load_or_initialize_war_room_state():
    """Load only an existing authoritative War Room state.

    The UI deliberately never creates draft state as a side effect of opening.
    """
    return load_war_room_state()


def get_or_build_base_rankings(
    cache,
    league_key,
    *,
    paths=None,
    builder=None,
    timeout_seconds=DRAFT_NIGHT_RANKINGS_REFRESH_TIMEOUT_SECONDS,
    status_cache=None,
):
    """Build expensive rankings once per league and reuse them from the supplied cache."""
    if builder is None:
        builder = build_draft_rankings
    if paths is None:
        paths = RANKINGS_SNAPSHOT_PATHS
    if league_key not in cache:
        cache[league_key], status = load_rankings_with_fallback(
            league_key,
            builder=builder,
            paths=paths,
            timeout_seconds=timeout_seconds,
        )
        if status_cache is not None:
            status_cache[league_key] = status
    return cache[league_key]


def build_live_view(
    search_text="",
    position=None,
    base_rankings=None,
    data_status=None,
    expected_draft_id=None,
    *,
    paths=None,
    builder=None,
    timeout_seconds=DRAFT_NIGHT_RANKINGS_REFRESH_TIMEOUT_SECONDS,
):
    """Build the War Room snapshot using fresh live context and optional cached rankings."""
    state = load_or_initialize_war_room_state()
    _require_authorized_draft(state, expected_draft_id)
    context = build_live_draft_context(state)

    if base_rankings is None:
        if builder is None:
            builder = build_draft_rankings
        if paths is None:
            paths = RANKINGS_SNAPSHOT_PATHS
        base_rankings, loaded_status = load_rankings_with_fallback(
            state["league_key"],
            builder=builder,
            paths=paths,
            timeout_seconds=timeout_seconds,
        )
        if data_status is None:
            data_status = loaded_status

    available_rankings = filter_available_players(base_rankings, state)
    if len(available_rankings) == len(base_rankings):
        available_rankings = base_rankings
    board = build_draft_assistant_from_rankings(
        available_rankings,
        draft_context=context,
    )
    board.attrs[AVAILABLE_PLAYERS_ONLY_ATTR] = True

    snapshot = build_war_room_snapshot(
        board,
        state,
        search_text=search_text,
        position=position,
    )
    if "roster" in snapshot:
        snapshot["roster"] = enrich_user_roster_metadata(
            snapshot["roster"],
            base_rankings,
        )
    if data_status is not None:
        snapshot["ranking_data_status"] = data_status
    return snapshot


def record_selected_player(available_players, player_name, *, expected_draft_id=None):
    """Record one selected available player using fresh persisted War Room state."""
    selected_name = str(player_name).strip()
    normalized_name = selected_name.casefold()
    matches = available_players[
        available_players["player_name_clean"]
        .astype(str)
        .str.strip()
        .str.casefold()
        == normalized_name
    ]

    if matches.empty:
        raise ValueError(f"{selected_name} is not available")

    state = load_war_room_state()
    _require_authorized_draft(state, expected_draft_id)
    return record_manual_pick(state, matches.iloc[0])


def undo_latest_pick(*, expected_draft_id=None):
    """Undo the latest manual pick using fresh persisted War Room state."""
    state = load_war_room_state()
    _require_authorized_draft(state, expected_draft_id)
    return undo_last_manual_pick(state)


def render_war_room_snapshot(st, snapshot):
    """Render the current War Room snapshot."""
    context = snapshot["context"]

    data_status = snapshot.get("ranking_data_status")
    if data_status is not None:
        render_rankings_status(st, data_status)

    render_draft_complete(st, context)

    st.metric("Current Pick", context.get("current_pick"))
    st.metric("Next BLKWDW'S Pick", context.get("next_user_pick"))
    st.metric("Picks Until You", context.get("picks_until_user"))

    if context.get("user_on_clock"):
        st.success("BLKWDW'S is on the clock")

    st.subheader("Available Players")
    st.markdown(
        build_static_available_board_html(snapshot["filtered_available"]),
        unsafe_allow_html=True,
    )

    st.subheader("Your Roster")
    st.dataframe(
        snapshot["roster"],
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Recent Draft History")
    st.dataframe(
        snapshot["recent_history"],
        use_container_width=True,
        hide_index=True,
    )


def _render_status_text(st, text):
    if hasattr(st, "caption"):
        st.caption(text)
    else:
        st.markdown(text)


def render_rankings_status(st, status):
    """Render source, timestamp, freshness, and any live-refresh failure."""
    age = "unknown age" if status.age_seconds is None else f"{status.age_seconds:.0f}s old"
    failure = status.failure_reason or "none"
    _render_status_text(
        st,
        f"Rankings: {status.source} | created {status.created_at} | age {age} | live refresh failure: {failure}",
    )


def render_draft_complete(st, context):
    """Show completion facts while leaving historical draft views available."""
    if not context.get("draft_complete"):
        return
    accounted = context.get("accounted_picks", 0)
    total = context.get("total_picks", 0)
    st.success(f"Draft Complete — {accounted} of {total} slots accounted for")


def render_lifecycle_gate(st, inspection):
    """Render the explicit Start/Resume choice and return the requested action."""
    _render_status_text(
        st,
        "Draft state: "
        f"id {inspection.draft_id or 'none'} | "
        f"source {inspection.source or 'none'} | "
        f"{inspection.completed_slots} of {inspection.total_slots or '?'} slots accounted for | "
        f"updated {inspection.updated_at or 'unknown'}",
    )
    _render_status_text(st, f"State artifact: {inspection.authoritative_path}")
    if st.button("Resume Draft", disabled=not inspection.can_resume):
        return "resume"
    if st.button("Start New Draft"):
        return "start"
    return None


def render_state_recovery(st, inspection):
    """Render non-destructive recovery facts and an explicit recovery control."""
    _render_status_text(st, f"Backup artifact: {inspection.backup_path}")
    _render_status_text(st, f"Recovery metadata: {inspection.recovery_metadata_path}")
    for label, error in (
        ("authoritative", inspection.authoritative_error),
        ("backup", inspection.backup_error),
        ("legacy", inspection.legacy_error),
    ):
        if error is not None:
            st.error(f"{label.title()} state issue: {error}")
    if inspection.can_recover:
        st.info("A validated backup is available. Recovery archives the corrupt state before restoring it.")
        if st.button("Recover Backup"):
            st.session_state[RECOVERY_REQUEST_KEY] = True


def _render_lifecycle_error(st, error):
    st.error(f"Draft state action was not completed: {error}")
    _render_status_text(st, f"State artifact: {DEFAULT_STATE_PATH}")
    _render_status_text(st, f"Archive/recovery path: {DRAFT_ARCHIVE_ROOT}")


def _return_to_lifecycle_gate(st, error):
    """Drop stale authorization and render the current non-mutating gate."""
    st.session_state.pop(DRAFT_AUTHORIZATION_KEY, None)
    st.error(str(error))
    try:
        inspection = inspect_draft_lifecycle(DEFAULT_STATE_PATH)
    except (StateLoadError, StateValidationError, ValueError) as inspection_error:
        _render_lifecycle_error(st, inspection_error)
        return
    render_state_recovery(st, inspection)
    render_lifecycle_gate(st, inspection)


def _render_rankings_startup_error(st, error):
    st.error(f"Rankings unavailable: {error}")
    st.info("Retry after restoring a live data connection or a validated rankings cache. See the draft-night runbook before recording picks.")
    if st.button("Retry"):
        st.rerun()


def render_player_explanation(st, snapshot):
    """Render a readable explanation for one selected live-ranked player."""
    if snapshot.get("context", {}).get("draft_complete"):
        return

    filtered_available = snapshot.get("filtered_available")
    available = snapshot.get("available")
    if filtered_available is None or available is None or filtered_available.empty:
        return

    player_names = filtered_available["player_name_clean"].tolist()
    selected_player = st.selectbox(
        "Explain player",
        player_names,
        index=0,
    )
    explanation = build_player_ranking_explanation(available, selected_player)

    st.subheader(f"Why EdgeIQ ranks {explanation['player_name']} here")
    st.markdown(
        f"**#{explanation['draft_rank']} · {explanation['brain_score']:.1f} Draft Brain · "
        f"{explanation['recommendation']}**"
    )

    tier_label = explanation["tier_label"]
    if tier_label:
        st.markdown(
            f"**{tier_label}:** {explanation['tier_remaining']} remaining · "
            f"{explanation['tier_scarcity_score']:.2f} scarcity"
        )

    numbers = explanation["key_numbers"]
    st.markdown(
        "**Key numbers:** "
        f"{numbers['projected_points']:.2f} projected pts · "
        f"{numbers['vorp']:.2f} VORP · "
        f"{numbers['edgescore']:.2f} EdgeScore · "
        f"{numbers['projection_confidence']:.2f}% confidence · "
        f"{numbers['injury_risk_score']:.1f} injury risk"
    )

    drivers = explanation["drivers"]
    if drivers:
        st.markdown("**Why EdgeIQ likes him:** " + " · ".join(drivers))

    warnings = explanation["warnings"]
    if warnings:
        st.markdown("**Warnings:** " + " · ".join(warnings))

    comparison = explanation["comparison"]
    if comparison:
        st.markdown(
            f"**Why above {comparison['player_name']}:** "
            f"{comparison['brain_score_delta']:+.2f} Brain · "
            f"{comparison['projected_points_delta']:+.2f} projected pts · "
            f"{comparison['vorp_delta']:+.2f} VORP · "
            f"{comparison['edgescore_delta']:+.2f} EdgeScore"
        )


def render_draft_actions(st, snapshot, *, expected_draft_id=None):
    """Render Record Pick in a form so selection changes do not rerun the app."""
    filtered_available = snapshot["filtered_available"]
    player_names = filtered_available["player_name_clean"].tolist()
    draft_complete = snapshot.get("context", {}).get("draft_complete", False)

    if hasattr(st, "form") and hasattr(st, "form_submit_button"):
        with st.form("draft_player_form"):
            selected_player = st.selectbox(
                "Draft player",
                player_names,
                index=0,
            )
            record_pick = st.form_submit_button(
                "Record Pick",
                disabled=draft_complete or not player_names,
            )
    else:
        selected_player = st.selectbox(
            "Draft player",
            player_names,
            index=0,
        )
        record_pick = st.button("Record Pick", disabled=draft_complete or not player_names)

    if record_pick:
        try:
            record_selected_player(
                snapshot["available"],
                selected_player,
                expected_draft_id=expected_draft_id,
            )
        except DraftAuthorizationError as error:
            st.session_state.pop(DRAFT_AUTHORIZATION_KEY, None)
            st.error(str(error))
        except (OSError, DraftCompleteError, StateLoadError, StateValidationError, ValueError) as error:
            st.error(f"Pick was not recorded: {error}")
        else:
            st.rerun()

    recent_history = snapshot["recent_history"]
    if st.button("Undo Last Pick", disabled=recent_history.empty):
        try:
            undo_latest_pick(expected_draft_id=expected_draft_id)
        except DraftAuthorizationError as error:
            st.session_state.pop(DRAFT_AUTHORIZATION_KEY, None)
            st.error(str(error))
        except (OSError, StateLoadError, StateValidationError, ValueError) as error:
            st.error(f"Pick was not undone: {error}")
        else:
            st.rerun()


def run_war_room_ui(st):
    """Authorize an inspected draft before loading its live board."""
    if not hasattr(st, "session_state"):
        st.error("Draft authorization requires a Streamlit session.")
        return

    try:
        inspection = inspect_draft_lifecycle(DEFAULT_STATE_PATH)
    except (StateLoadError, StateValidationError, ValueError) as error:
        _render_lifecycle_error(st, error)
        return

    authorized_draft_id = st.session_state.get(DRAFT_AUTHORIZATION_KEY)
    if not inspection.draft_id or authorized_draft_id != inspection.draft_id:
        st.session_state.pop(DRAFT_AUTHORIZATION_KEY, None)
        render_state_recovery(st, inspection)
        if st.session_state.pop(RECOVERY_REQUEST_KEY, False):
            try:
                recovered = recover_existing_draft(DEFAULT_STATE_PATH, DRAFT_ARCHIVE_ROOT)
            except (StateLoadError, StateValidationError, ValueError, OSError) as error:
                _render_lifecycle_error(st, error)
            else:
                st.session_state[DRAFT_AUTHORIZATION_KEY] = recovered["draft_id"]
                st.success(f"Recovered draft {recovered['draft_id']} from validated backup.")
                st.rerun()
            return
        action = render_lifecycle_gate(st, inspection)
        if action is None:
            return
        try:
            if action == "resume":
                state = resume_existing_draft(DEFAULT_STATE_PATH, archive_root=DRAFT_ARCHIVE_ROOT)
            else:
                state = start_new_draft(
                    "drunk_sundays",
                    DEFAULT_STATE_PATH,
                    DRAFT_ARCHIVE_ROOT,
                )
        except (StateLoadError, StateValidationError, ValueError, OSError) as error:
            _render_lifecycle_error(st, error)
            return
        st.session_state[DRAFT_AUTHORIZATION_KEY] = state["draft_id"]
        if action == "start":
            st.success(f"Started new draft. Verified archive path: {DRAFT_ARCHIVE_ROOT}")
        st.rerun()
        return

    search_text = st.text_input("Search players", value="")
    position = st.selectbox("Position", POSITION_OPTIONS, index=0)

    base_rankings = None
    if hasattr(st, "session_state"):
        state = inspection.state
        if BASE_RANKINGS_CACHE_KEY not in st.session_state:
            st.session_state[BASE_RANKINGS_CACHE_KEY] = {}
        rankings_cache = st.session_state[BASE_RANKINGS_CACHE_KEY]
        if RANKINGS_STATUS_CACHE_KEY not in st.session_state:
            st.session_state[RANKINGS_STATUS_CACHE_KEY] = {}
        status_cache = st.session_state[RANKINGS_STATUS_CACHE_KEY]
        try:
            base_rankings = get_or_build_base_rankings(
                rankings_cache,
                state["league_key"],
                paths=RANKINGS_SNAPSHOT_PATHS,
                builder=build_draft_rankings,
                timeout_seconds=DRAFT_NIGHT_RANKINGS_REFRESH_TIMEOUT_SECONDS,
                status_cache=status_cache,
            )
        except RankingRefreshError as error:
            _render_rankings_startup_error(st, error)
            return
        data_status = status_cache.get(state["league_key"])

    try:
        if base_rankings is None:
            snapshot = build_live_view(
                search_text=search_text,
                position=position,
                expected_draft_id=authorized_draft_id,
            )
        else:
            snapshot = build_live_view(
                search_text=search_text,
                position=position,
                base_rankings=base_rankings,
                data_status=data_status,
                expected_draft_id=authorized_draft_id,
            )
    except DraftAuthorizationError as error:
        _return_to_lifecycle_gate(st, error)
        return

    render_war_room_snapshot(st, snapshot)
    render_player_explanation(st, snapshot)
    render_draft_actions(st, snapshot, expected_draft_id=authorized_draft_id)


def main():
    """Launch the EdgeIQ War Room UI without coupling Streamlit to core imports."""
    import streamlit as st

    st.set_page_config(
        page_title="EdgeIQ War Room",
        layout="wide",
    )
    st.title("EdgeIQ War Room")
    st.caption("Live draft assistant shell")
    run_war_room_ui(st)


if __name__ == "__main__":
    main()
