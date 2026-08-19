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
