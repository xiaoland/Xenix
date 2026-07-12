from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime

import oss2
import requests


FEED_NAMES = {"assets.win-x64-stable.json", "releases.win-x64-stable.json", "RELEASES-win-x64-stable"}


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
    if manifest["version"] != args.version or not manifest["unsigned"]:
        raise RuntimeError("Manifest identity or unsigned boundary is invalid.")
    immutable = [
        item
        for item in manifest["artifacts"]
        if item["name"] not in FEED_NAMES and "Setup" not in item["name"]
    ]
    feeds = [item for item in manifest["artifacts"] if item["name"] in FEED_NAMES]
    setups = [item for item in manifest["artifacts"] if "Setup" in item["name"]]
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
        data = bucket.get_object(f"{candidate_prefix}/{item['name']}").read()
        if digest(data) != item["sha256"]:
            raise RuntimeError(f"Candidate feed hash mismatch: {item['name']}")
        if previous_hash is not None and object_digest(bucket, key) != previous_hash:
            raise RuntimeError(f"Live feed changed during publication: {item['name']}")
        bucket.put_object(key, data, headers={"Cache-Control": "no-cache"})
        if remote_digest(f"{origin}/{item['name']}") != item["sha256"]:
            raise RuntimeError(f"Published feed URL hash mismatch: {item['name']}")
    for item in setups:
        bucket.copy_object(
            bucket.bucket_name,
            f"{candidate_prefix}/{item['name']}",
            f"{published_prefix}/Xenix-Setup.exe",
            headers={"Cache-Control": "no-cache"},
        )
        if remote_digest(f"{origin}/Xenix-Setup.exe") != item["sha256"]:
            raise RuntimeError("Stable Setup alias hash mismatch.")
    print(f"published_version={args.version}")
    print(f"rollback_history={published_prefix}/publication-history/{stamp}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
