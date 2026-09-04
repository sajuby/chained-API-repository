"""文档导入与入库服务。"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PIL import Image

from app.core.document_parser import DocumentParser, ParsedDocument
from app.core.embedder import Embedder
from app.core.image_processor import ExtractedImage, ImageProcessor
from app.core.ocr_service import OcrService
from app.core.text_splitter import RecursiveTextSplitter
from app.data.database import Database
from app.data.models import Document, MediaAsset
from app.data.repository import Repository
from app.data.vector_store import VectorStore


ProgressCallback = Callable[[str, int, int], None]
OcrLike = Callable[[Path], str]


@dataclass
class ProcessingProgress:
    step: str = ""
    index: int = 0
    total: int = 1


class DocumentService:
    def __init__(
        self,
        config,
        database: Database,
        repository: Repository,
        vector_store: VectorStore,
        embedder: Embedder | None = None,
        ocr: OcrLike | OcrService | None = None,
        progress: ProgressCallback | None = None,
    ) -> None:
        self.config = config
        self.database = database
        self.repo = repository
        self.vector_store = vector_store
        self.embedder = embedder
        self.parser = DocumentParser()
        self.image_processor = ImageProcessor()
        self.ocr = ocr or OcrService()
        self.progress = progress or (lambda _step, _index, _total: None)

    def import_files(
        self,
        kb_id: int,
        file_paths: list[Path],
        include_images: bool = True,
    ) -> list[Document]:
        documents: list[Document] = []
        self.progress("准备导入", 0, len(file_paths))
        for index, source in enumerate(file_paths, start=1):
            self.progress(f"复制 {source.name}", index, len(file_paths))
            target = self._copy_into_kb(kb_id, source)
            doc = self.repo.add_document(
                kb_id=kb_id,
                filename=source.name,
                file_path=target,
                file_type=source.suffix.lower().lstrip("."),
                file_size=source.stat().st_size,
            )
            try:
                self.process_document(doc.id, include_images=include_images)
                documents.append(doc)
            except Exception as exc:
                self.repo.set_document_status(doc.id, "failed", str(exc))
                raise
        return documents

    def process_document(self, document_id: int, include_images: bool = True) -> Document:
        doc = self.repo.get_document(document_id)
        if not doc:
            raise KeyError(f"文档不存在: {document_id}")

        self.repo.set_document_status(doc.id, "processing")
        try:
            path = Path(doc.file_path)
            direct_image = path.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
            parsed = (
                ParsedDocument(filename=path.name, pages=[])
                if direct_image
                else self.parser.parse(path)
            )
            doc = self.repo.get_document(document_id)
            doc.page_count = 1 if direct_image else len(parsed.pages)
            self.repo.session.commit()

            self._remove_old_vectors(doc)
            image_contexts: list[str] = []
            if direct_image:
                image_contexts = self._process_direct_image(doc)
            elif include_images:
                image_contexts = self._process_images(doc, parsed)

            chunks = self._build_chunks(doc, parsed, image_contexts)
            self.progress("向量化", 0, max(len(chunks), 1))
            self._index_chunks(doc, chunks)
            return self.repo.set_document_status(doc.id, "success")
        except Exception as exc:
            self.repo.set_document_status(doc.id, "failed", str(exc))
            raise

    def _copy_into_kb(self, kb_id: int, source: Path) -> Path:
        if source.suffix.lower() not in {".pdf", ".docx", ".pptx", ".txt", ".md", ".jpg", ".jpeg", ".png", ".bmp", ".webp"}:
            raise ValueError(f"不支持的文件类型: {source.suffix}")
        kb_dir = self.config.documents_dir / f"kb_{kb_id}"
        kb_dir.mkdir(parents=True, exist_ok=True)
        candidate = kb_dir / source.name
        counter = 1
        while candidate.exists():
            candidate = kb_dir / f"{source.stem}_{counter}{source.suffix}"
            counter += 1
        shutil.copy2(source, candidate)
        return candidate

    def _remove_old_vectors(self, doc: Document) -> None:
        self.vector_store.delete_document(doc.kb_id, doc.id)
        assets = self.repo.list_media(document_id=doc.id)
        for asset in assets:
            path = Path(asset.stored_path)
            if path.exists():
                try:
                    path.unlink()
                except OSError:
                    pass
            # 直接删除 DB 行，避免重处理时残留。
            self.repo.session.delete(asset)
        self.repo.session.commit()

    def _process_images(self, doc: Document, parsed: ParsedDocument) -> list[str]:
        media_root = self.config.media_dir / f"kb_{doc.kb_id}"
        media_root.mkdir(parents=True, exist_ok=True)
        extracted = self.image_processor.extract(
            Path(doc.file_path),
            media_root,
            str(doc.id),
            [page.text for page in parsed.pages],
        )
        contexts: list[str] = []
        for index, image in enumerate(extracted, start=1):
            self.progress(f"OCR {image.original_name}", index, len(extracted))
            asset = self.repo.add_media(
                kb_id=doc.kb_id,
                document_id=doc.id,
                stored_path=image.source_path,
                original_name=image.original_name,
                asset_type="embedded",
                page_number=image.page_number,
                figure_index=image.figure_index or index,
                caption=image.caption,
                width=image.width,
                height=image.height,
            )
            ocr_text = ""
            description = ""
            try:
                ocr_text = self._run_ocr(image.source_path)
                if ocr_text:
                    asset.ocr_text = ocr_text
                    asset.status = "success"
                    self.repo.session.commit()
            except Exception as exc:
                asset.error_message = str(exc)
                asset.status = "failed"
                self.repo.session.commit()
            if ocr_text or description:
                contexts.append(
                    self._image_context_text(doc, image, ocr_text, description)
                )
        return contexts

    def _process_direct_image(self, doc: Document) -> list[str]:
        image_path = Path(doc.file_path)
        self.progress("OCR 图片资料", 1, 1)
        asset = self.repo.add_media(
            kb_id=doc.kb_id,
            document_id=doc.id,
            stored_path=image_path,
            original_name=doc.filename,
            asset_type="uploaded",
            page_number=1,
            figure_index=1,
        )
        try:
            with Image.open(image_path) as image:
                asset.width, asset.height = image.size
        except Exception:
            pass
        ocr_text = ""
        try:
            ocr_text = self._run_ocr(image_path)
            asset.ocr_text = ocr_text
            asset.status = "success"
        except Exception as exc:
            asset.error_message = str(exc)
            asset.status = "failed"
        self.repo.session.commit()
        if not ocr_text:
            return []
        return [
            (
                f"【图片资料：{doc.filename}】\n"
                f"图片文字：{ocr_text}"
            )
        ]

    def _run_ocr(self, image_path: Path) -> str:
        if callable(self.ocr) and not isinstance(self.ocr, OcrService):
            return self.ocr(image_path)
        return self.ocr.recognize(image_path)

    @staticmethod
    def _image_context_text(
        doc: Document,
        image: ExtractedImage,
        ocr_text: str,
        description: str,
    ) -> str:
        page = f"第{image.page_number}页" if image.page_number else "未知页"
        figure = f"图{image.figure_index}" if image.figure_index else "图片"
        parts = [f"【{doc.filename} {page} {figure}】"]
        if image.caption:
            parts.append(f"图题：{image.caption}")
        if ocr_text:
            parts.append(f"图片文字：{ocr_text}")
        if description:
            parts.append(f"图片描述：{description}")
        return "\n".join(parts)

    def _build_chunks(
        self,
        doc: Document,
        parsed: ParsedDocument,
        image_contexts: list[str],
    ) -> list[tuple[str, dict]]:
        splitter = RecursiveTextSplitter(
            chunk_size=self.config.config.retrieval.chunk_size,
            chunk_overlap=self.config.config.retrieval.chunk_overlap,
        )
        chunks: list[tuple[str, dict]] = []
        for page in parsed.pages:
            page_text = page.text.strip()
            if not page_text:
                continue
            for text in splitter.split_text(page_text):
                chunks.append(
                    (
                        text,
                        {
                            "document_id": str(doc.id),
                            "filename": doc.filename,
                            "page": page.page_number,
                            "source_type": "text",
                        },
                    )
                )
        for index, context in enumerate(image_contexts, start=1):
            chunks.append(
                (
                    context,
                    {
                        "document_id": str(doc.id),
                        "filename": doc.filename,
                        "source_type": "image",
                        "image_index": str(index),
                    },
                )
            )
        return chunks

    def _index_chunks(
        self,
        doc: Document,
        chunks: list[tuple[str, dict]],
    ) -> None:
        if not chunks:
            return
        if not self.embedder:
            raise RuntimeError("未配置嵌入模型，无法向量化文档。")
        batch_size = 32
        total = len(chunks)
        for start in range(0, total, batch_size):
            batch = chunks[start : start + batch_size]
            texts = [chunk[0] for chunk in batch]
            metadatas = [chunk[1] for chunk in batch]
            vectors = self.embedder.embed(texts)
            if len(vectors) != len(batch):
                raise RuntimeError("嵌入结果数量与文本块不一致。")
            ids = [
                f"doc{doc.id}_{'img' if meta.get('source_type') == 'image' else 'text'}_{start + index}"
                for index, (_text, meta) in enumerate(batch)
            ]
            self.vector_store.add(
                kb_id=doc.kb_id,
                ids=ids,
                embeddings=vectors,
                texts=texts,
                metadatas=metadatas,
            )
            self.progress("向量化", min(start + len(batch), total), total)
