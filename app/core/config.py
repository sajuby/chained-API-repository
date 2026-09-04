"""应用配置与本地数据目录管理。"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

from app.utils.paths import ensure_subdir, user_data_dir


AI_PROVIDERS = {
    "deepseek": {
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-chat",
        "tiers": [
            {"id": "flash", "name": "Flash", "model": "deepseek-chat"},
            {"id": "pro", "name": "Pro", "model": "deepseek-reasoner"},
        ],
    },
    "openai": {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "tiers": [
            {"id": "flash", "name": "Flash", "model": "gpt-4o-mini"},
            {"id": "pro", "name": "Pro", "model": "gpt-4o"},
        ],
    },
    "moonshot": {
        "name": "Kimi / Moonshot",
        "base_url": "https://api.moonshot.cn/v1",
        "model": "moonshot-v1-8k",
        "tiers": [
            {"id": "flash", "name": "Flash", "model": "moonshot-v1-8k"},
            {"id": "pro", "name": "Pro", "model": "moonshot-v1-32k"},
        ],
    },
    "zhipu": {
        "name": "智谱 AI",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model": "glm-4-flash",
        "tiers": [
            {"id": "flash", "name": "Flash", "model": "glm-4-flash"},
            {"id": "pro", "name": "Pro", "model": "glm-4-plus"},
        ],
    },
    "custom": {
        "name": "自定义",
        "base_url": "",
        "model": "",
        "tiers": [],
    },
}


@dataclass
class RetrievalSettings:
    top_k: int = 5
    similarity_threshold: float = 0.6
    chunk_size: int = 500
    chunk_overlap: int = 50


@dataclass
class VisionSettings:
    enabled: bool = False
    api_base: str = ""
    api_key: str = ""
    model: str = ""
    send_images: bool = False


@dataclass
class AppearanceSettings:
    background_enabled: bool = False
    background_path: str = ""
    background_mode: str = "cover"
    mask_opacity: int = 45
    blur_radius: int = 0


@dataclass
class AppConfig:
    provider_id: str = "deepseek"
    provider_name: str = "DeepSeek"
    model_name: str = "deepseek-chat"
    model_tier: str = "flash"
    provider_api_keys: dict = field(default_factory=dict)
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-chat"
    deepseek_base_url: str = "https://api.deepseek.com"
    retrieval: RetrievalSettings = field(default_factory=RetrievalSettings)
    vision: VisionSettings = field(default_factory=VisionSettings)
    appearance: AppearanceSettings = field(default_factory=AppearanceSettings)

    def provider_config(self) -> tuple[str, str, str, str]:
        preset = AI_PROVIDERS.get(self.provider_id, AI_PROVIDERS["custom"])
        if self.provider_id == "custom":
            base_url = self.deepseek_base_url
            model = self.model_name or self.deepseek_model
        elif self.provider_id == "deepseek":
            base_url = self.deepseek_base_url or preset["base_url"]
            model = self.model_name or self.deepseek_model or preset["model"]
        else:
            base_url = self.deepseek_base_url or preset["base_url"]
            model = self.model_name or preset["model"]
        if self.provider_id == "deepseek" and model not in {"deepseek-chat", "deepseek-reasoner"}:
            model = "deepseek-chat"
        api_key = self.provider_api_keys.get(self.provider_id, "")
        if not api_key and self.provider_id == "deepseek":
            api_key = self.deepseek_api_key
        name = preset["name"] or self.provider_name
        return base_url, api_key, model, name

    @property
    def display_model_name(self) -> str:
        _base_url, api_key, model, name = self.provider_config()
        return f"{name} · {model or '未选择模型'}"

    def is_llm_configured(self) -> bool:
        _base_url, api_key, model, _name = self.provider_config()
        return bool(api_key and model)


class ConfigManager:
    """加载/保存 JSON 配置，密钥字段可在后续版本接入系统钥匙串。"""

    DEFAULT_FILENAME = "config.json"

    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = data_dir or user_data_dir()
        self.config_path = self.data_dir / self.DEFAULT_FILENAME
        self.config = AppConfig()
        self.load()

    @property
    def config_dir(self) -> Path:
        return self.data_dir

    @property
    def documents_dir(self) -> Path:
        return ensure_subdir(self.data_dir, "documents")

    @property
    def generated_dir(self) -> Path:
        return ensure_subdir(self.data_dir, "generated")

    @property
    def backgrounds_dir(self) -> Path:
        return ensure_subdir(self.data_dir, "backgrounds")

    @property
    def media_dir(self) -> Path:
        return ensure_subdir(self.data_dir, "media")

    @property
    def exports_dir(self) -> Path:
        return ensure_subdir(self.data_dir, "exports")

    @property
    def models_dir(self) -> Path:
        return ensure_subdir(self.data_dir, "models")

    def load(self) -> None:
        if not self.config_path.exists():
            self.save()
            return
        try:
            raw = json.loads(self.config_path.read_text(encoding="utf-8"))
            current = asdict(self.config)
            current.update({k: v for k, v in raw.items() if k in current})
            self.config = self._from_dict(current)
        except (json.JSONDecodeError, OSError):
            self.save()

    def save(self) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(
            json.dumps(asdict(self.config), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _from_dict(self, data: dict) -> AppConfig:
        cfg = AppConfig()
        cfg.provider_id = data.get("provider_id", cfg.provider_id)
        cfg.provider_name = data.get("provider_name", cfg.provider_name)
        cfg.model_name = data.get("model_name", cfg.model_name)
        cfg.model_tier = data.get("model_tier", cfg.model_tier)
        cfg.provider_api_keys = data.get("provider_api_keys", {}) or {}
        cfg.deepseek_api_key = data.get("deepseek_api_key", cfg.deepseek_api_key)
        cfg.deepseek_model = data.get("deepseek_model", cfg.deepseek_model)
        cfg.deepseek_base_url = data.get("deepseek_base_url", cfg.deepseek_base_url)
        retrieval = data.get("retrieval") or {}
        for key in asdict(cfg.retrieval):
            if key in retrieval:
                setattr(cfg.retrieval, key, retrieval[key])
        vision = data.get("vision") or {}
        for key in asdict(cfg.vision):
            if key in vision:
                setattr(cfg.vision, key, vision[key])
        appearance = data.get("appearance") or {}
        for key in asdict(cfg.appearance):
            if key in appearance:
                setattr(cfg.appearance, key, appearance[key])
        return cfg


def get_api_key() -> str:
    """优先读取环境变量，便于无 GUI 环境测试。"""
    configured = ConfigManager().config.provider_config()
    return os.environ.get("DEEPSEEK_API_KEY", "") or configured[1]
