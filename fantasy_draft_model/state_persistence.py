"""Atomic persistence primitives for validated War Room state."""

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from fantasy_draft_model.war_room_state import validate_war_room_state


@dataclass(frozen=True)
class StateLoadResult:
    """Validated view of authoritative and backup state artifacts."""

    state: dict | None
    source: str | None
    authoritative_error: Exception | None
    backup_error: Exception | None
    authoritative_path: Path
    backup_path: Path


class StateLoadError(RuntimeError):
    """Raised when authoritative state cannot be safely loaded or recovered."""

    def __init__(self, inspection, message="Authoritative War Room state is unavailable"):
        self.inspection = inspection
        super().__init__(message)


def state_backup_path(path):
    """Return the deterministic last-known-good sibling for *path*."""
    path = Path(path)
    if path.suffix:
        return path.with_name(f"{path.stem}.backup{path.suffix}")
    return path.with_name(f"{path.name}.backup")


def _load_validated_json(path, validator):
    with Path(path).open("r", encoding="utf-8") as file:
        payload = json.load(file)
    return validator(payload)


def _temporary_sibling(path):
    path = Path(path)
    return path.with_name(f"{path.name}.tmp-{uuid4().hex}")


def _serialize_validated(payload, validator):
    validator(payload)
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def _write_validated_temporary(path, serialized, validator, fsync_func):
    temporary = _temporary_sibling(path)
    created = False
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as file:
            created = True
            file.write(serialized)
            file.flush()
            fsync_func(file.fileno())
        _load_validated_json(temporary, validator)
        return temporary
    except Exception:
        if created:
            temporary.unlink(missing_ok=True)
        raise


def atomic_write_json(
    path,
    payload,
    validator,
    *,
    replace_func=None,
    fsync_func=os.fsync,
    allow_invalid_authoritative=False,
):
    """Atomically persist validated JSON while rotating a valid old state."""
    path = Path(path)
    candidate_json = _serialize_validated(payload, validator)
    path.parent.mkdir(parents=True, exist_ok=True)
    replace_func = replace_func or Path.replace
    created_temporaries = []

    try:
        current_state = _load_validated_json(path, validator)
    except FileNotFoundError:
        current_state = None
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        if not allow_invalid_authoritative:
            raise StateLoadError(
                inspect_state_files(path),
                "Routine save refused to replace invalid authoritative state",
            ) from error
        current_state = None

    try:
        candidate = _write_validated_temporary(
            path,
            candidate_json,
            validator,
            fsync_func,
        )
        created_temporaries.append(candidate)

        if current_state is not None:
            backup_path = state_backup_path(path)
            backup_json = _serialize_validated(current_state, validator)
            backup_candidate = _write_validated_temporary(
                backup_path,
                backup_json,
                validator,
                fsync_func,
            )
            created_temporaries.append(backup_candidate)

        replace_func(candidate, path)
        authoritative_state = _load_validated_json(path, validator)
        if current_state is not None:
            replace_func(backup_candidate, backup_path)
        return authoritative_state
    finally:
        for temporary in created_temporaries:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def save_validated_state(state, path):
    """Persist one schema-2 War Room state through the atomic writer."""
    return atomic_write_json(path, state, validate_war_room_state)


def _inspect_one(path):
    try:
        return _load_validated_json(path, validate_war_room_state), None
    except Exception as error:
        return None, error


def inspect_state_files(path):
    """Validate state artifacts without modifying or silently recovering them."""
    authoritative_path = Path(path)
    backup_path = state_backup_path(authoritative_path)
    authoritative_state, authoritative_error = _inspect_one(authoritative_path)
    backup_state, backup_error = _inspect_one(backup_path)

    if authoritative_error is None:
        state = authoritative_state
        source = "authoritative"
    elif backup_error is None:
        state = backup_state
        source = "backup"
    else:
        state = None
        source = None

    return StateLoadResult(
        state=state,
        source=source,
        authoritative_error=authoritative_error,
        backup_error=backup_error,
        authoritative_path=authoritative_path,
        backup_path=backup_path,
    )


def _safe_archive_component(value):
    component = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value)).strip("-._")
    return component or "unknown-draft"


def _archive_destination(path, archive_root, draft_id):
    archive_root = Path(archive_root)
    archive_root.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    draft_component = _safe_archive_component(draft_id)
    base_name = f"{timestamp}-{draft_component}-{_safe_archive_component(path.name)}.corrupt"
    destination = archive_root / base_name
    counter = 1
    while destination.exists():
        destination = archive_root / f"{base_name}.{counter}"
        counter += 1
    return destination


def _write_archive_bytes(destination, source_bytes):
    with Path(destination).open("xb") as file:
        file.write(source_bytes)
        file.flush()
        os.fsync(file.fileno())


def _archive_corrupt_authoritative(
    path,
    archive_root,
    draft_id,
    archive_write_func,
):
    source_bytes = Path(path).read_bytes()
    destination = _archive_destination(path, archive_root, draft_id)
    archive_write_func(destination, source_bytes)
    archived_bytes = destination.read_bytes()
    if (
        len(archived_bytes) != len(source_bytes)
        or sha256(archived_bytes).digest() != sha256(source_bytes).digest()
    ):
        raise OSError(f"archive verification failed for {destination}")
    return destination


def recover_state_from_backup(
    path,
    archive_root,
    *,
    replace_func=None,
    fsync_func=os.fsync,
    archive_write_func=_write_archive_bytes,
):
    """Explicitly archive bad evidence and restore a validated backup."""
    inspection = inspect_state_files(path)
    if inspection.source != "backup":
        raise StateLoadError(
            inspection,
            "Recovery requires an invalid or missing authoritative state and a valid backup",
        )

    if inspection.authoritative_path.exists():
        _archive_corrupt_authoritative(
            inspection.authoritative_path,
            archive_root,
            inspection.state["draft_id"],
            archive_write_func,
        )

    atomic_write_json(
        inspection.authoritative_path,
        inspection.state,
        validate_war_room_state,
        replace_func=replace_func,
        fsync_func=fsync_func,
        allow_invalid_authoritative=True,
    )
    return _load_validated_json(
        inspection.authoritative_path,
        validate_war_room_state,
    )
