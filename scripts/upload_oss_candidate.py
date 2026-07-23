from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import oss2


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def object_sha256(bucket, key: str) -> str:
    value = hashlib.sha256()
    stream = bucket.get_object(key)
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        value.update(chunk)
    return value.hexdigest()


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    manifest_path = root / "dist" / "release-manifest.json"
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()
    prefix = f"candidates/{manifest['version']}/{manifest_hash}"
    auth = oss2.Auth(os.environ["ALIYUN_ACCESS_KEY_ID"], os.environ["ALIYUN_ACCESS_KEY_SECRET"])
    bucket = oss2.Bucket(auth, os.environ["OSS_ENDPOINT"], os.environ["OSS_BUCKET"])
    headers = {"x-oss-forbid-overwrite": "true"}
    for artifact in manifest["artifacts"]:
        relative_path = Path(str(artifact["path"]))
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise RuntimeError(f"Unsafe release artifact path: {relative_path}")
        path = (root / "dist" / relative_path).resolve()
        path.relative_to((root / "dist").resolve())
        if path.name != artifact["name"]:
            raise RuntimeError(f"Release artifact name/path mismatch: {path}")
        if path.stat().st_size != artifact["bytes"] or sha256(path) != artifact["sha256"]:
            raise RuntimeError(f"Local artifact hash changed: {path}")
        key = f"{prefix}/{path.name}"
        if not bucket.object_exists(key):
            bucket.put_object_from_file(key, str(path), headers=headers)
        if (
            bucket.get_object_meta(key).content_length != artifact["bytes"]
            or object_sha256(bucket, key) != artifact["sha256"]
        ):
            raise RuntimeError(f"Candidate artifact verification failed: {key}")
    manifest_key = f"{prefix}/release-manifest.json"
    if bucket.object_exists(manifest_key):
        if object_sha256(bucket, manifest_key) != manifest_hash:
            raise RuntimeError(f"Conflicting candidate manifest: {manifest_key}")
    else:
        bucket.put_object(manifest_key, manifest_bytes, headers=headers)
    print(f"version={manifest['version']}")
    print(f"manifest_sha256={manifest_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
