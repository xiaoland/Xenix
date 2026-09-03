from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from urllib.parse import quote
from uuid import uuid4

import oss2
import requests


FEED_NAMES = {
    "assets.win-x64-stable.json",
    "releases.win-x64-stable.json",
    "RELEASES-win-x64-stable",
}
ASSETS_FEED_NAME = "assets.win-x64-stable.json"
CANONICAL_FEED_NAME = "releases.win-x64-stable.json"
FEED_PUBLICATION_ORDER = (
    "RELEASES-win-x64-stable",
    ASSETS_FEED_NAME,
    CANONICAL_FEED_NAME,
)
MANIFEST_SCHEMA_VERSION = 3
RELEASE_PROTOCOL_VERSION = 1
ARTIFACT_TYPES = {"desktop_release", "update_feed", "knowledge_ocr_runtime"}
_COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}")
_STABLE_SEMVER_PATTERN = re.compile(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)")
_UPLOAD_THRESHOLD = 64 * 1024 * 1024
_UPLOAD_PART_SIZE = 16 * 1024 * 1024


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and not set(value) - set("0123456789abcdef")
    )


def file_digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def _stable_semver(value: str) -> tuple[int, int, int]:
    match = _STABLE_SEMVER_PATTERN.fullmatch(value)
    if not match:
        raise RuntimeError(
            f"Public releases require stable SemVer X.Y.Z, found {value!r}."
        )
    return tuple(int(part) for part in match.groups())


def current_release_version(data: bytes) -> str | None:
    document = json.loads(data)
    assets = document.get("Assets") if isinstance(document, dict) else None
    if not isinstance(assets, list):
        raise RuntimeError("Published canonical release feed shape is invalid.")
    versions = {
        str(item.get("Version"))
        for item in assets
        if isinstance(item, dict) and item.get("Version")
    }
    if not versions:
        return None
    return max(versions, key=_stable_semver)


def public_feed_data(
    name: str,
    release_data: bytes,
    artifact_names: set[str],
) -> bytes:
    if name != ASSETS_FEED_NAME:
        return release_data
    assets = json.loads(release_data)
    if not isinstance(assets, list):
        raise RuntimeError("Velopack assets feed shape is invalid.")
    retained = [
        asset
        for asset in assets
        if isinstance(asset, dict)
        and str(asset.get("RelativeFileName") or "") in artifact_names
    ]
    if retained == assets:
        return release_data
    return json.dumps(
        retained,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")


def validated_artifacts(
    manifest: object,
    *,
    expected_tag: str,
    expected_commit: str,
    expected_promotion_pr: int | None,
    expected_repository: str | None = None,
) -> list[dict]:
    if not isinstance(manifest, dict) or manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise RuntimeError("Release manifest schema is unsupported.")
    version = manifest.get("version")
    release = manifest.get("release")
    workflow = manifest.get("workflow")
    if (
        not isinstance(version, str)
        or expected_tag != f"v{version}"
        or manifest.get("commit") != expected_commit
        or manifest.get("unsigned") is not True
        or manifest.get("packaged_smoke") != "passed"
        or not isinstance(release, dict)
        or release.keys() != {"protocol_version", "tag", "promotion_pr"}
        or release.get("protocol_version") != RELEASE_PROTOCOL_VERSION
        or release.get("tag") != expected_tag
        or (
            expected_promotion_pr is not None
            and release.get("promotion_pr") != expected_promotion_pr
        )
        or not isinstance(workflow, dict)
        or workflow.keys() != {"repository", "run_id", "run_attempt"}
        or type(workflow.get("run_id")) is not int
        or workflow["run_id"] < 1
        or type(workflow.get("run_attempt")) is not int
        or workflow["run_attempt"] < 1
        or not isinstance(manifest.get("toolchain"), dict)
        or not manifest["toolchain"]
        or not _is_sha256(manifest.get("release_toml_sha256"))
        or not _is_sha256(manifest.get("lock_sha256"))
    ):
        raise RuntimeError("Release manifest identity or unsigned boundary is invalid.")
    if expected_repository is not None and workflow.get("repository") != expected_repository:
        raise RuntimeError("Release manifest repository identity is invalid.")
    _stable_semver(version)
    if not _COMMIT_PATTERN.fullmatch(expected_commit):
        raise RuntimeError("Expected release commit identity is invalid.")

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise RuntimeError("Release manifest has no artifacts.")
    validated: list[dict] = []
    names: set[str] = set()
    ocr_count = 0
    for item in artifacts:
        if not isinstance(item, dict) or item.keys() != {
            "type",
            "path",
            "name",
            "bytes",
            "sha256",
        }:
            raise RuntimeError("Release artifact shape is invalid.")
        artifact_type = item["type"]
        name = item["name"]
        raw_path = item["path"]
        if not isinstance(raw_path, str) or not raw_path:
            raise RuntimeError("Release artifact identity is invalid.")
        relative = PurePosixPath(raw_path)
        if (
            artifact_type not in ARTIFACT_TYPES
            or not isinstance(name, str)
            or not name
            or name in {".", ".."}
            or "/" in name
            or "\\" in name
            or relative.is_absolute()
            or ".." in relative.parts
            or relative.name != name
            or name in names
            or type(item["bytes"]) is not int
            or item["bytes"] < 1
            or not _is_sha256(item["sha256"])
        ):
            raise RuntimeError("Release artifact identity is invalid.")
        names.add(name)
        ocr_count += artifact_type == "knowledge_ocr_runtime"
        validated.append(item)
    if ocr_count != 1:
        raise RuntimeError("Release must contain exactly one Knowledge OCR runtime.")
    return validated


def partition_artifacts(
    artifacts: list[dict],
) -> tuple[list[dict], dict[str, dict], dict]:
    feeds = {
        item["name"]: item
        for item in artifacts
        if item["name"] in FEED_NAMES
    }
    setups = [
        item
        for item in artifacts
        if item["type"] == "desktop_release"
        and item["name"].endswith("-Setup.exe")
    ]
    if len(setups) != 1:
        raise RuntimeError("Release must contain exactly one Windows Setup.")
    if set(feeds) != FEED_NAMES or any(
        item["type"] != "update_feed" for item in feeds.values()
    ):
        raise RuntimeError("Release update feed set is invalid.")
    excluded_names = FEED_NAMES | {setups[0]["name"]}
    immutable = [item for item in artifacts if item["name"] not in excluded_names]
    if not immutable:
        raise RuntimeError("Release has no immutable package artifacts.")
    return immutable, feeds, setups[0]


@dataclass(frozen=True)
class PublicationPlan:
    root: Path
    manifest_path: Path
    manifest: dict
    artifacts: list[dict]
    immutable: list[dict]
    feeds: dict[str, dict]
    setup: dict

    @property
    def version(self) -> str:
        return str(self.manifest["version"])

    @property
    def tag(self) -> str:
        return str(self.manifest["release"]["tag"])


@dataclass(frozen=True)
class PublicationResult:
    history_prefix: str
    publication_seconds: float
    visibility_seconds: float


def build_plan(
    root: Path,
    *,
    manifest_path: Path,
    expected_tag: str,
    expected_commit: str,
    expected_promotion_pr: int | None,
    expected_repository: str | None,
) -> PublicationPlan:
    manifest_path = manifest_path.resolve()
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("Release manifest cannot be read.") from exc
    artifacts = validated_artifacts(
        manifest,
        expected_tag=expected_tag,
        expected_commit=expected_commit,
        expected_promotion_pr=expected_promotion_pr,
        expected_repository=expected_repository,
    )
    immutable, feeds, setup = partition_artifacts(artifacts)
    return PublicationPlan(
        root=root.resolve(),
        manifest_path=manifest_path,
        manifest=manifest,
        artifacts=artifacts,
        immutable=immutable,
        feeds=feeds,
        setup=setup,
    )


def _artifact_path(plan: PublicationPlan, item: dict) -> Path:
    relative = PurePosixPath(item["path"])
    return plan.root / "dist" / Path(*relative.parts)


def verify_local_artifacts(plan: PublicationPlan) -> None:
    for item in plan.artifacts:
        path = _artifact_path(plan, item)
        if (
            not path.is_file()
            or path.stat().st_size != item["bytes"]
            or file_digest(path) != item["sha256"]
        ):
            raise RuntimeError(f"Local release artifact verification failed: {item['name']}")


class _ProgressHeartbeat:
    def __init__(self, *, operation: str, interval_seconds: int = 60) -> None:
        self._operation = operation
        self._interval_seconds = interval_seconds
        self._last = 0.0
        self._started = time.monotonic()

    def __call__(self, consumed: int, total: int) -> None:
        now = time.monotonic()
        if consumed == total or now - self._last >= self._interval_seconds:
            percent = 100.0 if not total else consumed * 100.0 / total
            elapsed = max(now - self._started, 0.001)
            rate_mib_s = consumed / elapsed / (1024 * 1024)
            print(
                f"progress operation={self._operation} "
                f"bytes={consumed}/{total} percent={percent:.1f} "
                f"rate_mib_s={rate_mib_s:.2f}",
                flush=True,
            )
            self._last = now


class OssReleaseStore:
    def __init__(
        self,
        bucket,
        *,
        public_origin: str,
        checkpoint_root: Path,
    ) -> None:
        self.bucket = bucket
        self.public_origin = public_origin.rstrip("/")
        self.checkpoint_store = oss2.ResumableStore(root=str(checkpoint_root))

    @classmethod
    def from_environment(cls, *, checkpoint_root: Path) -> OssReleaseStore:
        auth = oss2.Auth(
            os.environ["ALIYUN_ACCESS_KEY_ID"],
            os.environ["ALIYUN_ACCESS_KEY_SECRET"],
        )
        bucket = oss2.Bucket(
            auth,
            os.environ["OSS_ENDPOINT"],
            os.environ["OSS_BUCKET"],
        )
        return cls(
            bucket,
            public_origin=os.environ["RELEASES_OSS_PUBLIC_URL"],
            checkpoint_root=checkpoint_root,
        )

    def exists(self, key: str) -> bool:
        return bool(self.bucket.object_exists(key))

    def read(self, key: str) -> bytes:
        return self.bucket.get_object(key).read()

    def size(self, key: str) -> int:
        return int(self.bucket.get_object_meta(key).content_length)

    def put_bytes_immutable(self, key: str, data: bytes) -> None:
        if self.exists(key):
            if self.read(key) != data:
                raise RuntimeError(f"Conflicting immutable release object: {key}")
            return
        self.bucket.put_object(
            key,
            data,
            headers={"x-oss-forbid-overwrite": "true"},
        )

    def upload_file(
        self,
        key: str,
        path: Path,
        *,
        immutable: bool,
        cache_control: str | None = None,
    ) -> None:
        if immutable and self.exists(key):
            if self.size(key) != path.stat().st_size:
                raise RuntimeError(f"Conflicting immutable release object: {key}")
            return
        headers: dict[str, str] = {}
        if immutable:
            headers["x-oss-forbid-overwrite"] = "true"
        if cache_control:
            headers["Cache-Control"] = cache_control
        print(
            f"upload_start key={key} bytes={path.stat().st_size} "
            f"multipart_threshold={_UPLOAD_THRESHOLD} "
            f"part_size={_UPLOAD_PART_SIZE} threads=4 resumable=true",
            flush=True,
        )
        oss2.resumable_upload(
            self.bucket,
            key,
            str(path),
            store=self.checkpoint_store,
            headers=headers,
            multipart_threshold=_UPLOAD_THRESHOLD,
            part_size=_UPLOAD_PART_SIZE,
            progress_callback=_ProgressHeartbeat(operation=f"upload:{key}"),
            num_threads=4,
        )
        print(f"upload_complete key={key}", flush=True)

    def put_bytes_mutable(self, key: str, data: bytes) -> None:
        self.bucket.put_object(key, data, headers={"Cache-Control": "no-cache"})

    def delete(self, key: str) -> None:
        self.bucket.delete_object(key)

    def copy(
        self,
        source: str,
        destination: str,
        *,
        immutable: bool,
        cache_control: str | None = None,
    ) -> None:
        headers: dict[str, str] = {}
        if immutable:
            headers["x-oss-forbid-overwrite"] = "true"
        if cache_control:
            headers.update(
                {
                    "x-oss-metadata-directive": "REPLACE",
                    "Cache-Control": cache_control,
                    "Content-Type": "application/octet-stream",
                }
            )
        self.bucket.copy_object(
            self.bucket.bucket_name,
            source,
            destination,
            headers=headers,
        )

    def _public_url(self, key: str) -> str:
        prefix = "published/"
        if not key.startswith(prefix):
            raise RuntimeError(f"Object is outside the published prefix: {key}")
        relative = key.removeprefix(prefix)
        encoded = "/".join(quote(part, safe="") for part in relative.split("/"))
        return f"{self.public_origin}/{encoded}"

    def public_digest(self, key: str) -> str:
        response = requests.get(self._public_url(key), stream=True, timeout=120)
        response.raise_for_status()
        expected = int(response.headers.get("Content-Length") or 0)
        consumed = 0
        value = hashlib.sha256()
        heartbeat = _ProgressHeartbeat(operation=f"verify:{key}")
        for chunk in response.iter_content(1024 * 1024):
            if not chunk:
                continue
            value.update(chunk)
            consumed += len(chunk)
            heartbeat(consumed, expected)
        if not expected:
            heartbeat(consumed, consumed)
        return value.hexdigest()

    def verify_public(self, key: str, expected_sha256: str) -> None:
        if self.public_digest(key) != expected_sha256:
            raise RuntimeError(f"Public release URL hash mismatch: {key}")
        ranged = requests.get(
            self._public_url(key),
            headers={"Range": "bytes=0-0"},
            timeout=30,
        )
        if ranged.status_code != 206:
            raise RuntimeError(f"Public release URL Range request failed: {key}")

    def require_no_cache(self, key: str) -> None:
        response = requests.head(self._public_url(key), timeout=30)
        response.raise_for_status()
        if "no-cache" not in response.headers.get("Cache-Control", "").lower():
            raise RuntimeError(f"Public release cache metadata is invalid: {key}")


def _history_prefix(plan: PublicationPlan) -> str:
    workflow = plan.manifest["workflow"]
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return (
        "published/publication-history/"
        f"{plan.tag}/{workflow['run_id']}-{workflow['run_attempt']}-"
        f"{stamp}-{uuid4().hex[:8]}"
    )


def publish_release(plan: PublicationPlan, store: OssReleaseStore) -> PublicationResult:
    print("phase=verify-local-artifacts", flush=True)
    verify_local_artifacts(plan)
    canonical_key = f"published/{CANONICAL_FEED_NAME}"
    if store.exists(canonical_key):
        current = current_release_version(store.read(canonical_key))
        if current is not None and _stable_semver(current) > _stable_semver(plan.version):
            raise RuntimeError(
                f"Release version regression is forbidden: {plan.version} < {current}."
            )

    publication_started = time.monotonic()
    print("phase=publish-immutable-artifacts", flush=True)
    for item in plan.immutable:
        key = f"published/{item['name']}"
        store.upload_file(
            key,
            _artifact_path(plan, item),
            immutable=True,
        )
        store.verify_public(key, item["sha256"])

    manifest_data = plan.manifest_path.read_bytes()
    manifest_key = f"published/release-manifests/{plan.tag}.json"
    store.put_bytes_immutable(manifest_key, manifest_data)
    store.verify_public(manifest_key, digest(manifest_data))

    visibility_started = time.monotonic()
    history_prefix = _history_prefix(plan)
    mutable_keys = [
        f"published/{plan.setup['name']}",
        "published/Xenix-Setup.exe",
        *(f"published/{name}" for name in FEED_PUBLICATION_ORDER),
    ]
    print(f"phase=snapshot-live-projections history={history_prefix}", flush=True)
    for key in mutable_keys:
        if store.exists(key):
            store.copy(
                key,
                f"{history_prefix}/{key.removeprefix('published/')}",
                immutable=True,
            )

    print("phase=publish-setup-projections", flush=True)
    generated_setup_key = f"published/{plan.setup['name']}"
    store.upload_file(
        generated_setup_key,
        _artifact_path(plan, plan.setup),
        immutable=False,
        cache_control="no-cache",
    )
    store.verify_public(generated_setup_key, plan.setup["sha256"])
    store.require_no_cache(generated_setup_key)
    alias_key = "published/Xenix-Setup.exe"
    store.copy(
        generated_setup_key,
        alias_key,
        immutable=False,
        cache_control="no-cache",
    )
    store.verify_public(alias_key, plan.setup["sha256"])
    store.require_no_cache(alias_key)

    print("phase=publish-feeds", flush=True)
    artifact_names = {item["name"] for item in plan.artifacts}
    for name in FEED_PUBLICATION_ORDER:
        item = plan.feeds[name]
        source = _artifact_path(plan, item).read_bytes()
        data = public_feed_data(name, source, artifact_names)
        key = f"published/{name}"
        store.put_bytes_mutable(key, data)
        store.verify_public(key, digest(data))
        store.require_no_cache(key)
        print(f"feed_published name={name} sha256={digest(data)}", flush=True)

    print(f"published_version={plan.version}")
    print(f"published_tag={plan.tag}")
    print(f"rollback_history={history_prefix}/")
    completed = time.monotonic()
    return PublicationResult(
        history_prefix=history_prefix,
        publication_seconds=round(completed - publication_started, 2),
        visibility_seconds=round(completed - visibility_started, 2),
    )


def _write_publication_evidence(
    plan: PublicationPlan,
    result: PublicationResult,
) -> Path:
    destination = plan.root / "dist" / "release-publication-timing.json"
    payload = {
        "schema_version": 1,
        "version": plan.version,
        "tag": plan.tag,
        "commit": plan.manifest["commit"],
        "promotion_pr": plan.manifest["release"]["promotion_pr"],
        "workflow": plan.manifest["workflow"],
        "publication_seconds": result.publication_seconds,
        "visibility_seconds": result.visibility_seconds,
        "rollback_history": f"{result.history_prefix}/",
    }
    destination.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return destination


def _write_github_outputs(plan: PublicationPlan, result: PublicationResult) -> None:
    destination = os.environ.get("GITHUB_OUTPUT", "").strip()
    if not destination:
        return
    with Path(destination).open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(f"published_version={plan.version}\n")
        stream.write(f"published_tag={plan.tag}\n")
        stream.write(f"rollback_history={result.history_prefix}/\n")
        stream.write(f"publication_seconds={result.publication_seconds}\n")
        stream.write(f"visibility_seconds={result.visibility_seconds}\n")


def _optional_positive_int(raw: str) -> int | None:
    value = raw.strip()
    if not value:
        return None
    parsed = int(value)
    if parsed < 1:
        raise ValueError("promotion PR must be a positive integer when present")
    return parsed


def cleanup_orphans(tag: str, store: OssReleaseStore) -> None:
    """Delete orphaned immutable objects left by a failed publish.

    A transient failure after the immutable uploads leaves the versioned
    package and OCR objects plus the manifest, while the canonical feed still
    points at the previous release. Removing only those immutable objects lets
    an unchanged-tag retry converge instead of failing closed on a byte
    mismatch caused by a non-reproducible rebuild.
    """
    manifest_key = f"published/release-manifests/{tag}.json"
    if not store.exists(manifest_key):
        print(f"cleanup_manifest_missing key={manifest_key}")
        return
    manifest = json.loads(store.read(manifest_key))
    if not isinstance(manifest, dict):
        raise RuntimeError("Release manifest is not an object.")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        raise RuntimeError("Release manifest has no artifacts.")
    excluded = FEED_NAMES | {
        str(item.get("name") or "")
        for item in artifacts
        if isinstance(item, dict)
        and item.get("type") == "desktop_release"
        and str(item.get("name") or "").endswith("-Setup.exe")
    }
    keys = [
        f"published/{item['name']}"
        for item in artifacts
        if isinstance(item, dict) and item.get("name") not in excluded
    ] + [manifest_key]
    for key in keys:
        if store.exists(key):
            store.delete(key)
            print(f"cleanup_deleted key={key}")
        else:
            print(f"cleanup_absent key={key}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cleanup-orphans",
        dest="cleanup_tag",
        default="",
        help="Delete orphaned immutable objects for a release tag instead of publishing.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("dist/release-manifest.json"),
    )
    parser.add_argument("--tag", default=os.environ.get("XENIX_RELEASE_TAG", ""))
    parser.add_argument("--commit", default=os.environ.get("GITHUB_SHA", ""))
    parser.add_argument(
        "--promotion-pr",
        default=os.environ.get("XENIX_PROMOTION_PR", ""),
    )
    parser.add_argument(
        "--repository",
        default=os.environ.get("GITHUB_REPOSITORY", ""),
    )
    args = parser.parse_args()
    if args.cleanup_tag:
        store = OssReleaseStore.from_environment(
            checkpoint_root=Path("build") / "release-upload-checkpoints",
        )
        cleanup_orphans(args.cleanup_tag, store)
        return 0
    promotion_pr = _optional_positive_int(args.promotion_pr)
    if not args.tag or not args.commit or not args.repository:
        raise RuntimeError(
            "Release tag, commit, and repository are required."
        )
    root = Path(__file__).resolve().parents[1]
    plan = build_plan(
        root,
        manifest_path=(root / args.manifest),
        expected_tag=args.tag,
        expected_commit=args.commit,
        expected_promotion_pr=promotion_pr,
        expected_repository=args.repository,
    )
    store = OssReleaseStore.from_environment(
        checkpoint_root=root / "build" / "release-upload-checkpoints",
    )
    result = publish_release(plan, store)
    _write_publication_evidence(plan, result)
    _write_github_outputs(plan, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
