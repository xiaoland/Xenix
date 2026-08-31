from __future__ import annotations

from pathlib import Path

from xenix.runtime_profile import (
    Capabilities,
    RuntimeProfile,
    RuntimeProfileContext,
    is_isolated_home_path,
    resolve_runtime_profile,
)


def _context(home: Path, *, run_id: str = "run") -> RuntimeProfileContext:
    return RuntimeProfileContext(RuntimeProfile.PRODUCTION, home, Capabilities(), run_id, False)


def test_mutex_is_scoped_to_normalized_home(tmp_path) -> None:
    home = tmp_path / "home"
    same_home_a = _context(home).mutex_name()
    same_home_b = _context(home, run_id="other-run").mutex_name()
    other_home = _context(tmp_path / "other").mutex_name()

    assert same_home_a == same_home_b
    assert same_home_a != other_home


def test_production_profile_uses_resolved_home_with_all_capabilities(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "prod-home"))
    profile = resolve_runtime_profile()

    assert profile.profile is RuntimeProfile.PRODUCTION
    assert profile.isolated_home is False
    assert profile.home == (tmp_path / "prod-home").resolve()
    assert profile.capabilities == Capabilities()


def test_agent_dev_isolates_home_and_denies_remote(tmp_path) -> None:
    profile = resolve_runtime_profile(agent_dev=True, temp_root=tmp_path)

    assert profile.profile is RuntimeProfile.AGENT_DEV
    assert profile.isolated_home is True
    assert profile.home.parent == tmp_path.resolve()
    assert profile.home.name.startswith("xenix-agent-dev-")
    assert profile.capabilities == Capabilities.agent_safe()


def test_agent_dev_and_ephemeral_compose_to_isolated_denied_run(tmp_path) -> None:
    profile = resolve_runtime_profile(agent_dev=True, ephemeral=True, temp_root=tmp_path)

    assert profile.profile is RuntimeProfile.EPHEMERAL
    assert profile.isolated_home is True
    assert profile.capabilities.update is False
    assert profile.capabilities.remote_otlp is False
    assert profile.capabilities.remote_ml_workers is False


def test_run_manifest_exposes_home_and_capabilities(tmp_path) -> None:
    profile = resolve_runtime_profile(agent_dev=True, temp_root=tmp_path)
    manifest = profile.run_manifest()

    assert manifest["profile"] == "agent-dev"
    assert manifest["home"] == str(profile.home)
    assert manifest["isolated_home"] is True
    assert manifest["capabilities"]["update"] is False
    assert manifest["capabilities"]["ssh_worker_setup"] is False


def test_is_isolated_home_path_accepts_only_xenix_minted_names(tmp_path) -> None:
    assert is_isolated_home_path(tmp_path / "xenix-agent-dev-0123456789ab")
    assert is_isolated_home_path(tmp_path / "xenix-ephemeral-ffffffffffff")
    assert not is_isolated_home_path(tmp_path / "home")
    assert not is_isolated_home_path(Path.home())
    assert not is_isolated_home_path(tmp_path)
    assert not is_isolated_home_path(tmp_path / "xenix-agent-dev-TOO-LONG-NAME")
    assert not is_isolated_home_path(tmp_path / "xenix-production-0123456789ab")
