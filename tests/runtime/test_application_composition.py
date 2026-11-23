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
        from PySide6.QtCore import QEventLoop, QTimer
        from xenix.app import build_main_window

        def wait_for_log(dialog, reference, text):
            dialog._search.setText(reference)
            loop = QEventLoop()
            poll = QTimer()
            def found():
                return dialog._selected_reference() == reference and text in dialog._logs._text.toPlainText()
            def check():
                if found():
                    loop.quit()
            poll.timeout.connect(check)
            poll.start(20)
            QTimer.singleShot(5000, loop.quit)
            loop.exec()
            assert found(), (reference, dialog._logs._text.toPlainText())

        handles = []
        app, window = build_main_window(show=False, show_splash=False, on_services_ready=handles.append)
        # Report driver assertions to pytest rather than the application's modal exception UI.
        sys.excepthook = sys.__excepthook__
        try:
            services = handles[0]
            imported = services.knowledge_import.enqueue_file(Path(sys.argv[1]))
            assert services.agent.scheduler.wait_idle(40), "Knowledge chain did not become idle"
            index_id = services.knowledge_index.enqueue_rebuild(("keyword",), trigger="manual")
            assert services.agent.scheduler.wait_idle(10), "Keyword index rebuild did not become idle"
            tasks = services.knowledge_tasks.list_tasks()
            assert not any(task.status in {"queued", "running", "failed", "needs_attention"} for task in tasks), tasks
            matches = services.agent.knowledge.lookup("umbrella inventory")
            assert any("three weeks" in match.quote for match in matches), matches
            window._open_jobs()
            jobs = window._auxiliary_windows._job_center_dialog
            jobs._scope_filter.setCurrentIndex(1)
            wait_for_log(jobs, f"knowledge:import:{imported.import_id}", "derivation finished")
            assert "snapshot" in jobs._logs._text.toPlainText()
            wait_for_log(jobs, f"knowledge:index:{index_id}", "index build finished")
            assert "rebuilding keyword" in jobs._logs._text.toPlainText()
            failed_index = services.knowledge_index.enqueue_rebuild(("text_vector",), trigger="manual")
            assert services.agent.scheduler.wait_idle(10), "Text vector rebuild did not become idle"
            wait_for_log(jobs, f"knowledge:index:{failed_index}", "ERROR: failed — index build failed")
            assert jobs._selected_job().status.value == "failed"
            assert jobs._selected_job().error_summary in jobs._detail.toPlainText()
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
