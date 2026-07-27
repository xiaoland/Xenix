from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from xenix.config import AppPaths
from xenix.trial_lock import (
    PackagedTrialLockConfig,
    TrialLockReason,
    check_trial_lock,
    trial_purchase_url,
    trial_lock_state_path,
)


def _paths(root: Path) -> AppPaths:
    return AppPaths(
        home=root,
        config=root / "config",
        logs=root / "logs",
        cache=root / "cache",
        state=root / "state",
        temp=root / "temp",
        artifacts=root / "artifacts",
        resources=root / "resources",
    )


def _enabled_config() -> PackagedTrialLockConfig:
    return PackagedTrialLockConfig(
        days=7,
        state_secret="test-secret",
        build_id="test-build",
    )


def test_source_trial_purchase_url_reads_build_environment(monkeypatch) -> None:
    monkeypatch.setenv("XENIX_TRIAL_PURCHASE_URL", " https://example.test/buy ")

    assert trial_purchase_url() == "https://example.test/buy"


def test_trial_lock_disabled_does_not_create_state(tmp_path: Path) -> None:
    paths = _paths(tmp_path)

    check = check_trial_lock(paths, config=PackagedTrialLockConfig())

    assert check.enabled is False
    assert check.locked is False
    assert check.reason is TrialLockReason.DISABLED
    assert not trial_lock_state_path(paths).exists()


def test_trial_lock_first_run_creates_signed_state(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    now = datetime(2026, 6, 11, 12, 0, 0, tzinfo=UTC)

    check = check_trial_lock(paths, now=now, config=_enabled_config())

    assert check.enabled is True
    assert check.locked is False
    assert check.reason is TrialLockReason.FIRST_RUN
    assert check.first_seen_utc == now
    assert check.expires_at_utc == now + timedelta(days=7)

    state_payload = json.loads(trial_lock_state_path(paths).read_text(encoding="utf-8"))
    assert state_payload["first_seen_utc"] == "2026-06-11T12:00:00Z"
    assert state_payload["last_seen_utc"] == "2026-06-11T12:00:00Z"
    assert state_payload["build_id"] == "test-build"
    assert state_payload["signature"]


def test_trial_lock_active_run_updates_last_seen(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    config = _enabled_config()
    first_seen = datetime(2026, 6, 11, 12, 0, 0, tzinfo=UTC)
    later = first_seen + timedelta(days=2)
    check_trial_lock(paths, now=first_seen, config=config)

    check = check_trial_lock(paths, now=later, config=config)

    assert check.locked is False
    assert check.reason is TrialLockReason.ACTIVE
    assert check.first_seen_utc == first_seen
    assert check.last_seen_utc == later

    state_payload = json.loads(trial_lock_state_path(paths).read_text(encoding="utf-8"))
    assert state_payload["last_seen_utc"] == "2026-06-13T12:00:00Z"


def test_trial_lock_expires_after_configured_elapsed_days(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    config = _enabled_config()
    first_seen = datetime(2026, 6, 11, 12, 0, 0, tzinfo=UTC)
    check_trial_lock(paths, now=first_seen, config=config)

    check = check_trial_lock(paths, now=first_seen + timedelta(days=7), config=config)

    assert check.locked is True
    assert check.reason is TrialLockReason.EXPIRED
    assert check.expires_at_utc == first_seen + timedelta(days=7)


def test_trial_lock_tampered_state_locks_startup(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    config = _enabled_config()
    first_seen = datetime(2026, 6, 11, 12, 0, 0, tzinfo=UTC)
    check_trial_lock(paths, now=first_seen, config=config)

    state_path = trial_lock_state_path(paths)
    state_payload = json.loads(state_path.read_text(encoding="utf-8"))
    state_payload["first_seen_utc"] = "2026-06-12T12:00:00Z"
    state_path.write_text(json.dumps(state_payload), encoding="utf-8")

    check = check_trial_lock(paths, now=first_seen + timedelta(days=1), config=config)

    assert check.locked is True
    assert check.reason is TrialLockReason.TAMPERED


def test_trial_lock_clock_rollback_locks_startup(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    config = _enabled_config()
    first_seen = datetime(2026, 6, 11, 12, 0, 0, tzinfo=UTC)
    check_trial_lock(paths, now=first_seen, config=config)
    check_trial_lock(paths, now=first_seen + timedelta(days=2), config=config)

    check = check_trial_lock(paths, now=first_seen + timedelta(days=1), config=config)

    assert check.locked is True
    assert check.reason is TrialLockReason.CLOCK_ROLLBACK
