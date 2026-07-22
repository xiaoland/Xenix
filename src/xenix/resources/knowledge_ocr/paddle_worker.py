from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
from contextlib import redirect_stdout
from pathlib import Path


SIDECAR_PROTOCOL_VERSION = 1
PYTHON_VERSION = "3.13.13"
PADDLE_VERSION = "3.3.1"
PADDLE_OCR_VERSION = "3.7.0"
MODEL_INVENTORY_VERSION = 2
MODEL_MARKER = (
    f"xenix-paddleocr-models:v{SIDECAR_PROTOCOL_VERSION}:"
    f"python-{PYTHON_VERSION}:paddle-{PADDLE_VERSION}:paddleocr-{PADDLE_OCR_VERSION}:"
    f"inventory-{MODEL_INVENTORY_VERSION}"
)
MODEL_HASH_BLOCK_BYTES = 1024 * 1024


def _model_file_fingerprint(path: Path) -> tuple[int, bytes]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as source:
        for block in iter(lambda: source.read(MODEL_HASH_BLOCK_BYTES), b""):
            size += len(block)
            digest.update(block)
    return size, digest.digest()


def _model_inventory() -> dict[str, object]:
    configured_root = (
        os.environ.get("PADDLE_PDX_CACHE_HOME")
        or os.environ.get("PADDLEX_HOME")
        or os.environ.get("PADDLEOCR_HOME")
    )
    root = Path(configured_root) if configured_root else None
    digest = hashlib.sha256(
        f"xenix.paddleocr.model-inventory.v{MODEL_INVENTORY_VERSION}\0".encode("ascii")
    )
    count = 0
    if root is not None and root.is_dir():
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.is_symlink():
                continue
            try:
                relative = path.relative_to(root).as_posix().encode("utf-8")
                size, content_sha256 = _model_file_fingerprint(path)
            except OSError:
                continue
            digest.update(len(relative).to_bytes(4, "big"))
            digest.update(relative)
            digest.update(size.to_bytes(8, "big"))
            digest.update(content_sha256)
            count += 1
    return {
        "model_file_count": count,
        "model_inventory_sha256": digest.hexdigest(),
    }


def _engine():
    from paddleocr import PaddleOCR

    return PaddleOCR(
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        enable_mkldnn=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("health", "models", "warmup", "ocr"))
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.command == "health":
        with redirect_stdout(sys.stderr):
            import paddle
            import paddleocr

        print(
            json.dumps(
                {
                    "protocol": SIDECAR_PROTOCOL_VERSION,
                    "python": platform.python_version(),
                    "paddle": getattr(paddle, "__version__", "unknown"),
                    "paddleocr": getattr(paddleocr, "__version__", "unknown"),
                },
                sort_keys=True,
            )
        )
        return 0
    if args.command == "models":
        print(
            json.dumps(
                {"protocol": SIDECAR_PROTOCOL_VERSION, **_model_inventory()},
                sort_keys=True,
            )
        )
        return 0
    if args.command == "warmup":
        with redirect_stdout(sys.stderr):
            _engine()
        print(
            json.dumps(
                {
                    "protocol": SIDECAR_PROTOCOL_VERSION,
                    "model_marker": MODEL_MARKER,
                    "models_ready": True,
                    **_model_inventory(),
                },
                sort_keys=True,
            )
        )
        return 0
    if args.input is None or args.output is None:
        parser.error("ocr requires --input and --output")
    engine = _engine()
    results = []
    for result in engine.predict(str(args.input)):
        payload = result.json
        results.append(payload if isinstance(payload, dict) else json.loads(payload))
    args.output.write_text(
        json.dumps(
            {"protocol": SIDECAR_PROTOCOL_VERSION, "pages": results},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
