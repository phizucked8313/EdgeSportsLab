import json
from pathlib import Path

import pytest

from fantasy_draft_model.live_war_room import load_war_room_state
from fantasy_draft_model.state_persistence import (
    StateLoadError,
    inspect_state_files,
    recover_state_from_backup,
    state_backup_path,
)


def _canonical_state(*, draft_id="draft-one", updated_at="2026-08-20T12:00:00+00:00"):
    return {
        "schema_version": 2,
        "draft_id": draft_id,
        "created_at": "2026-08-20T12:00:00+00:00",
        "updated_at": updated_at,
        "status": "active",
        "total_picks": 180,
        "league_name": "Drunk Sundays",
        "league_key": "drunk_sundays",
        "user_team": "BLKWDW'S",
        "team_count": 12,
        "draft_rounds": 15,
        "current_pick": 1,
        "manual_picks": [],
        "keeper_reservations": [],
        "processed_keeper_picks": [],
    }


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _archive_files(archive_root):
    return [candidate for candidate in archive_root.rglob("*") if candidate.is_file()]


def test_inspection_reports_valid_backup_without_recovering_corrupt_authoritative(tmp_path):
    path = tmp_path / "war-room.json"
    backup = state_backup_path(path)
    valid_backup_state = _canonical_state()
    path.write_bytes(b"{broken")
    _write_json(backup, valid_backup_state)
    authoritative_before = path.read_bytes()
    backup_before = backup.read_bytes()

    result = inspect_state_files(path)

    assert result.state == valid_backup_state
    assert result.source == "backup"
    assert result.authoritative_error is not None
    assert result.backup_error is None
    assert result.authoritative_path == path
    assert result.backup_path == backup
    assert path.read_bytes() == authoritative_before
    assert backup.read_bytes() == backup_before


def test_load_rejects_invalid_authoritative_even_when_backup_is_valid(tmp_path):
    path = tmp_path / "war-room.json"
    path.write_bytes(b"{broken")
    _write_json(state_backup_path(path), _canonical_state())

    with pytest.raises(StateLoadError) as raised:
        load_war_room_state(path, keeper_loader=lambda _league_name: None)

    assert raised.value.inspection.source == "backup"
    assert path.read_bytes() == b"{broken"


def test_inspection_reports_missing_authoritative_and_valid_backup(tmp_path):
    path = tmp_path / "war-room.json"
    backup_state = _canonical_state()
    _write_json(state_backup_path(path), backup_state)

    result = inspect_state_files(path)

    assert result.state == backup_state
    assert result.source == "backup"
    assert isinstance(result.authoritative_error, FileNotFoundError)
    assert result.backup_error is None
    assert not path.exists()


def test_inspection_uses_valid_authoritative_and_reports_invalid_backup(tmp_path):
    path = tmp_path / "war-room.json"
    authoritative_state = _canonical_state()
    _write_json(path, authoritative_state)
    state_backup_path(path).write_bytes(b"{broken-backup")

    result = inspect_state_files(path)

    assert result.state == authoritative_state
    assert result.source == "authoritative"
    assert result.authoritative_error is None
    assert result.backup_error is not None


def test_inspection_reports_both_invalid_without_selecting_state(tmp_path):
    path = tmp_path / "war-room.json"
    path.write_bytes(b"{broken-authoritative")
    state_backup_path(path).write_bytes(b"{broken-backup")

    result = inspect_state_files(path)

    assert result.state is None
    assert result.source is None
    assert result.authoritative_error is not None
    assert result.backup_error is not None


def test_recovery_archives_corrupt_bytes_and_atomically_restores_backup(tmp_path):
    path = tmp_path / "war-room.json"
    backup = state_backup_path(path)
    archive_root = tmp_path / "archives"
    valid_backup_state = _canonical_state(draft_id="draft:/ unsafe")
    path.write_bytes(b"{broken")
    _write_json(backup, valid_backup_state)

    restored = recover_state_from_backup(path, archive_root)

    assert restored == valid_backup_state
    assert json.loads(path.read_text(encoding="utf-8")) == valid_backup_state
    archived = _archive_files(archive_root)
    assert len(archived) == 1
    assert archived[0].read_bytes() == b"{broken"
    assert ":" not in archived[0].name
    assert "/" not in archived[0].name
    assert json.loads(backup.read_text(encoding="utf-8")) == valid_backup_state


def test_recovery_restores_valid_backup_when_authoritative_is_missing(tmp_path):
    path = tmp_path / "war-room.json"
    archive_root = tmp_path / "archives"
    valid_backup_state = _canonical_state()
    _write_json(state_backup_path(path), valid_backup_state)

    restored = recover_state_from_backup(path, archive_root)

    assert restored == valid_backup_state
    assert json.loads(path.read_text(encoding="utf-8")) == valid_backup_state
    assert _archive_files(archive_root) == []


def test_recovery_rejects_invalid_backup_and_preserves_both_artifacts(tmp_path):
    path = tmp_path / "war-room.json"
    backup = state_backup_path(path)
    path.write_bytes(b"{broken-authoritative")
    backup.write_bytes(b"{broken-backup")

    with pytest.raises(StateLoadError) as raised:
        recover_state_from_backup(path, tmp_path / "archives")

    assert raised.value.inspection.state is None
    assert path.read_bytes() == b"{broken-authoritative"
    assert backup.read_bytes() == b"{broken-backup"


def test_archive_verification_failure_preserves_original_artifacts(tmp_path):
    path = tmp_path / "war-room.json"
    backup = state_backup_path(path)
    path.write_bytes(b"{broken")
    _write_json(backup, _canonical_state())
    authoritative_before = path.read_bytes()
    backup_before = backup.read_bytes()

    def write_truncated_archive(destination, source_bytes):
        with Path(destination).open("xb") as file:
            file.write(source_bytes[:-1])

    with pytest.raises(OSError, match="verification"):
        recover_state_from_backup(
            path,
            tmp_path / "archives",
            archive_write_func=write_truncated_archive,
        )

    assert path.read_bytes() == authoritative_before
    assert backup.read_bytes() == backup_before


def test_recovery_replacement_failure_preserves_original_artifacts(tmp_path):
    path = tmp_path / "war-room.json"
    backup = state_backup_path(path)
    path.write_bytes(b"{broken")
    _write_json(backup, _canonical_state())
    authoritative_before = path.read_bytes()
    backup_before = backup.read_bytes()

    def fail_authoritative_replace(source, target):
        if Path(target) == path:
            raise OSError("injected recovery replacement failure")
        return Path(source).replace(target)

    with pytest.raises(OSError, match="injected recovery"):
        recover_state_from_backup(
            path,
            tmp_path / "archives",
            replace_func=fail_authoritative_replace,
        )

    assert path.read_bytes() == authoritative_before
    assert backup.read_bytes() == backup_before
