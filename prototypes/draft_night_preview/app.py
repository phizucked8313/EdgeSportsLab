"""Standalone Streamlit composition for the synthetic draft-night preview."""

import streamlit as st

from prototypes.draft_night_preview.components import (
    render_at_risk,
    render_available_players,
    render_draft_complete,
    render_draft_header,
    render_explanation,
    render_history,
    render_roster,
    render_wait_panel,
)
from prototypes.draft_night_preview.fixtures import complete_fixture, live_fixture
from prototypes.draft_night_preview.styles import preview_css


def _render_preview_html(html: str) -> None:
    """Place an escaped renderer fragment inside the scoped preview root."""
    st.markdown(f'<div class="edgeiq-preview">{html}</div>', unsafe_allow_html=True)


def main() -> None:
    """Render one of the immutable synthetic draft-night preview states."""
    st.set_page_config(page_title="EdgeIQ Draft Night Preview", layout="wide")
    st.markdown(preview_css(), unsafe_allow_html=True)

    brand, state_control = st.columns((4, 2))
    with brand:
        st.title("EdgeIQ · Draft Night")
        st.caption("SYNTHETIC PROTOTYPE · presentation-only preview")
    with state_control:
        preview_state = st.radio(
            "Preview state",
            ("Live Draft", "Draft Complete"),
            horizontal=True,
        )

    if preview_state == "Draft Complete":
        _render_preview_html(render_draft_complete(complete_fixture()))
        return

    fixture = live_fixture()
    _render_preview_html(render_draft_header(fixture.header))

    board, right_rail = st.columns((3, 1), gap="small")
    with board:
        _render_preview_html(render_available_players(fixture.available_players))
    with right_rail:
        _render_preview_html(render_roster(fixture.roster))
        _render_preview_html(render_history(fixture.history))

    explanation, risk, wait = st.columns((3, 2, 2), gap="small")
    with explanation:
        _render_preview_html(render_explanation(fixture.explanation))
    with risk:
        _render_preview_html(render_at_risk(fixture.at_risk))
    with wait:
        _render_preview_html(render_wait_panel(fixture.wait_scenario))


if __name__ == "__main__":
    main()
