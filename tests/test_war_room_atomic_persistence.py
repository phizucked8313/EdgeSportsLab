import copy
import json
import os
from pathlib import Path

import pytest

import fantasy_draft_model.state_persistence as persistence
from fantasy_draft_model.state_persistence import (
    StateLoadError,
    atomic_write_json,
    save_validated_state,
    state_backup_path,
)
from fantasy_draft_model.war_room_state import (
    StateValidationError,
    validate_war_room_state,
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


def _load_json(path):
    with Path(path).open("r", encoding="utf-8") as file:
        return json.load(file)


def test_successive_saves_rotate_last_known_good_state_to_backup(tmp_path):
    path = tmp_path / "war-room.json"
    state_one = _canonical_state()
    state_two = _canonical_state(
        draft_id="draft-two",
        updated_at="2026-08-20T12:01:00+00:00",
    )

    save_validated_state(state_one, path)
    save_validated_state(state_two, path)

    assert _load_json(path) == state_two
    assert _load_json(state_backup_path(path)) == state_one
    assert not list(tmp_path.glob("*.tmp-*"))


def test_authoritative_bytes_survive_failure_before_replacement(tmp_path):
    path = tmp_path / "war-room.json"
    backup = state_backup_path(path)
    state_one = _canonical_state()
    state_two = _canonical_state(
        draft_id="draft-two",
        updated_at="2026-08-20T12:01:00+00:00",
    )
    state_three = _canonical_state(
        draft_id="draft-three",
        updated_at="2026-08-20T12:02:00+00:00",
    )
    save_validated_state(state_one, path)
    save_validated_state(state_two, path)
    authoritative_before = path.read_bytes()
    backup_before = backup.read_bytes()
    fsynced = []

    def fail_authoritative_replace(source, target):
        if Path(target) == path:
            raise OSError("injected authoritative replacement failure")
        return Path(source).replace(target)

    def recording_fsync(file_descriptor):
        fsynced.append(file_descriptor)
        os.fsync(file_descriptor)

    with pytest.raises(OSError, match="injected authoritative"):
        atomic_write_json(
            path,
            state_three,
            validate_war_room_state,
            replace_func=fail_authoritative_replace,
            fsync_func=recording_fsync,
        )

    assert path.read_bytes() == authoritative_before
    assert backup.read_bytes() == backup_before
    assert fsynced
    assert not list(tmp_path.glob("*.tmp-*"))


def test_candidate_validation_failure_changes_neither_state_file(tmp_path):
    path = tmp_path / "war-room.json"
    state_one = _canonical_state()
    state_two = _canonical_state(
        draft_id="draft-two",
        updated_at="2026-08-20T12:01:00+00:00",
    )
    save_validated_state(state_one, path)
    save_validated_state(state_two, path)
    authoritative_before = path.read_bytes()
    backup_before = state_backup_path(path).read_bytes()
    invalid = copy.deepcopy(state_two)
    invalid["current_pick"] = 0
    fsynced = []

    with pytest.raises(StateValidationError, match="current_pick"):
        atomic_write_json(
            path,
            invalid,
            validate_war_room_state,
            fsync_func=fsynced.append,
        )

    assert path.read_bytes() == authoritative_before
    assert state_backup_path(path).read_bytes() == backup_before
    assert fsynced == []
    assert not list(tmp_path.glob("*.tmp-*"))


@pytest.mark.parametrize(
    "authoritative_bytes",
    [
        b"{malformed",
        json.dumps({**_canonical_state(), "current_pick": 0}).encode("utf-8"),
    ],
    ids=["malformed-json", "invalid-state"],
)
def test_routine_save_refuses_to_replace_corrupt_authoritative_state(
    tmp_path,
    authoritative_bytes,
):
    path = tmp_path / "war-room.json"
    backup = state_backup_path(path)
    state_one = _canonical_state()
    state_two = _canonical_state(
        draft_id="draft-two",
        updated_at="2026-08-20T12:01:00+00:00",
    )
    candidate = _canonical_state(
        draft_id="draft-three",
        updated_at="2026-08-20T12:02:00+00:00",
    )
    save_validated_state(state_one, path)
    save_validated_state(state_two, path)
    path.write_bytes(authoritative_bytes)
    authoritative_before = path.read_bytes()
    backup_before = backup.read_bytes()

    with pytest.raises(StateLoadError) as raised:
        save_validated_state(candidate, path)

    assert raised.value.inspection.authoritative_error is not None
    assert path.read_bytes() == authoritative_before
    assert backup.read_bytes() == backup_before
    assert not list(tmp_path.glob("*.tmp-*"))


def test_public_save_does_not_write_text_to_authoritative_path(tmp_path, monkeypatch):
    path = tmp_path / "war-room.json"
    original_write_text = Path.write_text

    def reject_authoritative_write_text(self, *args, **kwargs):
        if self == path:
            raise AssertionError("authoritative Path.write_text was used")
        return original_write_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", reject_authoritative_write_text)

    save_validated_state(_canonical_state(), path)

    assert _load_json(path) == _canonical_state()


def test_exclusive_temp_collision_does_not_delete_another_attempts_file(
    tmp_path,
    monkeypatch,
):
    path = tmp_path / "war-room.json"
    occupied_temp = tmp_path / "war-room.json.tmp-occupied"
    occupied_temp.write_bytes(b"another attempt")
    monkeypatch.setattr(
        persistence,
        "_temporary_sibling",
        lambda target: occupied_temp,
    )

    with pytest.raises(FileExistsError):
        save_validated_state(_canonical_state(), path)

    assert occupied_temp.read_bytes() == b"another attempt"
    assert not path.exists()
