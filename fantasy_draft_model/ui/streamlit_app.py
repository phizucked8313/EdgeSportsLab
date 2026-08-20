"""EdgeIQ Streamlit War Room shell."""

from fantasy_draft_model.draft_assistant import build_draft_assistant
from fantasy_draft_model.live_war_room import load_war_room_state
from fantasy_draft_model.ui.draft_war_room import (
    build_live_draft_context,
    build_war_room_snapshot,
)


def build_live_view(search_text="", position=None):
    """Build the read-only War Room snapshot used by the Streamlit shell."""
    state = load_war_room_state()
    context = build_live_draft_context(state)
    board = build_draft_assistant(
        state["league_key"],
        draft_context=context,
    )
    return build_war_room_snapshot(
        board,
        state,
        search_text=search_text,
        position=position,
    )


def main():
    """Launch the EdgeIQ War Room UI without coupling Streamlit to core imports."""
    import streamlit as st

    st.set_page_config(
        page_title="EdgeIQ War Room",
        layout="wide",
    )
    st.title("EdgeIQ War Room")
    st.caption("Live draft assistant shell")


if __name__ == "__main__":
    main()
