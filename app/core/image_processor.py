"""文档嵌入图片提取。"""

from __future__ import annotations

import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image


@dataclass
class ExtractedImage:
    source_path: Path
    original_name: str
    page_number: int | None = None
    figure_index: int | None = None
    caption: str = ""
    width: int | None = None
    height: int | None = None


class ImageProcessor:
    """从 PDF/DOCX/PPTX 中提取图片并保存到媒体目录。"""

    def extract(
        self,
        file_path: Path,
        media_root: Path,
        document_key: str,
        page_texts: list[str] | None = None,
    ) -> list[ExtractedImage]:
        suffix = file_path.suffix.lower()
        media_dir = media_root / document_key
        media_dir.mkdir(parents=True, exist_ok=True)
        if suffix == ".pdf":
            return self._extract_pdf(file_path, media_dir, page_texts or [])
        if suffix in {".docx", ".pptx"}:
            return self._extract_zip(file_path, media_dir, suffix)
        return []

    def _extract_pdf(
        self,
        file_path: Path,
        media_dir: Path,
        page_texts: list[str],
    ) -> list[ExtractedImage]:
        import pymupdf

        images: list[ExtractedImage] = []
        figure_count = 0
        with pymupdf.open(file_path) as doc:
            for page_number, page in enumerate(doc, start=1):
                page_images = page.get_images(full=True)
                for item in page_images:
                    xref = item[0]
                    try:
                        info = doc.extract_image(xref)
                    except Exception:
                        continue
                    ext = info.get("ext", "png")
                    if ext not in {"png", "jpg", "jpeg", "webp", "bmp"}:
                        ext = "png"
                    figure_count += 1
                    filename = f"p{page_number:03d}_img{figure_count:03d}.{ext}"
                    target = media_dir / filename
                    target.write_bytes(info.get("image", b""))
                    caption = self._find_caption(page_texts[page_number - 1] if page_texts else "", figure_count)
                    width = info.get("width")
                    height = info.get("height")
                    images.append(
                        ExtractedImage(
                            source_path=target,
                            original_name=filename,
                            page_number=page_number,
                            figure_index=figure_count,
                            caption=caption,
                            width=width,
                            height=height,
                        )
                    )
        return images

    def _extract_zip(
        self,
        file_path: Path,
        media_dir: Path,
        suffix: str,
    ) -> list[ExtractedImage]:
        images: list[ExtractedImage] = []
        try:
            with zipfile.ZipFile(file_path) as archive:
                names = sorted(name for name in archive.namelist() if self._is_media_name(name, suffix))
                for index, name in enumerate(names, start=1):
                    target = media_dir / f"{index:04d}_{Path(name).name}"
                    with archive.open(name) as source, open(target, "wb") as dest:
                        shutil.copyfileobj(source, dest)
                    try:
                        with Image.open(target) as image:
                            width, height = image.size
                    except Exception:
                        width, height = None, None
                    images.append(
                        ExtractedImage(
                            source_path=target,
                            original_name=Path(name).name,
                            page_number=1,
                            figure_index=index,
                            width=width,
                            height=height,
                        )
                    )
        except zipfile.BadZipFile:
            pass
        return images

    @staticmethod
    def _is_media_name(name: str, suffix: str) -> bool:
        lowered = name.lower()
        if suffix == ".docx":
            return lowered.startswith("word/media/") and not lowered.endswith((".xml", ".rels"))
        if suffix == ".pptx":
            return lowered.startswith("ppt/media/") and not lowered.endswith((".xml", ".rels"))
        return False

    @staticmethod
    def _find_caption(page_text: str, figure_index: int) -> str:
        if not page_text:
            return ""
        markers = (f"图{figure_index}：", f"图{figure_index}:", f"Figure {figure_index}")
        for marker in markers:
            if marker in page_text:
                index = page_text.index(marker)
                return page_text[index : index + 160]
        return ""
