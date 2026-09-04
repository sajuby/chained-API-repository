"""真实 bge 模型端到端冒烟：文档导入 → 语义检索 → 问答上下文。"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import AppConfig, ConfigManager
from app.core.document_service import DocumentService
from app.core.embedder import Embedder
from app.data.database import Database
from app.data.repository import Repository
from app.data.vector_store import VectorStore


class FakeLLM:
    def __init__(self) -> None:
        self.config = AppConfig()

    def complete(self, _system: str, _user: str) -> str:
        return "反向传播用于计算梯度。"


def main() -> int:
    from app.core.qa_service import QAService

    root = Path(__file__).resolve().parents[1] / "data" / "_e2e_smoke"
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    config = ConfigManager(root)
    database = Database(root / "app.db")
    database.initialize()
    store = VectorStore(root / "chroma")
    repo = Repository(database.session())
    try:
        model_path = Path(__file__).resolve().parents[1] / "data" / "models" / "bge-small-zh-v1.5"
        embedder = Embedder(model_path)
        kb = repo.create_kb("端到端测试")
        source = root / "机器学习.md"
        source.write_text(
            "反向传播算法通过链式法则计算损失函数对权重的梯度。\n"
            "学习率决定每次参数更新的步长。",
            encoding="utf-8",
        )
        service = DocumentService(
            config=config,
            database=database,
            repository=repo,
            vector_store=store,
            embedder=embedder,
            ocr=lambda _path: "",
        )
        doc = service.import_files(kb.id, [source])[0]
        conversation = repo.create_conversation(kb.id)
        qa = QAService(repo, store, embedder, FakeLLM())
        result = qa.ask("反向传播如何计算梯度？", conversation.id)
        print(f"文档状态: {doc.status}")
        print(f"命中片段: {len(result.contexts)}")
        print(f"回答: {result.answer}")
        if doc.status != "success" or not result.contexts:
            raise RuntimeError("端到端冒烟失败")
        return 0
    finally:
        repo.close()
        store.close()
        database.close()
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
