import json
from hashlib import sha256

import pandas as pd
import pytest

from fantasy_draft_model.final_snapshot import (
    build_freeze_manifest,
    load_frozen_snapshot_offline,
    normalize_player_name,
    select_top_300,
    validate_top_300,
    write_frozen_snapshot,
)


VALID_TEAMS = (
    "ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE",
    "DAL", "DEN", "DET", "GB", "HOU", "IND", "JAX", "KC",
    "LV", "LAC", "LAR", "MIA", "MIN", "NE", "NO", "NYG",
    "NYJ", "PHI", "PIT", "SEA", "SF", "TB", "TEN", "WAS",
)


def _board(rows=320):
    positions = ("QB", "RB", "WR", "TE")
    records = []
    for index in range(rows):
        team = VALID_TEAMS[index % len(VALID_TEAMS)]
        records.append(
            {
                "player_id": f"00-{index:07d}",
                "player_name_clean": f"Player {index + 1}",
                "position": positions[index % len(positions)],
                "team": team,
                "bye_week": _bye_map()[team],
                "draft_rank": index + 1,
                "projected_points": 500.0 - index,
                "vorp": 200.0 - index,
                "edgescore": 90.0,
                "draft_score": 80.0,
                "projection_confidence": 85.0,
                "tier": 1 + index // 50,
                "injury_risk_score": 10.0,
                "is_currently_injured": False,
                "current_injury_status": "",
                "current_injury_body_part": "",
                "current_injury_source": "",
                "current_injury_source_timestamp": "",
            }
        )
    return pd.DataFrame(records)


def _bye_map():
    return {team: 5 + index % 10 for index, team in enumerate(VALID_TEAMS)}


def _keepers():
    return pd.DataFrame(
        [
            {
                "league_name": "Drunk Sundays",
                "owner_team": "Manager A",
                "player_name": "Player 1",
                "keeper_type": "standard",
                "keeper_round": 15,
            }
        ]
    )


def _reservations():
    return [
        {
            "fantasy_team": "Manager A",
            "player_name": "Player 1",
            "keeper_type": "standard",
            "keeper_round": 15,
            "pick_number": 169,
        }
    ]


def test_select_and_validate_top_300_enforces_freeze_contract():
    selected = select_top_300(_board())

    report = validate_top_300(
        selected,
        bye_by_team=_bye_map(),
        keepers=_keepers(),
        keeper_reservations=_reservations(),
    )

    assert len(selected) == 300
    assert selected["draft_rank"].tolist() == list(range(1, 301))
    assert report["row_count"] == 300
    assert report["keeper_count"] == 1
    assert report["identity_unique"] is True


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda df: df.drop(index=df.index[-1]), "exactly 300"),
        (lambda df: df.assign(draft_rank=[1] * len(df)), "ranks 1 through 300"),
        (lambda df: df.assign(player_id=["same"] * len(df)), "player IDs"),
        (
            lambda df: df.assign(
                player_name_clean=["Player 1", " player-1 "]
                + df.player_name_clean.iloc[2:].tolist()
            ),
            "normalized player names",
        ),
        (lambda df: df.assign(team="AZ"), "canonical NFL team"),
        (lambda df: df.assign(position="FB"), "supported position"),
        (lambda df: df.assign(projected_points=None), "ranking input"),
    ],
)
def test_validate_top_300_rejects_structural_defects(mutate, message):
    with pytest.raises(ValueError, match=message):
        validate_top_300(
            mutate(select_top_300(_board())),
            bye_by_team=_bye_map(),
            keepers=_keepers(),
            keeper_reservations=_reservations(),
        )


def test_validate_top_300_rejects_wrong_bye_and_keeper_mismatch():
    selected = select_top_300(_board())
    selected.loc[0, "bye_week"] = 99
    with pytest.raises(ValueError, match="team/bye"):
        validate_top_300(
            selected,
            bye_by_team=_bye_map(),
            keepers=_keepers(),
            keeper_reservations=_reservations(),
        )

    with pytest.raises(ValueError, match="keeper"):
        validate_top_300(
            select_top_300(_board()),
            bye_by_team=_bye_map(),
            keepers=_keepers(),
            keeper_reservations=_reservations() * 2,
        )


def test_frozen_snapshot_round_trip_is_checksum_verified_and_offline(tmp_path):
    selected = select_top_300(_board())
    audit = validate_top_300(
        selected,
        bye_by_team=_bye_map(),
        keepers=_keepers(),
        keeper_reservations=_reservations(),
    )
    manifest = build_freeze_manifest(
        selected,
        source_commit="a" * 40,
        league_key="drunk_sundays",
        league_config_sha256="b" * 64,
        generated_at="2026-08-21T12:00:00+00:00",
        inputs={"weekly_stats": {"identifier": "stats_player_week_2025"}},
        audit=audit,
        exclusions=[],
        waivers=[],
    )
    csv_path = tmp_path / "edgeiq-top-300.csv"
    manifest_path = tmp_path / "edgeiq-top-300.manifest.json"

    write_frozen_snapshot(selected, manifest, csv_path, manifest_path)
    loaded, loaded_manifest = load_frozen_snapshot_offline(
        csv_path,
        manifest_path,
        bye_by_team=_bye_map(),
        keepers=_keepers(),
        keeper_reservations=_reservations(),
    )

    assert loaded["draft_rank"].tolist() == list(range(1, 301))
    assert loaded_manifest["snapshot_sha256"] == sha256(csv_path.read_bytes()).hexdigest()
    assert json.loads(manifest_path.read_text(encoding="utf-8"))["immutable"] is True

    csv_path.write_bytes(csv_path.read_bytes() + b"tamper")
    with pytest.raises(ValueError, match="checksum"):
        load_frozen_snapshot_offline(
            csv_path,
            manifest_path,
            bye_by_team=_bye_map(),
            keepers=_keepers(),
            keeper_reservations=_reservations(),
        )


def test_normalized_name_handles_suffix_punctuation_and_accents():
    assert normalize_player_name("Audric Estimé Jr.") == "audric estime jr"
