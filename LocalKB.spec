# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
from PyInstaller.utils.hooks import collect_all


PROJECT_ROOT = Path(SPECPATH)
model_data = [
    (str(PROJECT_ROOT / "data" / "models" / "bge-small-zh-v1.5"), "data/models/bge-small-zh-v1.5")
]

datas = list(model_data)
binaries = []
hiddenimports = []
for package in [
    "chromadb",
    "sentence_transformers",
    "transformers",
    "tokenizers",
    "rapidocr_onnxruntime",
    "pdfplumber",
    "pymupdf",
    "docx",
    "pptx",
    "PIL",
    "openai",
    "markdown",
]:
    package_datas, package_binaries, package_hidden = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hidden

hiddenimports += [
    "sqlalchemy.dialects.sqlite",
    "chromadb.api.segment",
    "chromadb.api.models.Collection",
]

a = Analysis(
    ["main.py"],
    pathex=[str(PROJECT_ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="本地文档知识库桌面助手",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="本地文档知识库桌面助手",
)
