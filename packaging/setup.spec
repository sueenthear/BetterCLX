from pathlib import Path

project_root = Path(SPECPATH)
if not (project_root / "setup.py").is_file():
    project_root = project_root / "packaging"
payload_root = project_root / "payload"
datas = [(str(payload_root), "payload")]

analysis = Analysis(
    [str(project_root / "setup.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(analysis.pure, analysis.zipped_data)
exe = EXE(
    pyz,
    analysis.scripts,
    analysis.binaries,
    analysis.datas,
    [],
    name="BetterCLX-Setup",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(project_root.parent / "icon.ico"),
)
