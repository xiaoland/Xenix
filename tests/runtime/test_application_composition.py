"""Exercise desktop wiring in a separate Qt process with real local services."""

import os
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest

from tests.support.paths import PROJECT_ROOT

pytestmark = pytest.mark.slow


def test_desktop_composition_connects_knowledge_jobs_and_job_center(app_paths, tmp_path: Path):
    source = tmp_path / "inventory-rules.txt"
    source.write_text("Umbrella inventory uses three weeks of average sales.", encoding="utf-8")
    driver = textwrap.dedent("""
        import sys
        from pathlib import Path

        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QPushButton

        from tests.support.ui_queries import find_control
        from xenix.app import build_main_window
        from xenix.ui.job_center import JobCenterDialog

        handles = []
        app, window = build_main_window(show_splash=False, on_services_ready=handles.append)
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

            jobs_button = find_control(window, "main.header.jobs", QPushButton)
            assert jobs_button.isVisible(), "The main window's Jobs button is hidden"
            QTest.mouseClick(jobs_button, Qt.MouseButton.LeftButton)
            app.processEvents()
            assert any(dialog.isVisible() for dialog in window.findChildren(JobCenterDialog)), (
                "The main window's Jobs button did not open the Job Center"
            )
            print("DESKTOP_KNOWLEDGE_AND_JOBS_OK")
        finally:
            window.close()
            app.processEvents()
    """)
    result = subprocess.run(
        [sys.executable, "-c", driver, str(source)],
        cwd=tmp_path,
        env={
            **os.environ,
            "PYTHONPATH": os.pathsep.join((str(PROJECT_ROOT / "src"), str(PROJECT_ROOT))),
            "QT_QPA_PLATFORM": "offscreen",
        },
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=70,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "DESKTOP_KNOWLEDGE_AND_JOBS_OK" in result.stdout
