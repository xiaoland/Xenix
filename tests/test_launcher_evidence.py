from __future__ import annotations

import json
from pathlib import Path

from xenix.main import _preserve_failure_evidence, _redact_error, _remove_isolated_home
from xenix.runtime_profile import Capabilities, RuntimeProfile, RuntimeProfileContext


def test_redact_error_replaces_paths_and_bounds_length() -> None:
    assert "<home>" in _redact_error(f"failed at {Path.home()}")
    assert "<path>" in _redact_error("failed at D:\\data\\secret.txt")
    assert len(_redact_error("x" * 10_000)) <= 4_000


def test_remove_isolated_home_deletes_directory(tmp_path: Path) -> None:
    home = tmp_path / "home"
    (home / "state").mkdir(parents=True)

    _remove_isolated_home(home)

    assert not home.exists()


def test_preserve_failure_evidence_writes_bounded_redacted_json(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("XENIX_EVIDENCE_DIR", str(tmp_path / "evidence"))
    profile = RuntimeProfileContext(
        RuntimeProfile.AGENT_DEV,
        tmp_path / "home",
        Capabilities.agent_safe(),
        "run-123",
        True,
    )

    _preserve_failure_evidence(profile, RuntimeError, RuntimeError("boom"))

    output = tmp_path / "evidence" / "run-123" / "failure.json"
    assert output.exists()
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["profile"] == "agent-dev"
    assert payload["run_id"] == "run-123"
    assert "boom" in payload["error"]
