# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ["src/xenix/main.py"],
    pathex=["src"],
    binaries=[],
    datas=[("src/xenix/resources", "xenix/resources")],
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
    a.binaries,
    a.datas,
    [],
    name="xenix",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
