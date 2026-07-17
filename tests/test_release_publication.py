from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path


def _load_script(name: str):
    path = Path(__file__).resolve().parents[1] / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"xenix_{name}_for_test", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


package_velopack = _load_script("package_velopack")
publish_candidate = _load_script("publish_oss_candidate")


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
    candidate = json.dumps(
        [
            {"RelativeFileName": "xenix-Setup.exe", "Type": "Installer"},
            {"RelativeFileName": "xenix-full.nupkg", "Type": "Full"},
            {"RelativeFileName": "xenix-Portable.zip", "Type": "Portable"},
        ],
        separators=(",", ":"),
    ).encode("utf-8")

    projected = publish_candidate.public_feed_data(
        "assets.win-x64-stable.json",
        candidate,
        {"assets.win-x64-stable.json", "xenix-Setup.exe", "xenix-full.nupkg"},
    )

    assert json.loads(projected) == [
        {"RelativeFileName": "xenix-Setup.exe", "Type": "Installer"},
        {"RelativeFileName": "xenix-full.nupkg", "Type": "Full"},
    ]


def test_publish_updates_stable_setup_without_touching_version_invariant_setup(monkeypatch) -> None:
    class FakeBucket:
        bucket_name = "xenix"

        def __init__(self, objects: dict[str, bytes]) -> None:
            self.objects = objects

        def get_object(self, key: str):
            return io.BytesIO(self.objects[key])

        def object_exists(self, key: str) -> bool:
            return key in self.objects

        def copy_object(self, _bucket: str, source: str, destination: str, headers=None) -> None:
            assert destination != f"published/{setup_name}"
            self.objects[destination] = self.objects[source]

        def get_object_meta(self, key: str):
            return type("Meta", (), {"content_length": len(self.objects[key])})()

        def put_object(self, key: str, data: bytes, headers=None) -> None:
            self.objects[key] = data

    class FakeResponse:
        def __init__(self, data: bytes, *, status_code: int = 200, headers: dict[str, str] | None = None) -> None:
            self.data = data
            self.status_code = status_code
            self.headers = headers or {}

        def raise_for_status(self) -> None:
            assert self.status_code < 400

        def iter_content(self, _size: int):
            yield self.data

    setup_name = "dev.lanzhijiang.xenix-win-x64-stable-Setup.exe"
    full_name = "dev.lanzhijiang.xenix-1.1.0-win-x64-stable-full.nupkg"
    setup = b"v1.1 setup"
    full = b"v1.1 full"
    assets = json.dumps(
        [
            {"RelativeFileName": setup_name, "Type": "Installer"},
            {"RelativeFileName": full_name, "Type": "Full"},
        ],
        separators=(",", ":"),
    ).encode()
    artifacts = [
        {"name": setup_name, "bytes": len(setup), "sha256": publish_candidate.digest(setup)},
        {"name": full_name, "bytes": len(full), "sha256": publish_candidate.digest(full)},
        {
            "name": "assets.win-x64-stable.json",
            "bytes": len(assets),
            "sha256": publish_candidate.digest(assets),
        },
    ]
    for name, data in {
        "releases.win-x64-stable.json": b"releases",
        "RELEASES-win-x64-stable": b"releases-index",
    }.items():
        artifacts.append({"name": name, "bytes": len(data), "sha256": publish_candidate.digest(data)})
    manifest_bytes = json.dumps({"version": "1.1.0", "unsigned": True, "artifacts": artifacts}).encode()
    manifest_sha256 = publish_candidate.digest(manifest_bytes)
    candidate_prefix = f"candidates/1.1.0/{manifest_sha256}"
    objects = {
        f"{candidate_prefix}/release-manifest.json": manifest_bytes,
        f"{candidate_prefix}/{setup_name}": setup,
        f"{candidate_prefix}/{full_name}": full,
        f"{candidate_prefix}/assets.win-x64-stable.json": assets,
        f"{candidate_prefix}/releases.win-x64-stable.json": b"releases",
        f"{candidate_prefix}/RELEASES-win-x64-stable": b"releases-index",
        f"published/{setup_name}": b"v1.0 setup",
    }
    bucket = FakeBucket(objects)

    def get(url: str, *, headers=None, **_kwargs):
        key = "published/" + url.rsplit("/", 1)[1]
        return FakeResponse(bucket.objects[key], status_code=206 if headers else 200)

    monkeypatch.setattr(publish_candidate.oss2, "Auth", lambda *_args: object())
    monkeypatch.setattr(publish_candidate.oss2, "Bucket", lambda *_args: bucket)
    monkeypatch.setattr(publish_candidate.requests, "get", get)
    monkeypatch.setattr(
        publish_candidate.requests,
        "head",
        lambda *_args, **_kwargs: FakeResponse(setup, headers={"Cache-Control": "no-cache"}),
    )
    monkeypatch.setenv("ALIYUN_ACCESS_KEY_ID", "id")
    monkeypatch.setenv("ALIYUN_ACCESS_KEY_SECRET", "secret")
    monkeypatch.setenv("OSS_ENDPOINT", "https://oss.example.test")
    monkeypatch.setenv("OSS_BUCKET", "xenix")
    monkeypatch.setenv("RELEASES_OSS_PUBLIC_URL", "https://public.example.test/published")
    monkeypatch.setattr(sys, "argv", ["publish", "--version", "1.1.0", "--manifest-sha256", manifest_sha256])

    assert publish_candidate.main() == 0

    assert bucket.objects[f"published/{setup_name}"] == b"v1.0 setup"
    assert bucket.objects["published/Xenix-Setup.exe"] == setup
    assert bucket.objects[f"published/{full_name}"] == full
    assert bucket.objects["published/assets.win-x64-stable.json"] == assets
