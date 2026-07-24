from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--executable",
        default=None,
        help="Path to the packaged executable. Defaults to dist/xenix/xenix.exe.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=240.0,
        help="Maximum time to wait for the packaged smoke test.",
    )
    return parser


def resolve_executable(explicit_path: str | None) -> Path:
    if explicit_path:
        return Path(explicit_path).resolve()

    project_root = Path(__file__).resolve().parents[1]
    return (project_root / "dist" / "xenix" / "xenix.exe").resolve()


def main() -> int:
    args = build_argument_parser().parse_args()
    executable = resolve_executable(args.executable)
    if not executable.is_file():
        raise FileNotFoundError(f"Packaged executable not found: {executable}")

    with tempfile.TemporaryDirectory(prefix="xenix-packaged-smoke-") as runtime_home:
        runtime_root = Path(runtime_home)
        environment = os.environ.copy()
        environment["XENIX_APP_HOME"] = str(runtime_root)
        project_root = Path(__file__).resolve().parents[1]
        catalog_path = project_root / "dist" / "knowledge-ocr" / "runtime_catalog.json"
        ocr_archive: Path | None = None
        if catalog_path.is_file():
            catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
            artifact_name = str(catalog.get("artifact_name") or "")
            candidate = catalog_path.parent / artifact_name
            if candidate.is_file() and candidate.name == artifact_name:
                ocr_archive = candidate.resolve()
                environment["XENIX_KNOWLEDGE_OCR_SMOKE_ARCHIVE"] = str(ocr_archive)
                golden_image = (
                    project_root
                    / "build"
                    / "knowledge-ocr"
                    / "downloads"
                    / "golden_image.png"
                )
                if not golden_image.is_file():
                    raise RuntimeError(
                        "Native OCR packaged smoke requires the locked golden image."
                    )
                environment["XENIX_KNOWLEDGE_OCR_SMOKE_IMAGE"] = str(
                    golden_image.resolve()
                )

        completed = subprocess.run(
            [str(executable), "--smoke-test"],
            cwd=str(executable.parent),
            env=environment,
            timeout=args.timeout_seconds,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(f"Packaged smoke test failed with exit code {completed.returncode}.")

        expected_paths = [
            runtime_root / "config",
            runtime_root / "logs",
            runtime_root / "cache",
            runtime_root / "state",
            runtime_root / "temp",
            runtime_root / "artifacts",
            runtime_root / "state" / "xenix.db",
            runtime_root / "state" / "knowledge-smoke.json",
            runtime_root / "logs" / "xenix.log",
        ]
        missing = [path for path in expected_paths if not path.exists()]
        if missing:
            joined = ", ".join(str(path) for path in missing)
            raise RuntimeError(f"Packaged smoke test did not create expected runtime artifacts: {joined}")
        marker = json.loads((runtime_root / "state" / "knowledge-smoke.json").read_text())
        if marker.get("spawned_docx_import") is not True:
            raise RuntimeError(
                "Packaged smoke did not import DOCX through the spawned Knowledge worker."
            )
        if marker.get("spawned_pptx_import") is not True:
            raise RuntimeError(
                "Packaged smoke did not import PPTX through the spawned Knowledge worker."
            )
        if marker.get("document_removal") is not True:
            raise RuntimeError(
                "Packaged smoke did not remove a Knowledge document through its lifecycle service."
            )
        if marker.get("same_sha_reimport") is not True:
            raise RuntimeError(
                "Packaged smoke did not re-import removed Knowledge content as a fresh identity."
            )
        if ocr_archive is not None and marker.get("paddle_native_activation") is not True:
            raise RuntimeError("Packaged smoke did not activate the native Knowledge OCR archive.")
        if ocr_archive is not None and marker.get("paddle_native_retrieval") is not True:
            raise RuntimeError(
                "Packaged smoke did not retrieve text from the native OCR import."
            )

    print(f"Packaged smoke test passed for {executable}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
