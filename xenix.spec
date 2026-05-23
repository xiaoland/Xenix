# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


project_root = Path.cwd()
src_root = project_root / "src"
scripts_root = project_root / "scripts"

a = Analysis(
    [str(scripts_root / "run_dev.py")],
    pathex=[str(src_root)],
    binaries=[],
    datas=[
        (str(src_root / "xenix" / "resources"), "xenix/resources"),
        (str(src_root / "xenix" / "translations"), "xenix/translations"),
        (str(src_root / "xenix"), "xenix_worker_source/xenix"),
    ],
    hiddenimports=[],
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
