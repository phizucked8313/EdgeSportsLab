import importlib.util
import pathlib
import subprocess
import sys

import pandas as pd

from fantasy_draft_model import rankings
from fantasy_draft_model.engines import mock_draft_engine
from fantasy_draft_model.ui import draft_board, player_selection


def test_core_draft_modules_import_when_streamlit_is_unavailable():
    code = r'''
import importlib.abc
import sys

class BlockStreamlit(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "streamlit" or fullname.startswith("streamlit."):
            raise ImportError("streamlit intentionally unavailable")
        return None

sys.meta_path.insert(0, BlockStreamlit())

import fantasy_draft_model.draft_assistant
import fantasy_draft_model.engines.mock_draft_engine
import fantasy_draft_model.ui.draft_war_room
print("core imports ok")
'''

    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "core imports ok" in result.stdout


def test_cli_draft_board_filters_without_mutating_core_available_pool(monkeypatch):
    available = pd.DataFrame(
        [
            {
                "player_name_clean": "RB One",
                "position": "RB",
                "team": "BUF",
                "bye_week": 7,
                "draft_rank": 1,
            },
            {
                "player_name_clean": "WR One",
                "position": "WR",
                "team": "DAL",
                "bye_week": 14,
                "draft_rank": 2,
            },
        ]
    )
    original = available.copy(deep=True)

    monkeypatch.setattr("builtins.input", lambda _prompt: "3")

    result = draft_board.build_draft_board(available)

    pd.testing.assert_frame_equal(available, original)
    assert result["player_name_clean"].tolist() == ["RB One"]
    assert result is not available


def test_mock_draft_core_wiring_uses_rankings_and_cli_consumers_directly():
    assert mock_draft_engine.build_draft_rankings is rankings.build_draft_rankings
    assert mock_draft_engine.build_draft_board is draft_board.build_draft_board
    assert mock_draft_engine.select_player is player_selection.select_player


def test_visual_ui_placeholders_remain_outside_core_execution_path():
    ui_dir = pathlib.Path(__file__).resolve().parents[1] / "fantasy_draft_model" / "ui"
    placeholder_names = [
        "streamlit_app.py",
        "league_dashboard.py",
        "player_card_view.py",
    ]

    for filename in placeholder_names:
        path = ui_dir / filename
        assert path.exists()
        assert path.read_text(encoding="utf-8").strip() == ""
        assert importlib.util.spec_from_file_location(path.stem, path) is not None
