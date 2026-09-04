"""P5 Markdown 导出测试。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.core.config import ConfigManager
from app.core.markdown_service import export_conversation
from app.data.database import Database
from app.data.repository import Repository


class MarkdownServiceTests(unittest.TestCase):
    def test_export_conversation(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            database = Database(root / "app.db")
            database.initialize()
            repo = Repository(database.session())
            try:
                kb = repo.create_kb("课程知识库")
                conversation = repo.create_conversation(kb.id, "反向传播问答")
                repo.add_message(conversation.id, "user", "什么是反向传播？")
                repo.add_message(
                    conversation.id,
                    "assistant",
                    "反向传播用于计算梯度。\n[来源：课件.pdf 第12页]",
                )
                target = root / "导出" / "反向传播问答.md"
                result = export_conversation(repo, conversation.id, target)
                self.assertTrue(result.exists())
                text = result.read_text(encoding="utf-8")
                self.assertIn("knowledge_base: 课程知识库", text)
                self.assertIn("什么是反向传播", text)
                self.assertIn("第12页", text)
            finally:
                repo.close()
                database.close()


if __name__ == "__main__":
    unittest.main()

