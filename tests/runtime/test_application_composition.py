"""Exercise desktop wiring in a separate Qt process with real local services."""

import os
from pathlib import Path
import subprocess
import sys
import textwrap

from tests.support.paths import PROJECT_ROOT


def test_desktop_import_reaches_keyword_retrieval_through_all_job_kinds(app_paths, tmp_path: Path):
    source = tmp_path / "inventory-rules.txt"
    source.write_text("Umbrella inventory uses three weeks of average sales.", encoding="utf-8")
    driver = textwrap.dedent("""
        import sys
        from pathlib import Path
        from xenix.app import build_main_window

        handles = []
        app, window = build_main_window(show=False, show_splash=False, on_services_ready=handles.append)
        # Report driver assertions to pytest rather than the application's modal exception UI.
        sys.excepthook = sys.__excepthook__
        try:
            services = handles[0]
            services.knowledge_import.enqueue_file(Path(sys.argv[1]))
            assert services.agent.scheduler.wait_idle(40), "Knowledge chain did not become idle"
            tasks = services.knowledge_tasks.list_tasks()
            assert not any(task.status in {"queued", "running", "failed", "needs_attention"} for task in tasks), tasks
            matches = services.agent.knowledge.lookup("umbrella inventory")
            assert any("three weeks" in match.quote for match in matches), matches
            print("DESKTOP_KNOWLEDGE_CHAIN_OK")
        finally:
            window.close()
            app.processEvents()
    """)
    result = subprocess.run(
        [sys.executable, "-c", driver, str(source)],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT / "src"), "QT_QPA_PLATFORM": "offscreen"},
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=70,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "DESKTOP_KNOWLEDGE_CHAIN_OK" in result.stdout
