from __future__ import annotations

import argparse
import json
from pathlib import Path


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
    parser.add_argument("command", choices=("health", "warmup", "ocr"))
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.command == "health":
        import paddle
        import paddleocr

        print(
            json.dumps(
                {
                    "protocol": 1,
                    "paddle": getattr(paddle, "__version__", "unknown"),
                    "paddleocr": getattr(paddleocr, "__version__", "unknown"),
                }
            )
        )
        return 0
    engine = _engine()
    if args.command == "warmup":
        print(json.dumps({"protocol": 1, "models_ready": True}))
        return 0
    if args.input is None or args.output is None:
        parser.error("ocr requires --input and --output")
    results = []
    for result in engine.predict(str(args.input)):
        payload = result.json
        results.append(payload if isinstance(payload, dict) else json.loads(payload))
    args.output.write_text(
        json.dumps({"protocol": 1, "pages": results}, ensure_ascii=False),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
