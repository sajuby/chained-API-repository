"""基于 RAG 的知识库问答服务。"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.embedder import Embedder
from app.core.llm_client import LLMClient
from app.data.models import Conversation
from app.data.repository import Repository
from app.data.vector_store import VectorStore


CANNOT_ANSWER = "根据已有文档，无法回答该问题"
SYSTEM_PROMPT = (
    "你是一个严格的本地知识库问答助手。"
    "只依据用户提供的“资料片段”回答问题，不要使用资料之外的知识。"
    "如果资料中没有答案，直接回答“根据已有文档，无法回答该问题”。"
    "答案应简洁准确，并在正文中保留引用标记，例如 [来源：文档名 第X页]。"
)


@dataclass
class QAResult:
    answer: str
    conversation_id: int
    citations: list[dict] = field(default_factory=list)
    contexts: list[str] = field(default_factory=list)


class QAService:
    def __init__(
        self,
        repository: Repository,
        vector_store: VectorStore,
        embedder: Embedder,
        llm_client: LLMClient,
    ) -> None:
        self.repo = repository
        self.vector_store = vector_store
        self.embedder = embedder
        self.llm = llm_client

    def ask(self, question: str, conversation_id: int, stream: bool = False):
        conversation = self.repo.get_conversation(conversation_id)
        if not conversation:
            raise KeyError(f"会话不存在: {conversation_id}")
        self.repo.add_message(conversation_id, "user", question)
        self._ensure_title(conversation, question)
        query_vector = self.embedder.embed([question])[0]
        settings = self.llm.config.retrieval
        rows = self.vector_store.query(
            conversation.kb_id,
            query_vector,
            top_k=settings.top_k,
            threshold=settings.similarity_threshold,
        )
        contexts = [row["text"] for row in rows]
        citations = [
            {
                "document_id": row.get("metadata", {}).get("document_id", ""),
                "filename": row.get("metadata", {}).get("filename", ""),
                "page": row.get("metadata", {}).get("page", ""),
                "source_type": row.get("metadata", {}).get("source_type", "text"),
            }
            for row in rows
        ]
        if not contexts:
            self.repo.add_message(conversation_id, "assistant", CANNOT_ANSWER)
            return QAResult(
                answer=CANNOT_ANSWER,
                conversation_id=conversation_id,
                citations=[],
                contexts=[],
            )

        user_prompt = self._build_user_prompt(question, contexts)
        if stream:
            answer = self._stream_answer(conversation_id, SYSTEM_PROMPT, user_prompt)
        else:
            answer = self.llm.complete(SYSTEM_PROMPT, user_prompt)
            self.repo.add_message(conversation_id, "assistant", answer, citations=citations)
        return QAResult(
            answer=answer,
            conversation_id=conversation_id,
            citations=citations,
            contexts=contexts,
        )

    def _stream_answer(self, conversation_id: int, system: str, user: str) -> str:
        fragments: list[str] = []
        for fragment in self.llm.stream(system, user):
            fragments.append(fragment)
            # GUI 可替换为信号；此处预留回调位置。
        answer = "".join(fragments).strip()
        citations = []
        self.repo.add_message(conversation_id, "assistant", answer, citations=citations)
        return answer

    @staticmethod
    def _build_user_prompt(question: str, contexts: list[str]) -> str:
        numbered = "\n\n".join(
            f"资料 {index}：\n{context}" for index, context in enumerate(contexts, start=1)
        )
        return f"{numbered}\n\n用户问题：{question}"

    def _ensure_title(self, conversation: Conversation, question: str) -> None:
        if conversation.title != "新对话":
            return
        title = question.strip().replace("\n", " ")[:30]
        conversation.title = title
        self.repo.session.commit()
