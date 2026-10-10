# PyInstaller onedir build for Better CLX
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files

project_root = Path(SPECPATH).parent
# PyInstaller's official PySide6 hooks collect imported Qt modules; avoid
# collecting every optional Qt/qfluentwidgets submodule into the onedir build.
hiddenimports = []
datas = collect_data_files("qfluentwidgets") + [
    (str(project_root / "icon.ico"), "."),
    (str(project_root / "Background.jpg"), "."),
    (str(project_root / "combo"), "examples/combo"),
]

block_cipher = None

a = Analysis(
    [str(project_root / "better_clx" / "main.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter"],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="BetterCLX",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(project_root / "icon.ico"),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="BetterCLX",
)
