from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import PurePosixPath

import oss2
import requests


FEED_NAMES = {"assets.win-x64-stable.json", "releases.win-x64-stable.json", "RELEASES-win-x64-stable"}
ASSETS_FEED_NAME = "assets.win-x64-stable.json"
MANIFEST_SCHEMA_VERSION = 2
ARTIFACT_TYPES = {"desktop_release", "update_feed", "knowledge_ocr_runtime"}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def remote_digest(url: str) -> str:
    response = requests.get(url, stream=True, timeout=120)
    response.raise_for_status()
    value = hashlib.sha256()
    for chunk in response.iter_content(1024 * 1024):
        value.update(chunk)
    return value.hexdigest()


def object_digest(bucket, key: str) -> str:
    value = hashlib.sha256()
    stream = bucket.get_object(key)
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        value.update(chunk)
    return value.hexdigest()


def public_feed_data(name: str, candidate_data: bytes, artifact_names: set[str]) -> bytes:
    if name != ASSETS_FEED_NAME:
        return candidate_data
    assets = json.loads(candidate_data)
    retained = [
        asset
        for asset in assets
        if str(asset.get("RelativeFileName") or "") in artifact_names
    ]
    if retained == assets:
        return candidate_data
    return json.dumps(retained, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def validated_artifacts(manifest: object, *, expected_version: str) -> list[dict]:
    if not isinstance(manifest, dict) or manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise RuntimeError("Candidate manifest schema is unsupported.")
    if (
        manifest.get("version") != expected_version
        or manifest.get("unsigned") is not True
        or manifest.get("packaged_smoke") != "passed"
    ):
        raise RuntimeError("Manifest identity or unsigned boundary is invalid.")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise RuntimeError("Candidate manifest has no artifacts.")
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
            raise RuntimeError("Candidate artifact shape is invalid.")
        artifact_type = item["type"]
        name = item["name"]
        raw_path = item["path"]
        if not isinstance(raw_path, str) or not raw_path:
            raise RuntimeError("Candidate artifact identity is invalid.")
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
            or not isinstance(item["sha256"], str)
            or len(item["sha256"]) != 64
            or set(item["sha256"]) - set("0123456789abcdef")
        ):
            raise RuntimeError("Candidate artifact identity is invalid.")
        names.add(name)
        ocr_count += artifact_type == "knowledge_ocr_runtime"
        validated.append(item)
    if ocr_count != 1:
        raise RuntimeError("Candidate must contain exactly one Knowledge OCR runtime.")
    return validated


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--manifest-sha256", required=True)
    args = parser.parse_args()
    auth = oss2.Auth(os.environ["ALIYUN_ACCESS_KEY_ID"], os.environ["ALIYUN_ACCESS_KEY_SECRET"])
    endpoint = os.environ["OSS_ENDPOINT"]
    bucket = oss2.Bucket(auth, endpoint, os.environ["OSS_BUCKET"])
    candidate_prefix = f"candidates/{args.version}/{args.manifest_sha256}"
    published_prefix = "published"
    manifest_bytes = bucket.get_object(f"{candidate_prefix}/release-manifest.json").read()
    if digest(manifest_bytes) != args.manifest_sha256:
        raise RuntimeError("Candidate manifest digest does not match the approved digest.")
    manifest = json.loads(manifest_bytes)
    artifacts = validated_artifacts(manifest, expected_version=args.version)
    artifact_names = {item["name"] for item in artifacts}
    immutable = [item for item in artifacts if item["name"] not in FEED_NAMES]
    feeds = [item for item in artifacts if item["name"] in FEED_NAMES]
    setups = [item for item in artifacts if "Setup" in item["name"]]
    for item in artifacts:
        candidate_key = f"{candidate_prefix}/{item['name']}"
        if (
            not bucket.object_exists(candidate_key)
            or bucket.get_object_meta(candidate_key).content_length != item["bytes"]
            or object_digest(bucket, candidate_key) != item["sha256"]
        ):
            raise RuntimeError(f"Candidate artifact verification failed: {item['name']}")
    for item in immutable:
        published_key = f"{published_prefix}/{item['name']}"
        if bucket.object_exists(published_key):
            if object_digest(bucket, published_key) != item["sha256"]:
                raise RuntimeError(f"Conflicting published artifact: {item['name']}")
        else:
            bucket.copy_object(
                bucket.bucket_name,
                f"{candidate_prefix}/{item['name']}",
                published_key,
                headers={"x-oss-forbid-overwrite": "true"},
            )
        if bucket.get_object_meta(published_key).content_length != item["bytes"]:
            raise RuntimeError(f"Published size mismatch: {item['name']}")
    origin = os.environ["RELEASES_OSS_PUBLIC_URL"].rstrip("/")
    for item in immutable:
        if remote_digest(f"{origin}/{item['name']}") != item["sha256"]:
            raise RuntimeError(f"Public release URL hash mismatch: {item['name']}")
        ranged = requests.get(f"{origin}/{item['name']}", headers={"Range": "bytes=0-0"}, timeout=30)
        if ranged.status_code != 206:
            raise RuntimeError(f"Public release URL Range request failed: {item['name']}")
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    for item in feeds:
        key = f"{published_prefix}/{item['name']}"
        previous_hash = None
        if bucket.object_exists(key):
            previous = bucket.get_object(key).read()
            previous_hash = digest(previous)
            bucket.put_object(
                f"{published_prefix}/publication-history/{stamp}/{item['name']}", previous,
                headers={"x-oss-forbid-overwrite": "true"},
            )
        candidate_data = bucket.get_object(f"{candidate_prefix}/{item['name']}").read()
        if digest(candidate_data) != item["sha256"]:
            raise RuntimeError(f"Candidate feed hash mismatch: {item['name']}")
        data = public_feed_data(item["name"], candidate_data, artifact_names)
        public_hash = digest(data)
        if previous_hash is not None and object_digest(bucket, key) != previous_hash:
            raise RuntimeError(f"Live feed changed during publication: {item['name']}")
        bucket.put_object(key, data, headers={"Cache-Control": "no-cache"})
        if remote_digest(f"{origin}/{item['name']}") != public_hash:
            raise RuntimeError(f"Published feed URL hash mismatch: {item['name']}")
        if public_hash != item["sha256"]:
            print(f"public_feed_sha256 name={item['name']} sha256={public_hash}")
    for item in setups:
        bucket.copy_object(
            bucket.bucket_name,
            f"{candidate_prefix}/{item['name']}",
            f"{published_prefix}/Xenix-Setup.exe",
            headers={
                "x-oss-metadata-directive": "REPLACE",
                "Cache-Control": "no-cache",
                "Content-Type": "application/octet-stream",
            },
        )
        if remote_digest(f"{origin}/Xenix-Setup.exe") != item["sha256"]:
            raise RuntimeError("Stable Setup alias hash mismatch.")
        alias_response = requests.head(f"{origin}/Xenix-Setup.exe", timeout=30)
        alias_response.raise_for_status()
        if "no-cache" not in alias_response.headers.get("Cache-Control", "").lower():
            raise RuntimeError("Stable Setup alias cache metadata is invalid.")
    print(f"published_version={args.version}")
    print(f"rollback_history={published_prefix}/publication-history/{stamp}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
