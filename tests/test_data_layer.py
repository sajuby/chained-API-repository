"""P1 数据层单元测试。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.core.config import AppConfig, ConfigManager
from app.data.database import Database
from app.data.repository import Repository
from app.data.vector_store import VectorStore


class DataLayerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.db = Database(self.root / "app.db")
        self.db.initialize()
        self.repo = Repository(self.db.session())

    def tearDown(self) -> None:
        self.repo.close()
        self.db.close()
        self.temp_dir.cleanup()

    def test_knowledge_base_and_document_crud(self) -> None:
        kb = self.repo.create_kb("课程资料", "机器学习课件")
        self.assertIsNotNone(kb.id)
        doc = self.repo.add_document(
            kb.id,
            "课件.pdf",
            self.root / "doc.pdf",
            "pdf",
            1024,
        )
        self.assertEqual(doc.status, "queued")
        self.repo.set_document_status(doc.id, "success")
        self.assertEqual(self.repo.get_document(doc.id).status, "success")
        self.assertEqual(len(self.repo.list_documents(kb.id)), 1)

    def test_cascade_delete_kb(self) -> None:
        kb = self.repo.create_kb("测试库")
        doc = self.repo.add_document(kb.id, "a.md", self.root / "a.md", "md", 10)
        media = self.repo.add_media(kb.id, doc.id, self.root / "a.png")
        conv = self.repo.create_conversation(kb.id, "会话")
        self.repo.add_message(conv.id, "user", "你好")
        self.assertIsNotNone(media.id)
        self.repo.delete_kb(kb.id)
        self.assertIsNone(self.repo.get_kb(kb.id))
        self.assertEqual(len(self.repo.list_documents(kb.id)), 0)

    def test_config_persistence(self) -> None:
        config = ConfigManager(self.root)
        config.config.deepseek_model = "deepseek-chat"
        config.config.retrieval.top_k = 4
        config.save()
        reloaded = ConfigManager(self.root)
        self.assertEqual(reloaded.config.retrieval.top_k, 4)

    def test_ai_provider_switching(self) -> None:
        config = ConfigManager(self.root)
        config.config.provider_id = "openai"
        config.config.provider_name = "OpenAI"
        config.config.model_name = "gpt-4o-mini"
        config.config.deepseek_base_url = "https://api.openai.com/v1"
        config.config.provider_api_keys = {"openai": "sk-test"}
        config.save()
        reloaded = ConfigManager(self.root)
        base_url, api_key, model, name = reloaded.config.provider_config()
        self.assertEqual(base_url, "https://api.openai.com/v1")
        self.assertEqual(api_key, "sk-test")
        self.assertEqual(model, "gpt-4o-mini")
        self.assertIn("OpenAI", reloaded.config.display_model_name)
        self.assertTrue(reloaded.config.is_llm_configured())


class VectorStoreTests(unittest.TestCase):
    def test_chroma_add_and_query(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            store = VectorStore(Path(folder))
            try:
                store.add(
                    kb_id=1,
                    ids=["1", "2"],
                    embeddings=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
                    texts=["机器学习基础", "项目管理流程"],
                    metadatas=[{"document_id": "10"}, {"document_id": "11"}],
                )
                result = store.query(
                    kb_id=1,
                    embedding=[1.0, 0.0, 0.0],
                    top_k=2,
                    threshold=0.2,
                )
                self.assertTrue(result)
                self.assertIn("机器学习", result[0]["text"])
                store.delete_kb(1)
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
