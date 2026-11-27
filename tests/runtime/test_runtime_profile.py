from __future__ import annotations

from pathlib import Path

from xenix.runtime_profile import (
    RuntimeProfile,
    RuntimeProfileContext,
    is_isolated_home_path,
    resolve_runtime_profile,
)


def _context(runtime_home: Path, *, run_id: str = "run") -> RuntimeProfileContext:
    return RuntimeProfileContext(RuntimeProfile.PRODUCTION, runtime_home, run_id, False)


def test_mutex_is_scoped_to_normalized_home(tmp_path) -> None:
    runtime_home = tmp_path / "home"
    same_home_a = _context(runtime_home).mutex_name()
    same_home_b = _context(runtime_home, run_id="other-run").mutex_name()
    other_home = _context(tmp_path / "other").mutex_name()

    assert same_home_a == same_home_b
    assert same_home_a != other_home


def test_production_profile_uses_resolved_home(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "prod-home"))
    profile = resolve_runtime_profile()

    assert profile.profile is RuntimeProfile.PRODUCTION
    assert profile.isolated_home is False
    assert profile.runtime_home == (tmp_path / "prod-home").resolve()


def test_isolated_profile_uses_fresh_temp_home(tmp_path) -> None:
    profile = resolve_runtime_profile(isolated=True, temp_root=tmp_path)

    assert profile.profile is RuntimeProfile.ISOLATED
    assert profile.isolated_home is True
    assert profile.runtime_home.parent == tmp_path.resolve()
    assert profile.runtime_home.name.startswith("xenix-isolated-")


def test_run_manifest_exposes_home(tmp_path) -> None:
    profile = resolve_runtime_profile(isolated=True, temp_root=tmp_path)
    manifest = profile.run_manifest()

    assert manifest["profile"] == "isolated"
    assert manifest["runtime_home"] == str(profile.runtime_home)
    assert manifest["isolated_home"] is True


def test_is_isolated_home_path_accepts_only_xenix_minted_names(tmp_path) -> None:
    assert is_isolated_home_path(tmp_path / "xenix-isolated-0123456789ab")
    assert not is_isolated_home_path(tmp_path / "home")
    assert not is_isolated_home_path(Path.home())
    assert not is_isolated_home_path(tmp_path)
    assert not is_isolated_home_path(tmp_path / "xenix-isolated-TOO-LONG-NAME")
    assert not is_isolated_home_path(tmp_path / "xenix-production-0123456789ab")
