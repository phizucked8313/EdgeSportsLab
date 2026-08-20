import copy
import json
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

import pytest

import fantasy_draft_model.draft_lifecycle as lifecycle
from fantasy_draft_model.draft_lifecycle import (
    archive_state_artifacts,
    inspect_draft_lifecycle,
    recover_existing_draft,
    resume_existing_draft,
    start_new_draft,
)
from fantasy_draft_model.keepers import load_keepers
from fantasy_draft_model.live_war_room import (
    build_keeper_reservations,
    load_war_room_state,
    resolve_league,
    save_war_room_state,
)
from fantasy_draft_model.state_persistence import (
    StateLoadError,
    save_validated_state,
    state_backup_path,
)
from fantasy_draft_model.war_room_state import StateValidationError


FIXED_NOW = datetime(2026, 8, 20, 18, 0, tzinfo=timezone.utc)
FIXED_NOW_ISO = FIXED_NOW.isoformat()


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _manual_pick(pick_number, *, player_name=None):
    league = resolve_league("drunk_sundays")
    team_count = int(league["team_count"])
    round_number = ((pick_number - 1) // team_count) + 1
    pick_in_round = ((pick_number - 1) % team_count) + 1
    draft_slot = (
        pick_in_round
        if round_number % 2
        else team_count - pick_in_round + 1
    )
    return {
        "player_name": player_name or f"Rehearsal Player {pick_number}",
        "position": "WR",
        "nfl_team": "CLE",
        "bye_week": 10,
        "draft_rank": pick_number,
        "fantasy_team": league["draft_order"][draft_slot - 1],
        "pick_number": pick_number,
        "round": round_number,
        "draft_slot": draft_slot,
    }


def _canonical_keepers():
    league = resolve_league("drunk_sundays")
    return build_keeper_reservations(league, load_keepers(league["name"]))


def _schema_two_state(*, draft_id="existing-draft", current_pick=13):
    league = resolve_league("drunk_sundays")
    keepers = _canonical_keepers()
    reserved = {item["pick_number"] for item in keepers}
    manual_picks = [
        _manual_pick(number)
        for number in range(1, current_pick)
        if number not in reserved
    ]
    processed = sorted(number for number in reserved if number < current_pick)
    return {
        "schema_version": 2,
        "draft_id": draft_id,
        "created_at": "2026-08-20T16:00:00+00:00",
        "updated_at": "2026-08-20T17:00:00+00:00",
        "status": "active",
        "total_picks": 180,
        "league_name": league["name"],
        "league_key": league["league_key"],
        "user_team": league["user_team"],
        "team_count": int(league["team_count"]),
        "draft_rounds": int(league["draft_rounds"]),
        "current_pick": current_pick,
        "manual_picks": manual_picks,
        "keeper_reservations": keepers,
        "processed_keeper_picks": processed,
    }


def _schema_one_rehearsal_state():
    state = _schema_two_state(current_pick=13)
    for field in (
        "draft_id",
        "created_at",
        "updated_at",
        "status",
        "total_picks",
    ):
        del state[field]
    state["schema_version"] = 1
    return state


def _first_non_keeper_pick(reservations):
    reserved = {item["pick_number"] for item in reservations}
    return next(number for number in range(1, 181) if number not in reserved)


def _artifact_bytes(path):
    candidates = [
        path,
        state_backup_path(path),
        path.with_name(f"{path.stem}.recovery{path.suffix}"),
    ]
    return {candidate: candidate.read_bytes() for candidate in candidates}


def test_inspection_reports_existing_progress_without_mutating_state(tmp_path):
    path = tmp_path / "war-room.json"
    state = _schema_two_state()
    _write_json(path, state)
    before = path.read_bytes()

    inspection = inspect_draft_lifecycle(path, now_func=lambda: FIXED_NOW)

    assert inspection.requires_choice is True
    assert inspection.can_resume is True
    assert inspection.can_recover is False
    assert inspection.completed_slots == 12
    assert inspection.total_slots == 180
    assert inspection.manual_pick_count == 12
    assert inspection.keeper_count == 15
    assert inspection.state_age_seconds == 3600
    assert inspection.draft_id == "existing-draft"
    assert inspection.status == "active"
    assert path.read_bytes() == before
    assert list(tmp_path.iterdir()) == [path]


def test_missing_state_still_requires_explicit_start_without_creating_artifacts(tmp_path):
    path = tmp_path / "war-room.json"

    inspection = inspect_draft_lifecycle(path, now_func=lambda: FIXED_NOW)

    assert inspection.requires_choice is True
    assert inspection.can_resume is False
    assert inspection.can_recover is False
    assert inspection.state is None
    assert list(tmp_path.iterdir()) == []


def test_archive_copies_every_artifact_verifies_manifest_and_never_overwrites(tmp_path):
    path = tmp_path / "war-room.json"
    archive_root = tmp_path / "archives"
    _write_json(path, _schema_two_state())
    _write_json(state_backup_path(path), _schema_two_state(draft_id="backup-draft"))
    recovery_path = path.with_name(f"{path.stem}.recovery{path.suffix}")
    recovery_path.write_bytes(b'{"recovery": "metadata"}\n')
    before = _artifact_bytes(path)

    first = archive_state_artifacts(
        path,
        archive_root,
        now_func=lambda: FIXED_NOW,
        id_func=lambda: "same-id",
    )
    second = archive_state_artifacts(
        path,
        archive_root,
        now_func=lambda: FIXED_NOW,
        id_func=lambda: "same-id",
    )

    assert first != second
    assert first.is_dir()
    assert second.is_dir()
    manifest = json.loads((first / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["timestamp"] == FIXED_NOW_ISO
    assert {entry["role"] for entry in manifest["artifacts"]} == {
        "authoritative",
        "backup",
        "recovery_metadata",
    }
    assert len(manifest["artifacts"]) == 3
    for entry in manifest["artifacts"]:
        source = Path(entry["source_path"])
        archived = Path(entry["archive_path"])
        assert archived.parent == first
        assert archived.read_bytes() == before[source]
        assert entry["byte_length"] == len(before[source])
        assert entry["sha256"] == sha256(before[source]).hexdigest()
    assert _artifact_bytes(path) == before
    assert not list(first.glob("*.tmp-*"))


def test_archive_verification_failure_preserves_all_source_bytes(tmp_path):
    path = tmp_path / "war-room.json"
    archive_root = tmp_path / "archives"
    _write_json(path, _schema_two_state())
    _write_json(state_backup_path(path), _schema_two_state(draft_id="backup-draft"))
    recovery_path = path.with_name(f"{path.stem}.recovery{path.suffix}")
    recovery_path.write_bytes(b"metadata")
    before = _artifact_bytes(path)

    def corrupt_copy(source, destination):
        Path(destination).write_bytes(Path(source).read_bytes() + b"corrupt")

    with pytest.raises(OSError, match="archive verification failed"):
        archive_state_artifacts(
            path,
            archive_root,
            copy_func=corrupt_copy,
        )

    assert _artifact_bytes(path) == before


def test_start_new_archives_before_initializing_and_reloads_canonical_keepers(
    tmp_path,
):
    path = tmp_path / "war-room.json"
    archive_root = tmp_path / "archives"
    old_state = _schema_two_state()
    save_validated_state(old_state, path)
    save_validated_state(
        _schema_two_state(draft_id="newer-old-state"),
        path,
    )
    sources_before = {
        path: path.read_bytes(),
        state_backup_path(path): state_backup_path(path).read_bytes(),
    }

    fresh = start_new_draft(
        "drunk_sundays",
        path,
        archive_root,
        now_func=lambda: FIXED_NOW,
        id_func=lambda: "fresh-draft-id",
    )

    expected_keepers = _canonical_keepers()
    assert fresh["draft_id"] == "fresh-draft-id"
    assert fresh["created_at"] == FIXED_NOW_ISO
    assert fresh["updated_at"] == FIXED_NOW_ISO
    assert fresh["current_pick"] == _first_non_keeper_pick(expected_keepers)
    assert fresh["manual_picks"] == []
    assert fresh["keeper_reservations"] == expected_keepers
    archive_dir = next(candidate for candidate in archive_root.iterdir() if candidate.is_dir())
    manifest = json.loads((archive_dir / "manifest.json").read_text(encoding="utf-8"))
    archived_by_source = {
        Path(entry["source_path"]): Path(entry["archive_path"]).read_bytes()
        for entry in manifest["artifacts"]
    }
    assert archived_by_source == sources_before
    assert json.loads(path.read_text(encoding="utf-8")) == fresh


def test_start_initialization_failure_preserves_authoritative_and_backup(tmp_path, monkeypatch):
    path = tmp_path / "war-room.json"
    archive_root = tmp_path / "archives"
    save_validated_state(_schema_two_state(), path)
    save_validated_state(_schema_two_state(draft_id="newer-old-state"), path)
    before = {
        path: path.read_bytes(),
        state_backup_path(path): state_backup_path(path).read_bytes(),
    }

    def fail_initialization(*args, **kwargs):
        raise RuntimeError("injected initialization failure")

    monkeypatch.setattr(lifecycle, "initialize_war_room", fail_initialization)

    with pytest.raises(RuntimeError, match="injected initialization"):
        start_new_draft("drunk_sundays", path, archive_root)

    assert {candidate: candidate.read_bytes() for candidate in before} == before
    assert list(archive_root.rglob("manifest.json"))


def test_start_partial_initialization_failure_cannot_write_authoritative_path(
    tmp_path,
    monkeypatch,
):
    path = tmp_path / "war-room.json"
    archive_root = tmp_path / "archives"
    save_validated_state(_schema_two_state(), path)
    save_validated_state(_schema_two_state(draft_id="newer-old-state"), path)
    before = {
        path: path.read_bytes(),
        state_backup_path(path): state_backup_path(path).read_bytes(),
    }

    def write_then_fail(league_key, state_path, **kwargs):
        Path(state_path).write_bytes(b"partial initialization")
        raise RuntimeError("injected partial initialization failure")

    monkeypatch.setattr(lifecycle, "initialize_war_room", write_then_fail)

    with pytest.raises(RuntimeError, match="partial initialization"):
        start_new_draft("drunk_sundays", path, archive_root)

    assert {candidate: candidate.read_bytes() for candidate in before} == before


def test_start_has_no_fallible_reload_after_canonical_replacement(tmp_path, monkeypatch):
    path = tmp_path / "war-room.json"
    archive_root = tmp_path / "archives"
    save_validated_state(_schema_two_state(), path)
    save_validated_state(_schema_two_state(draft_id="newer-old-state"), path)
    before = {
        path: path.read_bytes(),
        state_backup_path(path): state_backup_path(path).read_bytes(),
    }

    def fail_reload(*args, **kwargs):
        raise RuntimeError("injected post-write reload failure")

    monkeypatch.setattr(lifecycle, "load_war_room_state", fail_reload)

    try:
        fresh = start_new_draft("drunk_sundays", path, archive_root)
    except RuntimeError:
        assert {candidate: candidate.read_bytes() for candidate in before} == before
        raise

    assert fresh["schema_version"] == 2
    assert fresh["manual_picks"] == []


def test_start_has_no_late_keeper_load_after_canonical_replacement(tmp_path):
    path = tmp_path / "war-room.json"
    archive_root = tmp_path / "archives"
    save_validated_state(_schema_two_state(), path)
    save_validated_state(_schema_two_state(draft_id="newer-old-state"), path)
    before = {
        path: path.read_bytes(),
        state_backup_path(path): state_backup_path(path).read_bytes(),
    }
    load_count = 0

    def fail_third_keeper_load(league_name):
        nonlocal load_count
        load_count += 1
        if load_count == 3:
            raise RuntimeError("injected late keeper-loader failure")
        return load_keepers(league_name)

    try:
        fresh = start_new_draft(
            "drunk_sundays",
            path,
            archive_root,
            keeper_loader=fail_third_keeper_load,
        )
    except RuntimeError:
        assert {candidate: candidate.read_bytes() for candidate in before} == before
        raise

    assert load_count == 2
    assert fresh["keeper_reservations"] == _canonical_keepers()


def test_resume_valid_schema_two_never_initializes_or_rewrites(tmp_path, monkeypatch):
    path = tmp_path / "war-room.json"
    state = _schema_two_state()
    _write_json(path, state)
    before = path.read_bytes()

    def reject_initialization(*args, **kwargs):
        raise AssertionError("resume initialized a new draft")

    monkeypatch.setattr(lifecycle, "initialize_war_room", reject_initialization)

    resumed = resume_existing_draft(path)

    assert resumed == state
    assert path.read_bytes() == before


def test_legacy_inspection_is_read_only_and_explicit_resume_archives_then_migrates(tmp_path):
    path = tmp_path / "war-room.json"
    legacy = _schema_one_rehearsal_state()
    _write_json(path, legacy)
    before = path.read_bytes()

    inspection = inspect_draft_lifecycle(path, now_func=lambda: FIXED_NOW)

    assert inspection.requires_choice is True
    assert inspection.is_legacy is True
    assert inspection.can_resume is True
    assert inspection.completed_slots == 12
    assert inspection.manual_pick_count == 12
    assert inspection.keeper_count == 15
    assert path.read_bytes() == before
    assert not (tmp_path / "archives").exists()

    migrated = resume_existing_draft(
        path,
        now_func=lambda: FIXED_NOW,
        id_func=lambda: "migrated-draft-id",
    )

    assert migrated["schema_version"] == 2
    assert migrated["draft_id"] == "migrated-draft-id"
    assert migrated["manual_picks"] == legacy["manual_picks"]
    assert migrated["keeper_reservations"] == legacy["keeper_reservations"]
    assert json.loads(path.read_text(encoding="utf-8")) == migrated
    manifest_path = next((tmp_path / "archives").rglob("manifest.json"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    authoritative_entry = next(
        entry for entry in manifest["artifacts"] if entry["role"] == "authoritative"
    )
    assert Path(authoritative_entry["archive_path"]).read_bytes() == before


def test_legacy_resume_has_no_fallible_reload_after_canonical_replacement(
    tmp_path,
    monkeypatch,
):
    path = tmp_path / "war-room.json"
    legacy = _schema_one_rehearsal_state()
    _write_json(path, legacy)
    _write_json(state_backup_path(path), _schema_two_state(draft_id="backup-state"))
    before = {
        path: path.read_bytes(),
        state_backup_path(path): state_backup_path(path).read_bytes(),
    }

    def fail_reload(*args, **kwargs):
        raise RuntimeError("injected post-write reload failure")

    monkeypatch.setattr(lifecycle, "load_war_room_state", fail_reload)

    try:
        migrated = resume_existing_draft(path)
    except RuntimeError:
        assert {candidate: candidate.read_bytes() for candidate in before} == before
        raise

    assert migrated["schema_version"] == 2
    assert migrated["manual_picks"] == legacy["manual_picks"]


def test_legacy_resume_has_no_late_keeper_load_after_canonical_replacement(tmp_path):
    path = tmp_path / "war-room.json"
    legacy = _schema_one_rehearsal_state()
    _write_json(path, legacy)
    _write_json(state_backup_path(path), _schema_two_state(draft_id="backup-state"))
    before = {
        path: path.read_bytes(),
        state_backup_path(path): state_backup_path(path).read_bytes(),
    }
    load_count = 0

    def fail_fourth_keeper_load(league_name):
        nonlocal load_count
        load_count += 1
        if load_count == 4:
            raise RuntimeError("injected late keeper-loader failure")
        return load_keepers(league_name)

    try:
        migrated = resume_existing_draft(
            path,
            keeper_loader=fail_fourth_keeper_load,
        )
    except RuntimeError:
        assert {candidate: candidate.read_bytes() for candidate in before} == before
        raise

    assert load_count == 3
    assert migrated["keeper_reservations"] == legacy["keeper_reservations"]


def test_explicit_start_archives_rehearsal_shape_and_uses_current_keeper_data(tmp_path):
    path = tmp_path / "war-room.json"
    archive_root = tmp_path / "archives"
    legacy = _schema_one_rehearsal_state()
    _write_json(path, legacy)
    source_bytes = path.read_bytes()

    fresh = start_new_draft(
        "drunk_sundays",
        path,
        archive_root,
        now_func=lambda: FIXED_NOW,
        id_func=lambda: "fresh-after-rehearsal",
    )

    assert fresh["manual_picks"] == []
    assert fresh["keeper_reservations"] == _canonical_keepers()
    manifest_path = next(archive_root.rglob("manifest.json"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    archived = next(
        Path(entry["archive_path"])
        for entry in manifest["artifacts"]
        if entry["role"] == "authoritative"
    )
    assert archived.read_bytes() == source_bytes


def test_recover_existing_draft_delegates_only_to_explicit_validated_recovery(tmp_path):
    path = tmp_path / "war-room.json"
    archive_root = tmp_path / "archives"
    valid_backup = _schema_two_state(draft_id="backup-draft")
    path.write_bytes(b"{broken")
    _write_json(state_backup_path(path), valid_backup)
    corrupt_before = path.read_bytes()

    inspection = inspect_draft_lifecycle(path)
    assert inspection.can_resume is False
    assert inspection.can_recover is True
    assert path.read_bytes() == corrupt_before

    recovered = recover_existing_draft(path, archive_root)

    assert recovered == valid_backup
    assert json.loads(path.read_text(encoding="utf-8")) == valid_backup
    assert any(candidate.read_bytes() == corrupt_before for candidate in archive_root.iterdir())


def test_semantically_stale_authoritative_uses_current_keepers_to_offer_backup_recovery(
    tmp_path,
):
    """A schema-valid but stale keeper declaration is not a resumable draft."""
    path = tmp_path / "war-room.json"
    archive_root = tmp_path / "archives"
    backup_state = _schema_two_state(draft_id="canonical-backup")
    authoritative_state = _schema_two_state(draft_id="stale-authoritative")
    save_validated_state(backup_state, path)
    save_validated_state(authoritative_state, path)

    stale = json.loads(path.read_text(encoding="utf-8"))
    stale["keeper_reservations"][-1]["player_name"] = "Stale Keeper Declaration"
    _write_json(path, stale)

    inspection = inspect_draft_lifecycle(path)

    assert inspection.can_resume is False
    assert inspection.can_recover is True
    assert inspection.source == "backup"
    assert "keeper_reservations" in str(inspection.authoritative_error)
    assert inspection.state == backup_state

    with pytest.raises(StateLoadError) as raised:
        load_war_room_state(path)
    assert raised.value.inspection.source == "backup"

    recovered = recover_existing_draft(path, archive_root)

    assert recovered == backup_state
    assert json.loads(path.read_text(encoding="utf-8")) == backup_state


def test_save_war_room_state_rejects_structurally_valid_stale_keeper_state(tmp_path):
    path = tmp_path / "war-room.json"
    stale = _schema_two_state(draft_id="stale-at-save")
    stale["keeper_reservations"][-1]["player_name"] = "Stale Keeper Declaration"

    with pytest.raises(StateValidationError, match="keeper_reservations"):
        save_war_room_state(stale, path)

    assert not path.exists()
    assert not state_backup_path(path).exists()


def test_explicit_recovery_writes_truthful_atomic_recovery_metadata(tmp_path):
    path = tmp_path / "war-room.json"
    archive_root = tmp_path / "archives"
    backup = state_backup_path(path)
    corrupt_bytes = b"{corrupt authoritative state"
    valid_backup = _schema_two_state(draft_id="metadata-backup")
    path.write_bytes(corrupt_bytes)
    _write_json(backup, valid_backup)

    recovered = recover_existing_draft(path, archive_root)
    metadata_path = lifecycle.state_recovery_metadata_path(path)
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    assert recovered == valid_backup
    assert metadata["source"] == "backup"
    assert metadata["backup_path"] == str(backup.resolve())
    assert Path(metadata["archive_path"]).read_bytes() == corrupt_bytes
    assert metadata["recovered_at"].endswith("+00:00")
    assert metadata["authoritative_sha256"] == sha256(path.read_bytes()).hexdigest()
    assert metadata["backup_sha256"] == sha256(backup.read_bytes()).hexdigest()


def test_recovery_metadata_write_failure_does_not_report_a_committed_restore_as_failed(tmp_path):
    path = tmp_path / "war-room.json"
    archive_root = tmp_path / "archives"
    backup = state_backup_path(path)
    valid_backup = _schema_two_state(draft_id="metadata-write-failure")
    path.write_bytes(b"{corrupt authoritative state")
    _write_json(backup, valid_backup)
    backup_before = backup.read_bytes()

    def fail_metadata_write(*_args, **_kwargs):
        raise OSError("injected metadata write failure")

    recovered = recover_existing_draft(
        path,
        archive_root,
        recovery_metadata_writer=fail_metadata_write,
    )

    assert recovered == valid_backup
    assert json.loads(path.read_text(encoding="utf-8")) == valid_backup
    assert backup.read_bytes() == backup_before
