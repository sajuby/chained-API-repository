"""Markdown 导出与生成服务。"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from app.data.models import MarkdownExport
from app.data.repository import Repository


def _safe_filename(title: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]', "_", title).strip()
    return cleaned or "对话记录"


def export_conversation(
    repository: Repository,
    conversation_id: int,
    target: Path,
) -> Path:
    conversation = repository.get_conversation(conversation_id)
    if not conversation:
        raise KeyError("会话不存在。")
    kb = repository.get_kb(conversation.kb_id)
    kb_name = kb.name if kb else ""
    messages = repository.list_messages(conversation_id)
    if not messages:
        raise ValueError("当前会话没有可导出的内容。")

    lines = [
        "---",
        f"title: {conversation.title or '对话记录'}",
        f"knowledge_base: {kb_name}",
        f"created_at: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "---",
        "",
        "# 对话记录",
        "",
    ]
    for message in messages:
        prefix = "问" if message.role == "user" else "答"
        lines.append(f"## {prefix}：{message.content}")
        lines.append("")
        lines.append(message.markdown_content or message.content)
        lines.append("")

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines), encoding="utf-8")
    export = MarkdownExport(
        kb_id=conversation.kb_id,
        conversation_id=conversation.id,
        export_type="conversation",
        title=conversation.title,
        file_path=str(target),
        status="success",
    )
    repository.session.add(export)
    repository.session.commit()
    return target


def generate_summary_markdown(
    repository: Repository,
    conversation_id: int,
    title: str,
    summary: str,
    target: Path,
) -> Path:
    conversation = repository.get_conversation(conversation_id)
    if not conversation:
        raise KeyError("会话不存在。")
    kb = repository.get_kb(conversation.kb_id)
    content = [
        "---",
        f"title: {title}",
        f"knowledge_base: {kb.name if kb else ''}",
        f"created_at: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "---",
        "",
        f"# {title}",
        "",
        summary,
        "",
    ]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(content), encoding="utf-8")
    return target


def generate_ai_markdown(
    repository: Repository,
    conversation_id: int,
    llm_client,
    target: Path,
    title: str | None = None,
) -> Path:
    conversation = repository.get_conversation(conversation_id)
    if not conversation:
        raise KeyError("会话不存在。")
    kb = repository.get_kb(conversation.kb_id)
    messages = repository.list_messages(conversation_id)
    if not messages:
        raise ValueError("当前会话没有内容可生成。")
    document_title = title or conversation.title or "对话整理"
    transcript = "\n\n".join(
        f"【{message.role}】{message.content}" for message in messages
    )
    system = (
        "你是一个知识文档整理助手。请仅根据提供的对话内容生成一份规范的中文 Markdown 文档。"
        "文档必须包含 YAML 元信息后的正文，正文结构建议包含：摘要、核心问题、要点整理、可复用结论。"
        "不得补充对话中不存在的事实，保留与资料相关的页码或文件名引用。"
    )
    user = f"文档标题：{document_title}\n\n对话内容：\n{transcript}"
    body = llm_client.complete(system, user)
    content = [
        "---",
        f"title: {document_title}",
        f"knowledge_base: {kb.name if kb else ''}",
        f"created_at: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "---",
        "",
        body,
        "",
    ]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(content), encoding="utf-8")
    export = MarkdownExport(
        kb_id=conversation.kb_id,
        conversation_id=conversation.id,
        export_type="ai_summary",
        title=document_title,
        file_path=str(target),
        status="success",
    )
    repository.session.add(export)
    repository.session.commit()
    return target
