import json
from hashlib import sha256

import pandas as pd
import pytest

from fantasy_draft_model.final_snapshot import (
    audit_depth_chart,
    audit_injuries,
    audit_rookies,
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

FROZEN_OPTIONAL_STRING_COLUMNS = (
    "prior_roster_team",
    "roster_status_provenance",
    "roster_status_source",
    "roster_status_source_date",
    "roster_status_retrieved_at",
    "current_injury_status",
    "current_injury_body_part",
    "current_injury_practice_status",
    "current_injury_source_timestamp",
    "current_injury_source_quality",
    "current_injury_data_quality",
    "current_injury_source",
    "current_injury_expected_return",
    "current_injury_timeline_source",
    "current_injury_timeline_source_date",
    "current_injury_timeline_note",
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


def test_frozen_snapshot_round_trip_preserves_optional_string_schema(tmp_path):
    selected = select_top_300(_board())
    selected.loc[0, "projected_points"] = 123.45678901234567
    for column in FROZEN_OPTIONAL_STRING_COLUMNS:
        selected[column] = ""
        selected.loc[1, column] = pd.NA
        selected.loc[2, column] = f"evidence-{column}"
    manifest = build_freeze_manifest(
        selected,
        source_commit="a" * 40,
        league_key="drunk_sundays",
        league_config_sha256="b" * 64,
        generated_at="2026-08-21T12:00:00+00:00",
        inputs={"weekly_stats": {"identifier": "stats_player_week_2025"}},
        audit=validate_top_300(
            selected,
            bye_by_team=_bye_map(),
            keepers=_keepers(),
            keeper_reservations=_reservations(),
        ),
        exclusions=[],
        waivers=[],
    )
    csv_path = tmp_path / "edgeiq-top-300.csv"
    manifest_path = tmp_path / "edgeiq-top-300.manifest.json"

    write_frozen_snapshot(selected, manifest, csv_path, manifest_path)
    loaded, _ = load_frozen_snapshot_offline(
        csv_path,
        manifest_path,
        bye_by_team=_bye_map(),
        keepers=_keepers(),
        keeper_reservations=_reservations(),
    )

    for column in FROZEN_OPTIONAL_STRING_COLUMNS:
        assert str(loaded[column].dtype) == "string"
        assert loaded.loc[0, column] == ""
        assert pd.isna(loaded.loc[1, column])
        assert loaded.loc[2, column] == f"evidence-{column}"
    assert loaded["player_id"].tolist() == selected["player_id"].tolist()
    assert loaded["draft_rank"].tolist() == selected["draft_rank"].tolist()
    assert abs(loaded.loc[0, "projected_points"] - selected.loc[0, "projected_points"]) <= 1e-12


def test_normalized_name_handles_suffix_punctuation_and_accents():
    assert normalize_player_name("Audric Estimé Jr.") == "audric estime jr"


def test_depth_audit_matches_by_gsis_before_name_team_aliases():
    board = select_top_300(_board())
    board.loc[0, ["player_name_clean", "team"]] = ["Different Display", "LAR"]
    depth = pd.DataFrame(
        [
            {
                "gsis_id": board.loc[0, "player_id"],
                "player_name": "Source Display",
                "team": "LA",
                "pos_abb": board.loc[0, "position"],
                "pos_rank": 1,
                "edgeiq_role": "STARTER",
                "dt": "2026-08-21T12:00:00+00:00",
            }
        ]
    )

    report, enriched = audit_depth_chart(board.iloc[:1], depth)

    assert report["matched_count"] == 1
    assert report["missing_players"] == []
    assert enriched.loc[0, "depth_match_method"] == "gsis_id"
    assert enriched.loc[0, "depth_source_position"] == board.loc[0, "position"]


def test_depth_audit_matches_suffix_variant_when_source_ids_disagree():
    board = select_top_300(_board()).iloc[:1].copy()
    board.loc[board.index[0], ["player_id", "player_name_clean", "team", "position"]] = [
        "00-0040878",
        "Mike Washington",
        "LV",
        "RB",
    ]
    depth = pd.DataFrame([
        {
            "gsis_id": "WAS569019",
            "player_name": "Mike Washington Jr.",
            "team": "LV",
            "pos_abb": "RB",
            "pos_rank": 2,
            "edgeiq_role": "BACKUP",
            "dt": "2026-08-21T07:40:57+00:00",
        }
    ])

    report, enriched = audit_depth_chart(board, depth)

    assert report["missing_players"] == []
    assert enriched.loc[0, "depth_match_method"] == "name_team_position_suffix"
    assert enriched.loc[0, "depth_pos_rank"] == 2
    assert enriched.loc[0, "depth_role"] == "BACKUP"


def test_final_depth_audit_refreshes_existing_projection_metadata_without_duplicate_columns():
    board = select_top_300(_board()).iloc[:1].copy()
    board["depth_match_method"] = "old_match"
    board["depth_pos_rank"] = 3
    board["depth_role"] = "DEPTH"
    board["depth_timestamp"] = "old"
    depth = pd.DataFrame([{
        "gsis_id": board.iloc[0]["player_id"],
        "player_name": board.iloc[0]["player_name_clean"],
        "team": board.iloc[0]["team"],
        "pos_abb": board.iloc[0]["position"],
        "pos_rank": 1,
        "edgeiq_role": "STARTER",
        "dt": "2026-08-21T12:00:00+00:00",
    }])

    _, enriched = audit_depth_chart(board, depth)

    assert enriched.columns.tolist().count("depth_role") == 1
    assert enriched.loc[0, "depth_role"] == "STARTER"
    assert enriched.loc[0, "depth_pos_rank"] == 1


def test_depth_audit_rejects_id_match_from_a_different_depth_position():
    board = select_top_300(_board()).iloc[:1].copy()
    board.loc[board.index[0], ["player_id", "player_name_clean", "team", "position"]] = [
        "fullback-1", "Generic Fullback", "AAA", "RB",
    ]
    depth = pd.DataFrame([{
        "gsis_id": "fullback-1",
        "player_name": "Generic Fullback",
        "team": "AAA",
        "pos_abb": "FB",
        "pos_rank": 1,
        "edgeiq_role": "STARTER",
        "dt": "2026-08-21T12:00:00+00:00",
    }])

    audit, enriched = audit_depth_chart(board, depth)

    assert audit["matched_count"] == 0
    assert enriched.loc[0, "depth_match_method"] == ""
    assert bool(enriched.loc[0, "depth_position_mismatch"]) is True
    assert enriched.loc[0, "depth_source_position"] == "FB"
    assert pd.isna(enriched.loc[0, "depth_role"])


def test_depth_audit_does_not_merge_ambiguous_suffix_stripped_identities():
    board = select_top_300(_board()).iloc[:1].copy()
    board.loc[board.index[0], ["player_id", "player_name_clean", "team", "position"]] = [
        "unmatched",
        "Alex Smith III",
        "LV",
        "RB",
    ]
    depth = pd.DataFrame([
        {"gsis_id": "one", "player_name": "Alex Smith", "team": "LV", "pos_abb": "RB", "pos_rank": 1},
        {"gsis_id": "two", "player_name": "Alex Smith Jr.", "team": "LV", "pos_abb": "RB", "pos_rank": 2},
    ])

    report, enriched = audit_depth_chart(board, depth)

    assert report["missing_players"] == ["Alex Smith III"]
    assert enriched.loc[0, "depth_match_method"] == ""


def test_depth_audit_treats_unsigned_player_as_not_applicable():
    board = select_top_300(_board()).iloc[:1].copy()
    board.loc[board.index[0], ["player_name_clean", "team"]] = ["Unsigned Veteran", pd.NA]
    board["is_unsigned_free_agent"] = True

    report, enriched = audit_depth_chart(board, pd.DataFrame())

    assert report["missing_players"] == []
    assert enriched.loc[0, "depth_match_method"] == "not_applicable_unsigned"


def test_rookie_audit_requires_complete_identity_capital_roster_and_role_review():
    rookie = select_top_300(_board()).iloc[:1].assign(
        is_rookie=True,
        rookie_year=2026,
        draft_number=12,
        status="ACT",
        on_current_roster=True,
        depth_pos_rank=2,
        depth_role="BACKUP",
    )

    report = audit_rookies(rookie, top_300=rookie, expected_scope_count=1)

    assert report["reviewed_count"] == 1
    assert report["failures"] == []
    assert report["players"][0]["projected_role"] == "BACKUP"


def test_rookie_audit_derives_expected_count_from_authoritative_scope():
    scope = pd.concat(
        [
            select_top_300(_board()).iloc[:1].assign(
                player_id=f"rookie-{index}",
                player_name_clean=f"Rookie {index}",
                draft_rank=index + 1,
                is_rookie=True,
                rookie_year=2026,
                draft_number=index + 1,
                status="ACT",
                on_current_roster=True,
                depth_pos_rank=2,
                depth_role="BACKUP",
            )
            for index in range(54)
        ],
        ignore_index=True,
    )

    report = audit_rookies(scope, top_300=scope)

    assert report["expected_scope_count"] == 54
    assert report["reviewed_count"] == 54
    assert report["failures"] == []


def test_rookie_audit_reviews_50_scope_players_when_only_49_are_top_300():
    scope = pd.concat(
        [
            select_top_300(_board()).iloc[:1].assign(
                player_id=f"rookie-{index}",
                player_name_clean=f"Rookie {index}",
                draft_rank=index + 1 if index < 49 else 302,
                is_rookie=True,
                rookie_year=2026,
                draft_number=index + 1,
                status="ACT",
                on_current_roster=True,
                depth_pos_rank=2,
                depth_role="BACKUP",
            )
            for index in range(50)
        ],
        ignore_index=True,
    )
    top_300 = scope.loc[scope["draft_rank"].le(300)].copy()

    report = audit_rookies(scope, top_300=top_300, expected_scope_count=50)

    assert report["reviewed_count"] == 50
    assert report["top_300_rookie_count"] == 49
    assert report["failures"] == []
    assert report["outside_top_300"] == [
        {"player_id": "rookie-49", "player_name": "Rookie 49", "draft_rank": 302}
    ]


def test_injury_audit_blocks_unreconciled_ir_pup_out_and_doubtful():
    injuries = pd.DataFrame(
        [
            {
                "player_name_clean": "Unresolved Player",
                "team": "CLE",
                "position": "WR",
                "is_currently_injured": True,
                "current_injury_status": "IR",
                "current_injury_body_part": "Knee",
                "current_injury_source": "Sleeper",
                "current_injury_source_timestamp": "",
                "current_injury_timeline_source": "",
                "current_injury_expected_return": "",
            }
        ]
    )

    report = audit_injuries(injuries, retrieved_at="2026-08-21T12:00:00+00:00")

    assert report["reviewed_count"] == 1
    assert report["blocking_players"] == ["Unresolved Player"]
