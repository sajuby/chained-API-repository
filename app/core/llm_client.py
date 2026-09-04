"""OpenAI 兼容大模型客户端，默认对接 DeepSeek。"""

from __future__ import annotations

import json
from typing import Iterator

import requests

from app.core.config import AppConfig


class LLMNotConfigured(RuntimeError):
    pass


class LLMClient:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    @property
    def base_url(self) -> str:
        base_url, _key, _model, _name = self.config.provider_config()
        return (base_url or "https://api.deepseek.com").rstrip("/")

    def _headers(self) -> dict:
        _base_url, key, _model, _name = self.config.provider_config()
        if not key:
            raise LLMNotConfigured("尚未配置当前 AI 的 API Key，请在设置中填写。")
        return {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }

    def _payload(self, system: str, user: str) -> dict:
        _base_url, _key, model, _name = self.config.provider_config()
        return {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0,
            "stream": False,
        }

    def complete(self, system: str, user: str, timeout: int = 90) -> str:
        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers=self._headers(),
            json=self._payload(system, user),
            timeout=timeout,
        )
        if response.status_code == 401:
            raise LLMNotConfigured("API Key 无效或已过期。")
        if response.status_code >= 400:
            detail = response.text[:300] if response.text else response.reason
            raise RuntimeError(f"AI 请求失败（{response.status_code}）：{detail}")
        data = response.json()
        try:
            return data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("大模型返回内容格式异常。") from exc

    def stream(
        self,
        system: str,
        user: str,
        timeout: int = 90,
    ) -> Iterator[str]:
        payload = self._payload(system, user)
        payload["stream"] = True
        with requests.post(
            f"{self.base_url}/chat/completions",
            headers=self._headers(),
            json=payload,
            stream=True,
            timeout=timeout,
        ) as response:
            if response.status_code == 401:
                raise LLMNotConfigured("API Key 无效或已过期。")
            response.raise_for_status()
            for raw_line in response.iter_lines(decode_unicode=True):
                if not raw_line or not raw_line.startswith("data:"):
                    continue
                data = raw_line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    delta = json.loads(data)["choices"][0]["delta"].get("content") or ""
                except (KeyError, IndexError, json.JSONDecodeError):
                    continue
                if delta:
                    yield delta
