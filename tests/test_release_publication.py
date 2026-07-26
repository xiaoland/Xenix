from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


def _load_script(name: str):
    path = Path(__file__).resolve().parents[1] / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"xenix_{name}_for_test", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


package_velopack = _load_script("package_velopack")
publish_release = _load_script("publish_oss_release")


def test_package_assets_drop_deleted_portable(tmp_path: Path) -> None:
    setup_name = "xenix-Setup.exe"
    full_name = "xenix-full.nupkg"
    (tmp_path / setup_name).write_bytes(b"setup")
    (tmp_path / full_name).write_bytes(b"full")
    assets_path = tmp_path / "assets.win-x64-stable.json"
    assets_path.write_text(
        json.dumps(
            [
                {"RelativeFileName": setup_name, "Type": "Installer"},
                {"RelativeFileName": full_name, "Type": "Full"},
                {"RelativeFileName": "xenix-Portable.zip", "Type": "Portable"},
            ]
        ),
        encoding="utf-8",
    )

    package_velopack.prune_missing_assets(tmp_path)

    assert json.loads(assets_path.read_text(encoding="utf-8")) == [
        {"RelativeFileName": setup_name, "Type": "Installer"},
        {"RelativeFileName": full_name, "Type": "Full"},
    ]


def test_public_assets_project_from_manifest_artifacts() -> None:
    release_data = json.dumps(
        [
            {"RelativeFileName": "xenix-Setup.exe", "Type": "Installer"},
            {"RelativeFileName": "xenix-full.nupkg", "Type": "Full"},
            {"RelativeFileName": "xenix-Portable.zip", "Type": "Portable"},
        ],
        separators=(",", ":"),
    ).encode("utf-8")

    projected = publish_release.public_feed_data(
        "assets.win-x64-stable.json",
        release_data,
        {"assets.win-x64-stable.json", "xenix-Setup.exe", "xenix-full.nupkg"},
    )

    assert json.loads(projected) == [
        {"RelativeFileName": "xenix-Setup.exe", "Type": "Installer"},
        {"RelativeFileName": "xenix-full.nupkg", "Type": "Full"},
    ]


def _release_fixture(tmp_path: Path, *, version: str = "1.2.0"):
    commit = "a" * 40
    tag = f"v{version}"
    setup_name = "dev.lanzhijiang.xenix-win-x64-stable-Setup.exe"
    full_name = f"dev.lanzhijiang.xenix-{version}-win-x64-stable-full.nupkg"
    ocr_name = "xenix-knowledge-ocr-win-x64.zip"
    payloads = {
        setup_name: b"new setup",
        full_name: b"new full package",
        ocr_name: b"native ocr",
        "assets.win-x64-stable.json": json.dumps(
            [
                {"RelativeFileName": setup_name, "Type": "Installer"},
                {"RelativeFileName": full_name, "Type": "Full"},
                {"RelativeFileName": "deleted-Portable.zip", "Type": "Portable"},
            ],
            separators=(",", ":"),
        ).encode(),
        "releases.win-x64-stable.json": json.dumps(
            {
                "Assets": [
                    {
                        "Version": version,
                        "FileName": full_name,
                    }
                ]
            },
            separators=(",", ":"),
        ).encode(),
        "RELEASES-win-x64-stable": b"release-index",
    }
    artifacts = []
    for name, data in payloads.items():
        if name == ocr_name:
            artifact_type = "knowledge_ocr_runtime"
            relative = f"knowledge-ocr/{name}"
        elif name in publish_release.FEED_NAMES:
            artifact_type = "update_feed"
            relative = f"velopack/{name}"
        else:
            artifact_type = "desktop_release"
            relative = f"velopack/{name}"
        path = tmp_path / "dist" / Path(*relative.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        artifacts.append(
            {
                "type": artifact_type,
                "path": relative,
                "name": name,
                "bytes": len(data),
                "sha256": publish_release.digest(data),
            }
        )
    manifest = {
        "schema_version": 3,
        "version": version,
        "commit": commit,
        "release": {
            "protocol_version": 1,
            "tag": tag,
            "promotion_pr": 42,
        },
        "workflow": {
            "repository": "xiaoland/Xenix",
            "run_id": 100,
            "run_attempt": 2,
        },
        "unsigned": True,
        "packaged_smoke": "passed",
        "toolchain": {"python": "3.14.6"},
        "release_toml_sha256": "b" * 64,
        "lock_sha256": "c" * 64,
        "artifacts": artifacts,
    }
    manifest_path = tmp_path / "dist" / "release-manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    plan = publish_release.build_plan(
        tmp_path,
        manifest_path=manifest_path,
        expected_tag=tag,
        expected_commit=commit,
        expected_promotion_pr=42,
        expected_repository="xiaoland/Xenix",
    )
    return plan, payloads


class FakeReleaseStore:
    def __init__(self, objects: dict[str, bytes] | None = None) -> None:
        self.objects = dict(objects or {})
        self.mutations: list[tuple[str, str]] = []

    def exists(self, key: str) -> bool:
        return key in self.objects

    def read(self, key: str) -> bytes:
        return self.objects[key]

    def put_bytes_immutable(self, key: str, data: bytes) -> None:
        if key in self.objects and self.objects[key] != data:
            raise RuntimeError(f"Conflicting immutable release object: {key}")
        self.objects[key] = data
        self.mutations.append(("immutable-bytes", key))

    def upload_file(
        self,
        key: str,
        path: Path,
        *,
        immutable: bool,
        cache_control: str | None = None,
    ) -> None:
        data = path.read_bytes()
        if immutable and key in self.objects and self.objects[key] != data:
            raise RuntimeError(f"Conflicting immutable release object: {key}")
        self.objects[key] = data
        self.mutations.append(("immutable-file" if immutable else "mutable-file", key))

    def copy(
        self,
        source: str,
        destination: str,
        *,
        immutable: bool,
        cache_control: str | None = None,
    ) -> None:
        if (
            immutable
            and destination in self.objects
            and self.objects[destination] != self.objects[source]
        ):
            raise RuntimeError(f"Conflicting immutable release object: {destination}")
        self.objects[destination] = self.objects[source]
        self.mutations.append(("snapshot" if immutable else "mutable-copy", destination))

    def put_bytes_mutable(self, key: str, data: bytes) -> None:
        self.objects[key] = data
        self.mutations.append(("mutable-bytes", key))

    def verify_public(self, key: str, expected_sha256: str) -> None:
        assert publish_release.digest(self.objects[key]) == expected_sha256

    def require_no_cache(self, key: str) -> None:
        assert key in self.objects


def test_manifest_contract_binds_tag_commit_promotion_and_ocr(tmp_path: Path) -> None:
    plan, _ = _release_fixture(tmp_path)

    assert plan.tag == "v1.2.0"
    assert plan.manifest["commit"] == "a" * 40
    assert [item["type"] for item in plan.artifacts].count(
        "knowledge_ocr_runtime"
    ) == 1


def test_manifest_contract_rejects_unsafe_artifact_path(tmp_path: Path) -> None:
    plan, _ = _release_fixture(tmp_path)
    manifest = dict(plan.manifest)
    manifest["artifacts"] = [dict(item) for item in plan.artifacts]
    manifest["artifacts"][0]["path"] = "../unsafe.exe"

    with pytest.raises(RuntimeError, match="artifact identity"):
        publish_release.validated_artifacts(
            manifest,
            expected_tag=plan.tag,
            expected_commit=plan.manifest["commit"],
            expected_promotion_pr=42,
            expected_repository="xiaoland/Xenix",
        )


def test_direct_release_updates_setup_and_publishes_canonical_feed_last(
    tmp_path: Path,
) -> None:
    plan, payloads = _release_fixture(tmp_path)
    old_canonical = json.dumps(
        {"Assets": [{"Version": "1.1.0", "FileName": "old.nupkg"}]}
    ).encode()
    store = FakeReleaseStore(
        {
            "published/re417": b"unrelated",
            f"published/{plan.setup['name']}": b"old generated setup",
            "published/Xenix-Setup.exe": b"old alias",
            "published/releases.win-x64-stable.json": old_canonical,
            "published/assets.win-x64-stable.json": b"old assets",
            "published/RELEASES-win-x64-stable": b"old index",
        }
    )

    result = publish_release.publish_release(plan, store)

    assert store.objects[f"published/{plan.setup['name']}"] == payloads[plan.setup["name"]]
    assert store.objects["published/Xenix-Setup.exe"] == payloads[plan.setup["name"]]
    for item in plan.immutable:
        assert store.objects[f"published/{item['name']}"] == payloads[item["name"]]
    feed_writes = [
        key
        for operation, key in store.mutations
        if operation == "mutable-bytes"
    ]
    assert feed_writes[-1] == "published/releases.win-x64-stable.json"
    assert any(
        key.startswith(result.history_prefix)
        for _, key in store.mutations
    )


def test_interrupted_same_tag_release_converges(tmp_path: Path) -> None:
    plan, payloads = _release_fixture(tmp_path)
    full = next(item for item in plan.immutable if item["name"].endswith(".nupkg"))
    store = FakeReleaseStore(
        {
            f"published/{full['name']}": payloads[full["name"]],
            f"published/{plan.setup['name']}": payloads[plan.setup["name"]],
            "published/releases.win-x64-stable.json": json.dumps(
                {"Assets": [{"Version": "1.1.0"}]}
            ).encode(),
        }
    )

    publish_release.publish_release(plan, store)

    assert publish_release.current_release_version(
        store.objects["published/releases.win-x64-stable.json"]
    ) == "1.2.0"


def test_release_version_regression_is_rejected_before_mutation(tmp_path: Path) -> None:
    plan, _ = _release_fixture(tmp_path, version="1.2.0")
    store = FakeReleaseStore(
        {
            "published/releases.win-x64-stable.json": json.dumps(
                {"Assets": [{"Version": "1.3.0"}]}
            ).encode()
        }
    )

    with pytest.raises(RuntimeError, match="regression"):
        publish_release.publish_release(plan, store)

    assert store.mutations == []


def test_release_status_outputs_bind_tag_version_and_rollback_history(
    monkeypatch,
    tmp_path: Path,
) -> None:
    plan, _ = _release_fixture(tmp_path)
    output = tmp_path / "github-output.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    result = publish_release.PublicationResult(
        history_prefix="published/publication-history/v1.2.0/run-attempt",
        publication_seconds=42.5,
        visibility_seconds=3.25,
    )

    evidence_path = publish_release._write_publication_evidence(plan, result)
    publish_release._write_github_outputs(plan, result)

    assert output.read_text(encoding="utf-8").splitlines() == [
        "published_version=1.2.0",
        "published_tag=v1.2.0",
        "rollback_history=published/publication-history/v1.2.0/run-attempt/",
        "publication_seconds=42.5",
        "visibility_seconds=3.25",
    ]
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["commit"] == "a" * 40
    assert evidence["publication_seconds"] == 42.5
    assert evidence["visibility_seconds"] == 3.25
