"""可选 OpenAI 兼容视觉模型服务。"""

from __future__ import annotations

import base64
from pathlib import Path

import requests

from app.core.config import VisionSettings


class VisionService:
    def __init__(self, settings: VisionSettings) -> None:
        self.settings = settings

    def describe(self, image_path: Path, question: str = "请描述这张图片的主要内容。") -> str:
        if not self.settings.enabled or not self.settings.send_images:
            raise RuntimeError("视觉理解未启用或未允许发送图片。")
        if not self.settings.api_key or not self.settings.model:
            raise RuntimeError("视觉模型配置不完整。")
        encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
        payload = {
            "model": self.settings.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": question},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/{image_path.suffix.lstrip('.').lower()};base64,{encoded}"
                            },
                        },
                    ],
                }
            ],
            "temperature": 0,
        }
        url = (self.settings.api_base or "").rstrip("/") + "/chat/completions"
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {self.settings.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=90,
        )
        response.raise_for_status()
        try:
            return response.json()["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError) as exc:
            raise RuntimeError("视觉模型返回内容异常。") from exc

