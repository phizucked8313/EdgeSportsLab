"""EdgeIQ Streamlit War Room shell."""

from fantasy_draft_model.draft_assistant import (
    build_draft_assistant,
    build_draft_assistant_from_rankings,
)
from fantasy_draft_model.rankings import build_draft_rankings
from fantasy_draft_model.live_war_room import (
    initialize_war_room,
    load_war_room_state,
    record_manual_pick,
    undo_last_manual_pick,
)
from fantasy_draft_model.ui.draft_war_room import (
    build_live_draft_context,
    build_static_available_board_html,
    build_war_room_snapshot,
)


POSITION_OPTIONS = ["ALL", "QB", "RB", "WR", "TE", "K", "DEF"]
BASE_RANKINGS_CACHE_KEY = "_edgeiq_base_rankings_cache"


def load_or_initialize_war_room_state():
    """Load persisted War Room state, initializing Drunk Sundays on first launch."""
    try:
        return load_war_room_state()
    except FileNotFoundError:
        return initialize_war_room("drunk_sundays")


def get_or_build_base_rankings(cache, league_key):
    """Build expensive rankings once per league and reuse them from the supplied cache."""
    if league_key not in cache:
        cache[league_key] = build_draft_rankings(league_key)
    return cache[league_key]


def build_live_view(search_text="", position=None, base_rankings=None):
    """Build the War Room snapshot using fresh live context and optional cached rankings."""
    state = load_or_initialize_war_room_state()
    context = build_live_draft_context(state)

    if base_rankings is None:
        board = build_draft_assistant(
            state["league_key"],
            draft_context=context,
        )
    else:
        board = build_draft_assistant_from_rankings(
            base_rankings,
            draft_context=context,
        )

    return build_war_room_snapshot(
        board,
        state,
        search_text=search_text,
        position=position,
    )


def record_selected_player(available_players, player_name):
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
    return record_manual_pick(state, matches.iloc[0])


def undo_latest_pick():
    """Undo the latest manual pick using fresh persisted War Room state."""
    state = load_war_room_state()
    return undo_last_manual_pick(state)


def render_war_room_snapshot(st, snapshot):
    """Render the current War Room snapshot."""
    context = snapshot["context"]

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


def render_draft_actions(st, snapshot):
    """Render Record Pick in a form so selection changes do not rerun the app."""
    filtered_available = snapshot["filtered_available"]
    player_names = filtered_available["player_name_clean"].tolist()

    if hasattr(st, "form") and hasattr(st, "form_submit_button"):
        with st.form("draft_player_form"):
            selected_player = st.selectbox(
                "Draft player",
                player_names,
                index=0,
            )
            record_pick = st.form_submit_button(
                "Record Pick",
                disabled=not player_names,
            )
    else:
        selected_player = st.selectbox(
            "Draft player",
            player_names,
            index=0,
        )
        record_pick = st.button("Record Pick", disabled=not player_names)

    if record_pick:
        record_selected_player(snapshot["available"], selected_player)
        st.rerun()

    recent_history = snapshot["recent_history"]
    if st.button("Undo Last Pick", disabled=recent_history.empty):
        undo_latest_pick()
        st.rerun()


def run_war_room_ui(st):
    """Collect filters, reuse cached rankings, render the live view, and expose actions."""
    search_text = st.text_input("Search players", value="")
    position = st.selectbox("Position", POSITION_OPTIONS, index=0)

    base_rankings = None
    if hasattr(st, "session_state"):
        state = load_or_initialize_war_room_state()
        if BASE_RANKINGS_CACHE_KEY not in st.session_state:
            st.session_state[BASE_RANKINGS_CACHE_KEY] = {}
        base_rankings = get_or_build_base_rankings(
            st.session_state[BASE_RANKINGS_CACHE_KEY],
            state["league_key"],
        )

    if base_rankings is None:
        snapshot = build_live_view(
            search_text=search_text,
            position=position,
        )
    else:
        snapshot = build_live_view(
            search_text=search_text,
            position=position,
            base_rankings=base_rankings,
        )

    render_war_room_snapshot(st, snapshot)
    render_draft_actions(st, snapshot)


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
