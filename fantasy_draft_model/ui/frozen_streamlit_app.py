"""Production Streamlit entrypoint for the immutable 2026 draft-night board."""

from __future__ import annotations

import pandas as pd

from fantasy_draft_model.draft_assistant import build_draft_assistant_from_rankings
from fantasy_draft_model.draft_night_board import load_production_draft_night_board
from fantasy_draft_model.ui import streamlit_app as legacy
from fantasy_draft_model.ui.draft_war_room import (
    AVAILABLE_PLAYERS_ONLY_ATTR,
    build_live_draft_context,
    build_war_room_snapshot,
    enrich_user_roster_metadata,
    filter_available_players,
)


PRODUCTION_BOARD_CACHE_KEY = "_edgeiq_frozen_production_board_cache"
PRODUCTION_STATUS_CACHE_KEY = "_edgeiq_frozen_production_status_cache"


def _supplemental_mask(board: pd.DataFrame) -> pd.Series:
    values = board.get("is_supplemental", pd.Series(False, index=board.index))
    return values.fillna(False).astype(bool)


def _restore_frozen_rank_order(board: pd.DataFrame) -> pd.DataFrame:
    """Keep the immutable Top 300 order authoritative after live overlays."""
    ordered = board.copy()
    ordered["_frozen_order"] = pd.to_numeric(
        ordered["draft_rank"], errors="coerce"
    )
    ordered = ordered.sort_values(
        ["_frozen_order", "player_name_clean"],
        ascending=[True, True],
        na_position="last",
        kind="stable",
    )
    return ordered.drop(columns="_frozen_order").reset_index(drop=True)


def build_production_live_view(
    *,
    search_text="",
    position=None,
    base_rankings,
    data_status,
    expected_draft_id=None,
):
    """Build the live view without applying frozen-player scoring to K/DEF rows."""
    state = legacy.load_or_initialize_war_room_state()
    legacy._require_authorized_draft(state, expected_draft_id)
    context = build_live_draft_context(state)

    available_rankings = filter_available_players(base_rankings, state)
    supplemental = _supplemental_mask(available_rankings)
    ranked_available = available_rankings.loc[~supplemental].copy()
    supplemental_available = available_rankings.loc[supplemental].copy()

    ranked_board = build_draft_assistant_from_rankings(
        ranked_available,
        draft_context=context,
    )
    ranked_board = _restore_frozen_rank_order(ranked_board)
    board = pd.concat(
        [ranked_board, supplemental_available],
        ignore_index=True,
        sort=False,
    )
    board.attrs[AVAILABLE_PLAYERS_ONLY_ATTR] = True

    snapshot = build_war_room_snapshot(
        board,
        state,
        search_text=search_text,
        position=position,
    )
    snapshot["roster"] = enrich_user_roster_metadata(
        snapshot["roster"],
        base_rankings,
    )
    snapshot["ranking_data_status"] = data_status
    return snapshot


def render_ranked_player_explanation(st, snapshot):
    """Explain frozen-ranked players while keeping unscored K/DEF visibly separate."""
    if snapshot.get("context", {}).get("draft_complete"):
        return

    available = snapshot.get("available")
    filtered = snapshot.get("filtered_available")
    if available is None or filtered is None or filtered.empty:
        return

    ranked_available = available.loc[~_supplemental_mask(available)].copy()
    ranked_filtered = filtered.loc[~_supplemental_mask(filtered)].copy()
    if ranked_filtered.empty:
        st.info(
            "K/DEF are deterministic offline supplemental entries. "
            "League-adjusted Draft Brain value is withheld until verified component "
            "projection data is available; no fake frozen rank is assigned."
        )
        return

    explanation_snapshot = dict(snapshot)
    explanation_snapshot["available"] = ranked_available
    explanation_snapshot["filtered_available"] = ranked_filtered
    legacy.render_player_explanation(st, explanation_snapshot)


def _render_frozen_startup_error(st, error):
    st.error(f"Frozen rankings unavailable: {error}")
    st.info(
        "Draft-night startup fails closed. Restore the committed frozen CSV/manifest "
        "before recording any picks; live rankings and mutable cache are not substitutes."
    )
    if st.button("Retry"):
        st.rerun()


def run_war_room_ui(st):
    """Authorize draft state, then load only the immutable frozen production board."""
    if not hasattr(st, "session_state"):
        st.error("Draft authorization requires a Streamlit session.")
        return

    try:
        inspection = legacy.inspect_draft_lifecycle(legacy.DEFAULT_STATE_PATH)
    except (
        legacy.StateLoadError,
        legacy.StateValidationError,
        OSError,
        ValueError,
    ) as error:
        legacy._render_lifecycle_error(st, error)
        return

    authorized_draft_id = st.session_state.get(legacy.DRAFT_AUTHORIZATION_KEY)
    if not inspection.draft_id or authorized_draft_id != inspection.draft_id:
        st.session_state.pop(legacy.DRAFT_AUTHORIZATION_KEY, None)
        legacy.render_state_recovery(st, inspection)
        if st.session_state.pop(legacy.RECOVERY_REQUEST_KEY, False):
            try:
                recovered = legacy.recover_existing_draft(
                    legacy.DEFAULT_STATE_PATH,
                    legacy.DRAFT_ARCHIVE_ROOT,
                )
            except (
                legacy.StateLoadError,
                legacy.StateValidationError,
                ValueError,
                OSError,
            ) as error:
                legacy._render_lifecycle_error(st, error)
            else:
                st.session_state.pop(legacy.DRAFT_AUTHORIZATION_KEY, None)
                st.success(
                    f"Recovered draft {recovered['draft_id']} from validated backup."
                )
                st.rerun()
            return

        action = legacy.render_lifecycle_gate(st, inspection)
        if action is None:
            return
        try:
            if action == "resume":
                state = legacy.resume_existing_draft(
                    legacy.DEFAULT_STATE_PATH,
                    archive_root=legacy.DRAFT_ARCHIVE_ROOT,
                )
            else:
                state = legacy.start_new_draft(
                    "drunk_sundays",
                    legacy.DEFAULT_STATE_PATH,
                    legacy.DRAFT_ARCHIVE_ROOT,
                )
        except (
            legacy.StateLoadError,
            legacy.StateValidationError,
            ValueError,
            OSError,
        ) as error:
            legacy._render_lifecycle_error(st, error)
            return

        st.session_state[legacy.DRAFT_AUTHORIZATION_KEY] = state["draft_id"]
        if action == "start":
            st.success(
                f"Started new draft. Verified archive path: {legacy.DRAFT_ARCHIVE_ROOT}"
            )
        st.rerun()
        return

    search_text = st.text_input("Search players", value="")
    position = st.selectbox("Position", legacy.POSITION_OPTIONS, index=0)
    state = inspection.state

    board_cache = st.session_state.setdefault(PRODUCTION_BOARD_CACHE_KEY, {})
    status_cache = st.session_state.setdefault(PRODUCTION_STATUS_CACHE_KEY, {})
    league_key = state["league_key"]
    if league_key not in board_cache:
        try:
            board_cache[league_key], status_cache[league_key] = (
                load_production_draft_night_board(league_key)
            )
        except (OSError, ValueError) as error:
            _render_frozen_startup_error(st, error)
            return

    try:
        snapshot = build_production_live_view(
            search_text=search_text,
            position=position,
            base_rankings=board_cache[league_key],
            data_status=status_cache[league_key],
            expected_draft_id=authorized_draft_id,
        )
    except legacy.DraftAuthorizationError as error:
        legacy._return_to_lifecycle_gate(st, error)
        return
    except (
        legacy.StateLoadError,
        legacy.StateValidationError,
        OSError,
        ValueError,
    ) as error:
        legacy._return_to_lifecycle_gate(st, error)
        return

    legacy.render_war_room_snapshot(st, snapshot)
    render_ranked_player_explanation(st, snapshot)
    legacy.render_draft_actions(
        st,
        snapshot,
        expected_draft_id=authorized_draft_id,
    )


def main():
    import streamlit as st

    st.set_page_config(page_title="EdgeIQ War Room", layout="wide")
    st.title("EdgeIQ War Room")
    st.caption("Immutable 2026 draft-night baseline · offline-safe K/DEF supplement")
    run_war_room_ui(st)


if __name__ == "__main__":
    main()
