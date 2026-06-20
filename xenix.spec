# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs


project_root = Path.cwd()
src_root = project_root / "src"
scripts_root = project_root / "scripts"
xgboost_binaries = collect_dynamic_libs("xgboost")
xgboost_datas = collect_data_files("xgboost", includes=["VERSION", "py.typed"])
polars_datas = collect_data_files("polars") + collect_data_files("fastexcel")

a = Analysis(
    [str(scripts_root / "run_packaged.py")],
    pathex=[str(src_root)],
    binaries=xgboost_binaries,
    datas=[
        (str(src_root / "xenix" / "resources"), "xenix/resources"),
        (str(src_root / "xenix" / "translations"), "xenix/translations"),
        (str(src_root / "xenix"), "xenix_worker_source/xenix"),
    ]
    + xgboost_datas
    + polars_datas,
    hiddenimports=[
        "xenix._generated_trial_lock",
        "xenix._generated_trial_llm",
        "xenix.services.agent.chatbot_events",
        "xenix.services.agent.completion_guard",
        "xenix.services.agent.conversation_store",
        "xenix.services.agent.harness_service",
        "xenix.services.agent.lazy_tools",
        "xenix.services.agent.providers",
        "xenix.services.agent.settings",
        "xenix.services.agent.tool_presentations",
        "xenix.services.agent.tools",
        "xenix.services.artifact_service",
        "xenix.services.data_cleaning",
        "xenix.services.data_transform",
        "xenix.services.dataset_service",
        "xenix.services.lazy_ml_service",
        "xenix.services.lazy_services",
        "xenix.services.llm",
        "xenix.services.ml.worker_settings",
        "xenix.services.ml_service",
        "xenix.services.ml_task_service",
        "xenix.services.storage",
        "xenix.services.storage.layout",
        "fastexcel",
        "opentelemetry.exporter.otlp.proto.grpc.trace_exporter",
        "opentelemetry.exporter.otlp.proto.grpc.metric_exporter",
        "opentelemetry.exporter.otlp.proto.grpc._log_exporter",
        "opentelemetry.exporter.otlp.proto.http.trace_exporter",
        "opentelemetry.exporter.otlp.proto.http.metric_exporter",
        "opentelemetry.exporter.otlp.proto.http._log_exporter",
        "polars",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="xenix",
    icon=str(project_root / "logo.ico"),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="xenix",
)
