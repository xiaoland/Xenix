from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_script(name: str):
    path = Path(__file__).resolve().parents[1] / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"xenix_{name}_for_test", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


audit = _load_script("audit_release_controls")


def _ready_rulesets():
    return [
        {
            "target": "branch",
            "enforcement": "active",
            "conditions": {"ref_name": {"include": ["refs/heads/main"]}},
            "rules": [
                {"type": "deletion"},
                {"type": "non_fast_forward"},
                {"type": "pull_request"},
                {
                    "type": "required_status_checks",
                    "parameters": {
                        "required_status_checks": [
                            {"context": "Native CI Gate"}
                        ]
                    },
                },
            ],
        },
        {
            "target": "tag",
            "enforcement": "active",
            "conditions": {"ref_name": {"include": ["refs/tags/v*"]}},
            "rules": [
                {"type": "deletion"},
                {"type": "non_fast_forward"},
            ],
        },
    ]


def test_release_controls_accept_complete_contract() -> None:
    failures = audit.validate_controls(
        rulesets=_ready_rulesets(),
        environment={
            "name": "native-release",
            "can_admins_bypass": False,
            "protection_rules": [{"type": "branch_policy"}],
            "deployment_branch_policy": {
                "protected_branches": False,
                "custom_branch_policies": True,
            },
        },
        deployment_policies={
            "branch_policies": [{"name": "v*", "type": "tag"}]
        },
        repository_environments={
            "environments": [{"name": "native-release"}]
        },
    )

    assert failures == []


def test_release_controls_report_missing_gate_and_tag_immutability() -> None:
    rulesets = _ready_rulesets()
    rulesets[0]["rules"] = [
        rule
        for rule in rulesets[0]["rules"]
        if rule["type"] != "required_status_checks"
    ]
    rulesets[1]["rules"] = [{"type": "deletion"}]

    failures = audit.validate_controls(
        rulesets=rulesets,
        environment={"name": "native-release"},
        deployment_policies={"branch_policies": []},
        repository_environments={
            "environments": [
                {"name": "native-candidate"},
                {"name": "native-publish"},
            ]
        },
    )

    assert any("Native CI Gate" in failure for failure in failures)
    assert any("non_fast_forward" in failure for failure in failures)
    assert any("v* tags" in failure for failure in failures)
    assert any("superseded release environments" in failure for failure in failures)
