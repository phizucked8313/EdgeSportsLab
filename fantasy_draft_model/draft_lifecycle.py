"""Explicit, evidence-preserving lifecycle controls for the live draft."""

import copy
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from shutil import copyfile
from uuid import uuid4

from fantasy_draft_model.keepers import load_keepers
from fantasy_draft_model.live_war_room import (
    build_keeper_reservations,
    initialize_war_room,
    load_war_room_state,
    make_keeper_aware_state_validator,
    resolve_league,
)
from fantasy_draft_model.state_persistence import (
    StateLoadError,
    atomic_write_json,
    inspect_state_files,
    recover_state_from_backup,
    state_backup_path,
)
from fantasy_draft_model.war_room_state import (
    migrate_legacy_state,
    validate_war_room_state,
)


@dataclass(frozen=True)
class LifecycleInspection:
    """Read-only lifecycle facts used by the explicit Start/Resume gate."""

    state: dict | None
    source: str | None
    requires_choice: bool
    can_resume: bool
    can_recover: bool
    is_legacy: bool
    completed_slots: int
    total_slots: int | None
    manual_pick_count: int
    keeper_count: int
    state_age_seconds: float | None
    draft_id: str | None
    league_name: str | None
    status: str | None
    created_at: str | None
    updated_at: str | None
    authoritative_path: Path
    backup_path: Path
    recovery_metadata_path: Path
    authoritative_error: Exception | None
    backup_error: Exception | None
    legacy_error: Exception | None


def state_recovery_metadata_path(path):
    """Return the deterministic recovery-metadata sibling for *path*."""
    path = Path(path)
    if path.suffix:
        return path.with_name(f"{path.stem}.recovery{path.suffix}")
    return path.with_name(f"{path.name}.recovery")


def _utc_now():
    return datetime.now(timezone.utc)


def _as_utc_datetime(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _now_value(now_func):
    return _as_utc_datetime(now_func())


def _safe_component(value):
    component = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value)).strip("-._")
    return component or "archive"


def _canonical_keeper_reservations(state, keeper_loader):
    league = resolve_league(state.get("league_key") or state["league_name"])
    keepers = keeper_loader(league["name"])
    return build_keeper_reservations(league, keepers)


def _validate_with_current_keepers(state, keeper_loader):
    reservations = _canonical_keeper_reservations(state, keeper_loader)
    return validate_war_room_state(state, keeper_reservations=reservations)


def _read_legacy_candidate(path, keeper_loader):
    with Path(path).open("r", encoding="utf-8") as file:
        legacy = json.load(file)
    if not isinstance(legacy, dict) or legacy.get("schema_version") != 1:
        raise ValueError("authoritative state is not a schema-1 candidate")
    migrated = migrate_legacy_state(legacy)
    _validate_with_current_keepers(migrated, keeper_loader)
    return legacy, migrated


def _read_and_validate_candidate(path, validator):
    with Path(path).open("r", encoding="utf-8") as file:
        candidate = json.load(file)
    return validator(candidate)


def _state_age_seconds(state, source_path, now):
    timestamp = state.get("updated_at") if state else None
    if timestamp:
        updated_at = _as_utc_datetime(timestamp)
    else:
        updated_at = datetime.fromtimestamp(
            Path(source_path).stat().st_mtime,
            tz=timezone.utc,
        )
    return max(0.0, (now - updated_at).total_seconds())


def inspect_draft_lifecycle(
    state_path,
    *,
    now_func=_utc_now,
    keeper_loader=load_keepers,
):
    """Inspect lifecycle choices without writing or recovering any artifact."""
    state_path = Path(state_path)
    keeper_aware_validator = make_keeper_aware_state_validator(keeper_loader)
    file_inspection = inspect_state_files(state_path)
    recovery_path = state_recovery_metadata_path(state_path)
    state = None
    source = None
    can_resume = False
    can_recover = False
    is_legacy = False
    legacy_error = None
    authoritative_error = file_inspection.authoritative_error
    backup_error = file_inspection.backup_error

    if file_inspection.source == "authoritative":
        try:
            state = keeper_aware_validator(file_inspection.state)
            source = "authoritative"
            can_resume = True
            if file_inspection.backup_path.exists():
                try:
                    _read_and_validate_candidate(
                        file_inspection.backup_path,
                        keeper_aware_validator,
                    )
                except Exception as error:
                    backup_error = error
        except Exception as error:
            authoritative_error = error
            try:
                state = _read_and_validate_candidate(
                    file_inspection.backup_path,
                    keeper_aware_validator,
                )
                source = "backup"
                can_recover = True
            except Exception as backup_validation_error:
                backup_error = backup_validation_error
    elif state_path.exists():
        try:
            _legacy, state = _read_legacy_candidate(state_path, keeper_loader)
            source = "authoritative_legacy"
            can_resume = True
            is_legacy = True
        except Exception as error:
            legacy_error = error

    if not can_resume and file_inspection.source == "backup":
        try:
            state = keeper_aware_validator(file_inspection.state)
            source = "backup"
            can_recover = True
        except Exception as error:
            backup_error = error

    completed_slots = int(state.get("current_pick", 1)) - 1 if state else 0
    total_slots = int(state["total_picks"]) if state and "total_picks" in state else None
    source_path = (
        file_inspection.backup_path
        if source == "backup"
        else file_inspection.authoritative_path
    )
    state_age = (
        _state_age_seconds(state, source_path, _now_value(now_func))
        if state is not None
        else None
    )
    return LifecycleInspection(
        state=copy.deepcopy(state) if state is not None else None,
        source=source,
        requires_choice=True,
        can_resume=can_resume,
        can_recover=can_recover,
        is_legacy=is_legacy,
        completed_slots=max(0, completed_slots),
        total_slots=total_slots,
        manual_pick_count=len(state.get("manual_picks", [])) if state else 0,
        keeper_count=len(state.get("keeper_reservations", [])) if state else 0,
        state_age_seconds=state_age,
        draft_id=state.get("draft_id") if state else None,
        league_name=state.get("league_name") if state else None,
        status=state.get("status") if state else None,
        created_at=state.get("created_at") if state else None,
        updated_at=state.get("updated_at") if state else None,
        authoritative_path=file_inspection.authoritative_path,
        backup_path=file_inspection.backup_path,
        recovery_metadata_path=recovery_path,
        authoritative_error=authoritative_error,
        backup_error=backup_error,
        legacy_error=legacy_error,
    )


def _unique_archive_directory(archive_root, timestamp, unique_id):
    archive_root = Path(archive_root)
    archive_root.mkdir(parents=True, exist_ok=True)
    stamp = timestamp.strftime("%Y%m%dT%H%M%S%fZ")
    base_name = f"{stamp}-{_safe_component(unique_id)}"
    candidate = archive_root / base_name
    counter = 1
    while True:
        try:
            candidate.mkdir(exist_ok=False)
            return candidate
        except FileExistsError:
            candidate = archive_root / f"{base_name}-{counter}"
            counter += 1


def _verified_manifest(directory, manifest):
    manifest_path = Path(directory) / "manifest.json"
    with manifest_path.open("r", encoding="utf-8") as file:
        reloaded = json.load(file)
    if reloaded != manifest:
        raise OSError(f"archive manifest verification failed for {manifest_path}")
    for entry in reloaded["artifacts"]:
        source = Path(entry["source_path"])
        archived = Path(entry["archive_path"])
        archived_bytes = archived.read_bytes()
        if (
            len(archived_bytes) != entry["byte_length"]
            or sha256(archived_bytes).hexdigest() != entry["sha256"]
            or archived_bytes != source.read_bytes()
        ):
            raise OSError(f"archive verification failed for {archived}")
    return manifest_path


def _write_manifest_atomically(directory, manifest, unique_id, fsync_func):
    manifest_path = Path(directory) / "manifest.json"
    temporary = Path(directory) / f"manifest.json.tmp-{_safe_component(unique_id)}"
    serialized = (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    try:
        with temporary.open("xb") as file:
            file.write(serialized)
            file.flush()
            fsync_func(file.fileno())
        temporary.replace(manifest_path)
    finally:
        temporary.unlink(missing_ok=True)
    return _verified_manifest(directory, manifest)


def archive_state_artifacts(
    state_path,
    archive_root,
    *,
    now_func=_utc_now,
    id_func=lambda: uuid4().hex,
    copy_func=copyfile,
    fsync_func=os.fsync,
):
    """Copy and checksum every current state artifact into one unique archive."""
    state_path = Path(state_path)
    timestamp = _now_value(now_func)
    archive_id = id_func()
    directory = _unique_archive_directory(archive_root, timestamp, archive_id)
    sources = (
        ("authoritative", state_path),
        ("backup", state_backup_path(state_path)),
        ("recovery_metadata", state_recovery_metadata_path(state_path)),
    )
    entries = []

    for role, source in sources:
        if not source.exists():
            continue
        destination = directory / f"{role}-{source.name}"
        source_bytes = source.read_bytes()
        copy_func(source, destination)
        archived_bytes = destination.read_bytes()
        if (
            len(archived_bytes) != len(source_bytes)
            or sha256(archived_bytes).digest() != sha256(source_bytes).digest()
        ):
            raise OSError(f"archive verification failed for {destination}")
        entries.append(
            {
                "role": role,
                "source_path": str(source.resolve()),
                "archive_path": str(destination.resolve()),
                "sha256": sha256(source_bytes).hexdigest(),
                "byte_length": len(source_bytes),
                "timestamp": timestamp.isoformat(),
            }
        )

    manifest = {
        "timestamp": timestamp.isoformat(),
        "artifacts": entries,
    }
    _write_manifest_atomically(directory, manifest, id_func(), fsync_func)
    return directory


def _save_after_verified_archive(
    state,
    state_path,
    *,
    validator=validate_war_room_state,
):
    return atomic_write_json(
        state_path,
        state,
        validator,
        allow_invalid_authoritative=True,
    )


def start_new_draft(
    league_key,
    state_path,
    archive_root,
    *,
    now_func=_utc_now,
    id_func=lambda: str(uuid4()),
    keeper_loader=load_keepers,
):
    """Archive every existing artifact, then initialize and reload fresh state."""
    archive_directory = archive_state_artifacts(
        state_path,
        archive_root,
        now_func=now_func,
        id_func=id_func,
    )
    timestamp = _now_value(now_func).isoformat()
    candidate = initialize_war_room(
        league_key,
        state_path=archive_directory / "fresh-state.candidate.json",
        clock_func=lambda: timestamp,
        id_func=id_func,
        keeper_loader=keeper_loader,
        state_saver=lambda state, _path: copy.deepcopy(state),
    )
    keeper_aware_validator = make_keeper_aware_state_validator(keeper_loader)
    keeper_aware_validator(candidate)
    return _save_after_verified_archive(
        candidate,
        state_path,
        validator=keeper_aware_validator,
    )


def _default_archive_root(state_path):
    return Path(state_path).parent / "archives"


def resume_existing_draft(
    state_path,
    *,
    archive_root=None,
    now_func=_utc_now,
    id_func=lambda: str(uuid4()),
    keeper_loader=load_keepers,
):
    """Resume valid schema-2 state or explicitly archive and migrate schema 1."""
    state_path = Path(state_path)
    inspection = inspect_draft_lifecycle(
        state_path,
        now_func=now_func,
        keeper_loader=keeper_loader,
    )
    if not inspection.can_resume:
        raise StateLoadError(
            inspect_state_files(
                state_path,
                validator=make_keeper_aware_state_validator(keeper_loader),
            ),
            "No authoritative War Room state is eligible to resume",
        )
    if not inspection.is_legacy:
        return _validate_with_current_keepers(
            load_war_room_state(
                state_path,
                keeper_loader=keeper_loader,
            ),
            keeper_loader,
        )

    archive_state_artifacts(
        state_path,
        archive_root or _default_archive_root(state_path),
        now_func=now_func,
        id_func=id_func,
    )
    legacy, migrated = _read_legacy_candidate(state_path, keeper_loader)
    del legacy
    timestamp = _now_value(now_func).isoformat()
    migrated.update(
        {
            "draft_id": id_func(),
            "created_at": timestamp,
            "updated_at": timestamp,
        }
    )
    keeper_aware_validator = make_keeper_aware_state_validator(keeper_loader)
    keeper_aware_validator(migrated)
    return atomic_write_json(
        state_path,
        migrated,
        keeper_aware_validator,
        allow_invalid_authoritative=True,
    )


def recover_existing_draft(
    state_path,
    archive_root,
    *,
    keeper_loader=load_keepers,
    recovery_metadata_writer=None,
):
    """Explicitly recover the validated backup selected by lifecycle inspection."""
    inspection = inspect_draft_lifecycle(
        state_path,
        keeper_loader=keeper_loader,
    )
    if not inspection.can_recover:
        raise StateLoadError(
            inspect_state_files(
                state_path,
                validator=make_keeper_aware_state_validator(keeper_loader),
            ),
            "No validated backup is eligible for recovery",
        )
    keeper_aware_validator = make_keeper_aware_state_validator(keeper_loader)
    recovered = recover_state_from_backup(
        state_path,
        archive_root,
        validator=keeper_aware_validator,
        recovery_metadata_path=state_recovery_metadata_path(state_path),
        recovery_metadata_writer=recovery_metadata_writer,
    )
    return recovered
