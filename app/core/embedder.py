"""文本嵌入服务。"""

from __future__ import annotations

import hashlib
from pathlib import Path


class Embedder:
    """基于 sentence-transformers 的本地嵌入模型。"""

    DEFAULT_MODEL = "BAAI/bge-small-zh-v1.5"

    def __init__(self, model_path: Path | str | None = None) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("未安装 sentence-transformers，无法生成向量。") from exc
        self.model = SentenceTransformer(str(model_path or self.DEFAULT_MODEL))
        getter = getattr(self.model, "get_embedding_dimension", None)
        if getter is None:
            getter = self.model.get_sentence_embedding_dimension
        self.dimension = int(getter())

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = self.model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return vectors.tolist()


class HashEmbedder:
    """确定性测试用嵌入器：可稳定执行但不能表达语义。"""

    DIMENSION = 32

    def __init__(self, dimension: int = DIMENSION) -> None:
        self.dimension = dimension

    def embed(self, texts: list[str]) -> list[list[float]]:
        result: list[list[float]] = []
        for text in texts:
            vector = [0.0] * self.dimension
            for token in text:
                digest = hashlib.sha256(token.encode("utf-8")).digest()
                index = int.from_bytes(digest[:2], "big") % self.dimension
                vector[index] += 1.0
            total = sum(vector) or 1.0
            normalized = [round(value / total, 8) for value in vector]
            result.append(normalized)
        return result
