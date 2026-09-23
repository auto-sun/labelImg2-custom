# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller one-folder build for the offline Windows installer."""
from pathlib import Path

from PyInstaller.utils.hooks import collect_all


project_root = Path.cwd().resolve()
icon_path = project_root / 'build' / 'LabelImg2Custom.ico'
if not icon_path.is_file():
    raise FileNotFoundError(
        'Generate build/LabelImg2Custom.ico with packaging/create_icon.py first.')

ultralytics_data, ultralytics_binaries, ultralytics_imports = collect_all(
    'ultralytics')

project_data = [
    (str(project_root / 'img'), 'img'),
    (str(project_root / 'data'), 'data'),
]
for name in (
        'LICENSE', 'LICENSE-MIT-UPSTREAM', 'NOTICE.md',
        'NOTICE_zh-CN.md', 'MODIFICATIONS.md',
        'MODIFICATIONS_zh-CN.md', 'README.md',
        'FIRST_USE_GUIDE_zh-CN.md'):
    project_data.append((str(project_root / name), '.'))

a = Analysis(
    [str(project_root / 'labelImg.py')],
    pathex=[str(project_root)],
    binaries=ultralytics_binaries,
    datas=project_data + ultralytics_data,
    hiddenimports=ultralytics_imports + [
        'PyQt5.QtSvg', 'pypinyin', 'send2trash', 'yamlloader'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PySide2', 'PySide6', 'PyQt6', 'tensorflow', 'jax'],
    noarchive=False,
)

pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='LabelImg2Custom',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(icon_path),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name='LabelImg2Custom',
)
