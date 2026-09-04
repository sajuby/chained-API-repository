"""P3 问答服务单元测试。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.core.config import AppConfig, ConfigManager
from app.core.document_service import DocumentService
from app.core.embedder import HashEmbedder
from app.core.llm_client import LLMNotConfigured
from app.core.qa_service import CANNOT_ANSWER, QAService
from app.data.database import Database
from app.data.repository import Repository
from app.data.vector_store import VectorStore


class FakeLLM:
    def __init__(self, answer: str = "这是基于资料的答案。") -> None:
        self.config = AppConfig()
        self.config.retrieval.similarity_threshold = 0.001
        self.answer = answer
        self.calls = 0

    def complete(self, _system: str, _user: str) -> str:
        self.calls += 1
        return self.answer


class QAServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.config = ConfigManager(self.root)
        self.db = Database(self.root / "app.db")
        self.db.initialize()
        self.repo = Repository(self.db.session())
        self.vector_store = VectorStore(self.root / "chroma")
        self.embedder = HashEmbedder()

    def tearDown(self) -> None:
        self.vector_store.close()
        self.repo.close()
        self.db.close()
        self.temp_dir.cleanup()

    def _load_kb(self) -> int:
        kb = self.repo.create_kb("问答测试库")
        source = self.root / "资料.md"
        source.write_text(
            "反向传播用于计算神经网络中的梯度。\n学习率影响参数更新步长。",
            encoding="utf-8",
        )
        service = DocumentService(
            config=self.config,
            database=self.db,
            repository=self.repo,
            vector_store=self.vector_store,
            embedder=self.embedder,
            ocr=lambda _path: "",
        )
        service.import_files(kb.id, [source])
        return kb.id

    def test_answer_uses_context_and_persists_messages(self) -> None:
        kb_id = self._load_kb()
        conversation = self.repo.create_conversation(kb_id, "新对话")
        fake = FakeLLM("答案是反向传播算法。")
        qa = QAService(self.repo, self.vector_store, self.embedder, fake)

        result = qa.ask("反向传播是什么？", conversation.id)
        self.assertIn("反向传播算法", result.answer)
        self.assertEqual(fake.calls, 1)
        messages = self.repo.list_messages(conversation.id)
        self.assertEqual([message.role for message in messages], ["user", "assistant"])
        self.assertNotEqual(self.repo.get_conversation(conversation.id).title, "新对话")

    def test_cannot_answer_when_no_context(self) -> None:
        kb_id = self.repo.create_kb("空库").id
        conversation = self.repo.create_conversation(kb_id)
        fake = FakeLLM()
        qa = QAService(self.repo, self.vector_store, self.embedder, fake)
        result = qa.ask("完全不相关的问题", conversation.id)
        self.assertEqual(result.answer, CANNOT_ANSWER)
        self.assertEqual(fake.calls, 0)


if __name__ == "__main__":
    unittest.main()

