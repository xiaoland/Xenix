from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable


_REPOSITORY_PATTERN = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")


def _gh_json(root: Path, endpoint: str) -> Any:
    result = subprocess.run(
        ["gh", "api", endpoint],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or f"exit code {result.returncode}"
        raise RuntimeError(f"GitHub API request failed for {endpoint}: {detail}")
    return json.loads(result.stdout)


def _ruleset_applies(
    ruleset: dict[str, Any],
    *,
    target: str,
    ref: str,
) -> bool:
    conditions = ruleset.get("conditions")
    ref_name = conditions.get("ref_name") if isinstance(conditions, dict) else None
    includes = ref_name.get("include") if isinstance(ref_name, dict) else None
    return (
        ruleset.get("enforcement") == "active"
        and ruleset.get("target") == target
        and isinstance(includes, list)
        and ref in includes
    )


def _applicable_rules(
    details: list[dict[str, Any]],
    *,
    target: str,
    ref: str,
) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    for ruleset in details:
        if _ruleset_applies(ruleset, target=target, ref=ref) and isinstance(
            ruleset.get("rules"),
            list,
        ):
            rules.extend(
                rule for rule in ruleset["rules"] if isinstance(rule, dict)
            )
    return rules


def validate_controls(
    *,
    rulesets: list[dict[str, Any]],
    environment: dict[str, Any],
    deployment_policies: dict[str, Any],
    repository_environments: dict[str, Any],
) -> list[str]:
    failures: list[str] = []
    main_rules = _applicable_rules(
        rulesets,
        target="branch",
        ref="refs/heads/main",
    )
    main_types = {rule.get("type") for rule in main_rules}
    if any(
        ruleset.get("bypass_actors")
        for ruleset in rulesets
        if _ruleset_applies(
            ruleset,
            target="branch",
            ref="refs/heads/main",
        )
    ):
        failures.append("main protection has bypass actors")
    for required in {
        "deletion",
        "non_fast_forward",
        "pull_request",
        "required_status_checks",
    }:
        if required not in main_types:
            failures.append(f"main is missing active {required!r} protection")
    status_contexts = {
        check.get("context")
        for rule in main_rules
        if rule.get("type") == "required_status_checks"
        for check in (
            rule.get("parameters", {}).get("required_status_checks", [])
            if isinstance(rule.get("parameters"), dict)
            else []
        )
        if isinstance(check, dict)
    }
    if "Native CI Gate" not in status_contexts:
        failures.append("main does not require the stable 'Native CI Gate' check")

    tag_rules = _applicable_rules(
        rulesets,
        target="tag",
        ref="refs/tags/v*",
    )
    tag_types = {rule.get("type") for rule in tag_rules}
    if any(
        ruleset.get("bypass_actors")
        for ruleset in rulesets
        if _ruleset_applies(
            ruleset,
            target="tag",
            ref="refs/tags/v*",
        )
    ):
        failures.append("release tag protection has bypass actors")
    for required in {"deletion", "non_fast_forward"}:
        if required not in tag_types:
            failures.append(f"release tags are missing active {required!r} protection")

    branch_policy = environment.get("deployment_branch_policy")
    protection_rules = environment.get("protection_rules")
    if (
        environment.get("name") != "native-release"
        or not isinstance(branch_policy, dict)
        or branch_policy.get("protected_branches") is not False
        or branch_policy.get("custom_branch_policies") is not True
        or not isinstance(protection_rules, list)
        or any(
            not isinstance(rule, dict) or rule.get("type") != "branch_policy"
            for rule in protection_rules
        )
    ):
        failures.append(
            "native-release environment does not enforce only custom ref policy "
            "without a second approval gate"
        )
    policies = deployment_policies.get("branch_policies")
    if (
        not isinstance(policies, list)
        or len(policies) != 1
        or not isinstance(policies[0], dict)
        or policies[0].get("name") != "v*"
        or policies[0].get("type") != "tag"
    ):
        failures.append("native-release environment does not admit only v* tags")
    environments = repository_environments.get("environments")
    deprecated = {"native-candidate", "native-publish"}
    existing_deprecated = []
    if isinstance(environments, list):
        existing_deprecated = sorted(
            item.get("name")
            for item in environments
            if isinstance(item, dict) and item.get("name") in deprecated
        )
    if existing_deprecated:
        failures.append(
            f"superseded release environments still exist: {existing_deprecated!r}"
        )
    return failures


def audit_repository(
    root: Path,
    *,
    repository: str,
    fetch: Callable[[Path, str], Any] = _gh_json,
) -> None:
    summaries = fetch(root, f"repos/{repository}/rulesets")
    if not isinstance(summaries, list):
        raise RuntimeError("GitHub ruleset response is invalid.")
    rulesets = [
        fetch(root, f"repos/{repository}/rulesets/{summary['id']}")
        for summary in summaries
        if isinstance(summary, dict) and type(summary.get("id")) is int
    ]
    try:
        environment = fetch(root, f"repos/{repository}/environments/native-release")
    except RuntimeError:
        environment = {}
    try:
        policies = fetch(
            root,
            f"repos/{repository}/environments/native-release/deployment-branch-policies",
        )
    except RuntimeError:
        policies = {}
    repository_environments = fetch(root, f"repos/{repository}/environments")
    failures = validate_controls(
        rulesets=[item for item in rulesets if isinstance(item, dict)],
        environment=environment if isinstance(environment, dict) else {},
        deployment_policies=policies if isinstance(policies, dict) else {},
        repository_environments=(
            repository_environments
            if isinstance(repository_environments, dict)
            else {}
        ),
    )
    if failures:
        raise RuntimeError(
            "GitHub release controls are not ready:\n- " + "\n- ".join(failures)
        )

    workflows = root / ".github" / "workflows"
    if not (workflows / "native-release.yml").is_file():
        raise RuntimeError("Native Release workflow is missing.")
    forbidden = [
        path.name
        for path in (
            workflows / "native-candidate.yml",
            workflows / "native-publish.yml",
        )
        if path.exists()
    ]
    if forbidden:
        raise RuntimeError(f"Superseded release workflows still exist: {forbidden!r}")
    print("release_controls=ready")
    print("required_check=Native CI Gate")
    print("release_environment=native-release")
    print("release_ref_policy=v* tags only")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True)
    args = parser.parse_args()
    if not _REPOSITORY_PATTERN.fullmatch(args.repository):
        raise RuntimeError(f"Invalid GitHub repository identity: {args.repository!r}")
    try:
        audit_repository(
            Path(__file__).resolve().parents[1],
            repository=args.repository,
        )
    except RuntimeError as exc:
        print("release_controls=not_ready", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
