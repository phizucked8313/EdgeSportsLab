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


def apply_player_filters(rankings, search_text="", position=None):
    filtered = rankings.copy()

    search_text = str(search_text or "").strip().casefold()
    if search_text:
        name_mask = filtered["player_name_clean"].map(normalize_player_name).str.contains(
            search_text,
            regex=False,
        )
        filtered = filtered.loc[name_mask]

    if position and str(position).strip().upper() != "ALL":
        position_clean = str(position).strip().upper()
        position_mask = filtered["position"].astype(str).str.strip().str.upper() == position_clean
        filtered = filtered.loc[position_mask]

    return filtered.copy().reset_index(drop=True)


def select_display_columns(rankings, preferred_columns):
    return [column for column in preferred_columns if column in rankings.columns]


def build_recent_history(state, limit=10):
    history = pd.DataFrame(state.get("manual_picks", []))
    if history.empty:
        return history

    if "pick_number" in history.columns:
        history = history.sort_values("pick_number", ascending=False)
    else:
        history = history.iloc[::-1]

    return history.head(limit).reset_index(drop=True)
