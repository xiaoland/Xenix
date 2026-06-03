from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    src_path = project_root / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

    if len(sys.argv) >= 2 and sys.argv[1] == "--analysis-lambda-worker":
        from xenix.services.analysis_lambda_worker import main as worker_main

        if len(sys.argv) != 4:
            raise SystemExit("Usage: xenix --analysis-lambda-worker <input-json> <output-json>")
        worker_main(sys.argv[2], sys.argv[3])
        return 0

    from xenix.main import main as application_main

    return application_main(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
