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


def _write_exact_temporary(path, payload, fsync_func):
    """Write exact bytes to a sibling temporary for transaction rollback."""
    temporary = _temporary_sibling(path)
    try:
        with temporary.open("xb") as file:
            file.write(payload)
            file.flush()
            fsync_func(file.fileno())
        return temporary
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _restore_path_bytes(
    path,
    existed,
    previous_bytes,
    *,
    replace_func,
    fsync_func,
):
    """Restore one official artifact to its exact pre-transaction state."""
    path = Path(path)
    if not existed:
        path.unlink(missing_ok=True)
        return

    temporary = _write_exact_temporary(path, previous_bytes, fsync_func)
    try:
        replace_func(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _artifact_changed(path, existed, previous_bytes):
    """Detect a replacement that raised after mutating its destination."""
    path = Path(path)
    current_exists = path.exists()
    if current_exists != existed:
        return True
    if not current_exists:
        return False
    try:
        return path.read_bytes() != previous_bytes
    except OSError:
        return True


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
    backup_path = state_backup_path(path)
    candidate_json = _serialize_validated(payload, validator)
    path.parent.mkdir(parents=True, exist_ok=True)
    replace_func = replace_func or Path.replace
    created_temporaries = []

    authoritative_before_exists = path.exists()
    authoritative_before_bytes = path.read_bytes() if authoritative_before_exists else None
    backup_before_exists = backup_path.exists()
    backup_before_bytes = backup_path.read_bytes() if backup_before_exists else None

    try:
        current_state = _load_validated_json(path, validator)
    except FileNotFoundError:
        current_state = None
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        if not allow_invalid_authoritative:
            raise StateLoadError(
                inspect_state_files(path, validator=validator),
                "Routine save refused to replace invalid authoritative state",
            ) from error
        current_state = None

    backup_replaced = False
    authoritative_replaced = False
    backup_rollback_replace = replace_func
    authoritative_rollback_replace = replace_func
    try:
        candidate = _write_validated_temporary(
            path,
            candidate_json,
            validator,
            fsync_func,
        )
        created_temporaries.append(candidate)

        if current_state is not None:
            backup_json = _serialize_validated(current_state, validator)
            backup_candidate = _write_validated_temporary(
                backup_path,
                backup_json,
                validator,
                fsync_func,
            )
            created_temporaries.append(backup_candidate)

        if current_state is not None:
            try:
                replace_func(backup_candidate, backup_path)
            except BaseException:
                backup_replaced = _artifact_changed(
                    backup_path,
                    backup_before_exists,
                    backup_before_bytes,
                )
                if backup_replaced:
                    backup_rollback_replace = Path.replace
                raise
            else:
                backup_replaced = True
        try:
            replace_func(candidate, path)
        except BaseException:
            authoritative_replaced = _artifact_changed(
                path,
                authoritative_before_exists,
                authoritative_before_bytes,
            )
            if authoritative_replaced:
                authoritative_rollback_replace = Path.replace
            raise
        else:
            authoritative_replaced = True
        authoritative_state = _load_validated_json(path, validator)
        return authoritative_state
    except BaseException:
        if authoritative_replaced:
            try:
                _restore_path_bytes(
                    path,
                    authoritative_before_exists,
                    authoritative_before_bytes,
                    replace_func=authoritative_rollback_replace,
                    fsync_func=fsync_func,
                )
            except Exception:
                pass
        if backup_replaced:
            try:
                _restore_path_bytes(
                    backup_path,
                    backup_before_exists,
                    backup_before_bytes,
                    replace_func=backup_rollback_replace,
                    fsync_func=fsync_func,
                )
            except Exception:
                pass
        raise
    finally:
        for temporary in created_temporaries:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def save_validated_state(state, path, *, validator=validate_war_room_state):
    """Persist one schema-2 War Room state through the atomic writer."""
    return atomic_write_json(path, state, validator)


def _inspect_one(path, validator):
    try:
        return _load_validated_json(path, validator), None
    except Exception as error:
        return None, error


def inspect_state_files(path, *, validator=validate_war_room_state):
    """Validate state artifacts without modifying or silently recovering them."""
    authoritative_path = Path(path)
    backup_path = state_backup_path(authoritative_path)
    authoritative_state, authoritative_error = _inspect_one(
        authoritative_path,
        validator,
    )
    backup_state, backup_error = _inspect_one(backup_path, validator)

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


def _default_recovery_metadata_path(path):
    path = Path(path)
    if path.suffix:
        return path.with_name(f"{path.stem}.recovery{path.suffix}")
    return path.with_name(f"{path.name}.recovery")


def _write_recovery_metadata(path, metadata):
    """Atomically publish recovery facts after restoration has committed."""
    serialized = (json.dumps(metadata, indent=2, ensure_ascii=False) + "\n").encode(
        "utf-8"
    )
    temporary = _write_exact_temporary(path, serialized, os.fsync)
    try:
        os.replace(temporary, Path(path))
    finally:
        temporary.unlink(missing_ok=True)


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
    validator=validate_war_room_state,
    recovery_metadata_path=None,
    recovery_metadata_writer=None,
):
    """Explicitly archive bad evidence and restore a validated backup."""
    inspection = inspect_state_files(path, validator=validator)
    if inspection.source != "backup":
        raise StateLoadError(
            inspection,
            "Recovery requires an invalid or missing authoritative state and a valid backup",
        )

    archive_path = None
    if inspection.authoritative_path.exists():
        archive_path = _archive_corrupt_authoritative(
            inspection.authoritative_path,
            archive_root,
            inspection.state["draft_id"],
            archive_write_func,
        )

    restored = atomic_write_json(
        inspection.authoritative_path,
        inspection.state,
        validator,
        replace_func=replace_func,
        fsync_func=fsync_func,
        allow_invalid_authoritative=True,
    )

    metadata_path = recovery_metadata_path
    if metadata_path is None and recovery_metadata_writer is not None:
        metadata_path = _default_recovery_metadata_path(inspection.authoritative_path)
    if metadata_path is not None:
        metadata = {
            "schema": "edgeiq-state-recovery/v1",
            "source": "backup",
            "recovered_at": datetime.now(timezone.utc).isoformat(),
            "authoritative_path": str(inspection.authoritative_path.resolve()),
            "backup_path": str(inspection.backup_path.resolve()),
            "archive_path": (
                str(archive_path.resolve()) if archive_path is not None else None
            ),
            "authoritative_sha256": sha256(
                inspection.authoritative_path.read_bytes()
            ).hexdigest(),
            "backup_sha256": sha256(inspection.backup_path.read_bytes()).hexdigest(),
        }
        writer = recovery_metadata_writer or _write_recovery_metadata
        try:
            writer(Path(metadata_path), metadata)
        except Exception:
            # The state restoration is already committed; metadata is diagnostic.
            pass

    return restored
