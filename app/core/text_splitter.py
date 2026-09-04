"""文本分块工具。"""

from __future__ import annotations

import re


def estimate_tokens(text: str) -> int:
    """中文按约 1.5 字符/token，英文按 4 字符/token 估算。"""
    chinese = len(re.findall(r"[\u4e00-\u9fff]", text))
    others = len(text) - chinese
    return max(1, round(chinese / 1.5 + others / 4))


class RecursiveTextSplitter:
    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        separators: tuple[str, ...] | None = None,
    ) -> None:
        self.chunk_size = max(50, chunk_size)
        self.chunk_overlap = max(0, min(chunk_overlap, self.chunk_size // 2))
        self.separators = separators or (
            "\n\n",
            "\n",
            "。",
            "；",
            "，",
            " ",
        )

    def split_text(self, text: str) -> list[str]:
        text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
        if not text:
            return []
        chunks: list[str] = []
        current = ""
        for paragraph in self._split_recursive(text):
            candidate = paragraph if not current else current + paragraph
            if estimate_tokens(candidate) <= self.chunk_size:
                current = candidate
                continue
            if current:
                chunks.append(current.strip())
            if estimate_tokens(paragraph) <= self.chunk_size:
                current = paragraph
            else:
                start = 0
                while start < len(paragraph):
                    end = self._find_end(paragraph, start)
                    chunk = paragraph[start:end]
                    if chunk:
                        chunks.append(chunk.strip())
                    next_start = max(end - self._overlap_chars(paragraph[start:end]), end)
                    start = next_start
                    if start >= len(paragraph):
                        break
                current = ""
        if current.strip():
            chunks.append(current.strip())
        return [c for c in chunks if c]

    def _split_recursive(self, text: str) -> list[str]:
        if estimate_tokens(text) <= self.chunk_size or not self.separators:
            return [text]
        separator = next((s for s in self.separators if s in text), None)
        if separator is None:
            return [text]
        pieces = [p for p in text.split(separator) if p]
        parts: list[str] = []
        for piece in pieces:
            if estimate_tokens(piece) <= self.chunk_size:
                parts.append(piece + separator)
            else:
                parts.extend(self._split_recursive(piece))
        return parts

    def _find_end(self, text: str, start: int) -> int:
        target = min(len(text), start + max(120, round(self.chunk_size * 1.8)))
        window = text[start:target]
        for separator in self.separators:
            index = window.rfind(separator)
            if index > 0:
                return start + index + len(separator)
        return target

    def _overlap_chars(self, chunk: str) -> int:
        if self.chunk_overlap == 0 or not chunk:
            return 0
        tokens = estimate_tokens(chunk)
        return max(20, round(len(chunk) * self.chunk_overlap / max(tokens, 1)))

