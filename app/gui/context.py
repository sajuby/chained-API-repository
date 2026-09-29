"""GUI 运行上下文与后台服务工厂。"""

from __future__ import annotations

import os
import sys
import threading
from pathlib import Path
from typing import Callable

from app.core.config import ConfigManager
from app.core.document_service import DocumentService
from app.core.embedder import Embedder
from app.core.llm_client import LLMClient
from app.core.qa_service import QAService
from app.data.database import Database
from app.data.repository import Repository
from app.data.vector_store import VectorStore


class AppContext:
    def __init__(self, config: ConfigManager, database: Database) -> None:
        self.config = config
        self.database = database
        self.vector_store = VectorStore(config.data_dir / "chroma")
        self._embedder: Embedder | None = None
        self._model_lock = threading.Lock()

    def repository(self) -> Repository:
        return Repository(self.database.session())

    def get_embedder(self) -> Embedder:
        if self._embedder is not None:
            return self._embedder
        with self._model_lock:
            if self._embedder is not None:
                return self._embedder
            os.environ["HF_HOME"] = str(self.config.data_dir / ".huggingface")
            local_model = self.config.models_dir / "bge-small-zh-v1.5"
            bundled_model = (
                Path(getattr(sys, "_MEIPASS", "")) / "data" / "models" / "bge-small-zh-v1.5"
                if getattr(sys, "_MEIPASS", None)
                else None
            )
            model_name = Embedder.DEFAULT_MODEL
            if local_model.exists() and any(local_model.iterdir()):
                model_name = str(local_model)
            elif bundled_model and bundled_model.exists() and any(bundled_model.iterdir()):
                model_name = str(bundled_model)
            self._embedder = Embedder(model_name)
            return self._embedder

    def make_document_service(
        self,
        repository: Repository,
        progress: Callable | None = None,
    ) -> DocumentService:
        return DocumentService(
            config=self.config,
            database=self.database,
            repository=repository,
            vector_store=self.vector_store,
            embedder=self.get_embedder(),
            progress=progress,
        )

    def import_files(
        self,
        kb_id: int,
        paths: list[Path],
        progress: Callable,
    ) -> list:
        repo = self.repository()
        try:
            service = self.make_document_service(repo, progress)
            return service.import_files(kb_id, paths)
        finally:
            repo.close()

    def reprocess(self, document_id: int, progress: Callable):
        repo = self.repository()
        try:
            service = self.make_document_service(repo, progress)
            return service.process_document(document_id)
        finally:
            repo.close()

    def delete_document(self, document_id: int) -> None:
        repo = self.repository()
        try:
            doc = repo.get_document(document_id)
            if doc:
                self.vector_store.delete_document(doc.kb_id, doc.id)
                assets = repo.list_media(document_id=doc.id)
                for asset in assets:
                    path = Path(asset.stored_path)
                    if path.exists():
                        try:
                            path.unlink()
                        except OSError:
                            pass
            repo.delete_document(document_id)
        finally:
            repo.close()

    def delete_kb(self, kb_id: int) -> None:
        self.vector_store.delete_kb(kb_id)
        repo = self.repository()
        try:
            repo.delete_kb(kb_id)
        finally:
            repo.close()

    def ask(
        self,
        question: str,
        conversation_id: int,
        progress: Callable | None = None,
    ):
        repo = self.repository()
        try:
            qa = QAService(
                repository=repo,
                vector_store=self.vector_store,
                embedder=None,
                embedder_factory=self.get_embedder,
                llm_client=LLMClient(self.config.config),
            )
            return qa.ask(question, conversation_id)
        finally:
            repo.close()

    def generate_markdown(
        self,
        conversation_id: int,
        target: Path,
        title: str | None = None,
    ):
        from app.core.markdown_service import generate_ai_markdown

        repo = self.repository()
        try:
            llm = LLMClient(self.config.config)
            return generate_ai_markdown(repo, conversation_id, llm, target, title)
        finally:
            repo.close()
