"""本地 OCR 服务。"""

from __future__ import annotations

from pathlib import Path


class OcrService:
    def __init__(self) -> None:
        self._engine = None

    def _get_engine(self):
        if self._engine is None:
            from rapidocr_onnxruntime import RapidOCR

            self._engine = RapidOCR()
        return self._engine

    def recognize(self, image_path: Path) -> str:
        engine = self._get_engine()
        try:
            result, _elapsed = engine(str(image_path))
        except Exception as exc:
            raise RuntimeError(f"OCR 识别失败：{image_path.name}: {exc}") from exc
        if not result:
            return ""
        lines = [str(item[1]).strip() for item in result if len(item) > 1 and item[1]]
        return "\n".join(lines).strip()

