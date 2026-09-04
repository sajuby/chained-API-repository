"""跨平台数据与资源路径。"""

from __future__ import annotations

import os
import sys
from pathlib import Path


PROJECT_ROOT = (
    Path(sys.executable).resolve().parent
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parents[2]
)
STORAGE_OVERRIDE_FILE = PROJECT_ROOT / ".local-kb-storage-path"


def configured_data_dir() -> Path | None:
    if STORAGE_OVERRIDE_FILE.exists():
        try:
            raw = STORAGE_OVERRIDE_FILE.read_text(encoding="utf-8").strip()
            if raw:
                return Path(raw)
        except OSError:
            pass
    return None


def user_data_dir() -> Path:
    """返回按平台划分的本地数据根目录。"""
    override = os.environ.get("LOCAL_KB_DATA_DIR")
    if override:
        root = Path(override)
    elif sys.platform == "win32":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        root = root / "LocalKnowledgeBase"
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support" / "LocalKnowledgeBase"
    else:
        root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
        root = root / "LocalKnowledgeBase"
    root.mkdir(parents=True, exist_ok=True)
    return root


def ensure_subdir(base: Path, name: str) -> Path:
    target = base / name
    target.mkdir(parents=True, exist_ok=True)
    return target


def resource_dir() -> Path:
    """打包后也能正确找到资源目录。"""
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[2]
