from hashlib import sha256

import pandas as pd

from fantasy_draft_model.ui import streamlit_app


EXPECTED_FROZEN_SHA256 = (
    "e79f4ea672f5a08b81d3a89ac2ed1e8ac38f6b714127bf1df81b44d8e17d245b"
)


def test_production_board_loader_uses_frozen_baseline_and_offline_special_teams(monkeypatch):
    loader = getattr(streamlit_app, "load_production_draft_night_board", None)
    assert callable(loader), "production frozen/offline board loader is missing"

    monkeypatch.setattr(
        streamlit_app,
        "build_draft_rankings",
        lambda _league_key: (_ for _ in ()).throw(
            AssertionError("production draft-night startup called the live rankings builder")
        ),
    )
    monkeypatch.setattr(
        streamlit_app,
        "load_rankings_with_fallback",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("production draft-night startup called mutable cache fallback")
        ),
    )

    board, status = loader("drunk_sundays")

    assert status.source == "FROZEN/OFFLINE"
    assert len(board) == 324

    supplemental = board["is_supplemental"].fillna(False).astype(bool)
    frozen = board.loc[~supplemental].copy()
    special = board.loc[supplemental].copy()

    assert len(frozen) == 300
    assert frozen["draft_rank"].tolist() == list(range(1, 301))
    assert len(special.loc[special["position"].eq("K")]) == 12
    assert len(special.loc[special["position"].eq("DEF")]) == 12
    assert special["draft_rank"].isna().all()
    assert special["supplemental_position_rank"].notna().all()
    assert set(special["ranking_source"]) == {"SUPPLEMENTAL/OFFLINE"}


def test_production_frozen_bytes_still_match_verified_checksum():
    csv_path = getattr(streamlit_app, "FROZEN_TOP_300_CSV", None)
    assert csv_path is not None, "production frozen CSV path is not exposed"

    assert sha256(csv_path.read_bytes()).hexdigest() == EXPECTED_FROZEN_SHA256


def test_special_teams_rows_are_searchable_without_fake_frozen_ranks():
    loader = getattr(streamlit_app, "load_production_draft_night_board", None)
    assert callable(loader), "production frozen/offline board loader is missing"

    board, _status = loader("drunk_sundays")

    defenses = board.loc[board["position"].eq("DEF")]
    kickers = board.loc[board["position"].eq("K")]

    assert "Philadelphia Eagles" in defenses["player_name_clean"].tolist()
    assert "Brandon Aubrey" in kickers["player_name_clean"].tolist()
    assert defenses["draft_rank"].isna().all()
    assert kickers["draft_rank"].isna().all()
    assert pd.to_numeric(defenses["supplemental_position_rank"], errors="raise").tolist() == list(range(1, 13))
    assert pd.to_numeric(kickers["supplemental_position_rank"], errors="raise").tolist() == list(range(1, 13))
