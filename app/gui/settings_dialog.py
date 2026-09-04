"""设置与外观对话框。"""

from __future__ import annotations

import shutil
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.gui.context import AppContext
from app.core.config import AI_PROVIDERS
from app.utils.paths import STORAGE_OVERRIDE_FILE


class SettingsDialog(QDialog):
    def __init__(
        self,
        context: AppContext,
        current_kb_id: int | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.context = context
        self.current_kb_id = current_kb_id
        self.setWindowTitle("设置")
        self.resize(680, 560)
        self.background_source: str = ""
        cfg = context.config.config
        provider = AI_PROVIDERS.get(cfg.provider_id, AI_PROVIDERS["custom"])
        current_key = cfg.provider_api_keys.get(cfg.provider_id, "")
        if not current_key and cfg.provider_id == "deepseek":
            current_key = cfg.deepseek_api_key

        self.provider_combo = QComboBox()
        for provider_id, preset in AI_PROVIDERS.items():
            self.provider_combo.addItem(preset["name"], provider_id)
        self.provider_combo.setCurrentIndex(max(0, self.provider_combo.findData(cfg.provider_id)))
        self.provider_combo.currentIndexChanged.connect(self._provider_changed)
        self.api_key_edit = QLineEdit(current_key)
        self.api_base_edit = QLineEdit(cfg.deepseek_base_url or provider["base_url"])
        self.model_edit = QLineEdit(cfg.model_name or cfg.deepseek_model or provider["model"])
        self.tier_combo = QComboBox()
        self.tier_combo.currentIndexChanged.connect(self._tier_changed)
        self._populate_tiers(cfg.provider_id, cfg.model_name)

        self.storage_path_edit = QLineEdit(str(context.config.data_dir))
        self.storage_path_edit.setReadOnly(True)
        self.storage_choose_btn = QPushButton("更改目录")
        self.storage_choose_btn.clicked.connect(self.choose_storage)
        self.new_storage_path: Path | None = None

        self.top_k_spin = QSpinBox()
        self.top_k_spin.setRange(1, 30)
        self.top_k_spin.setValue(cfg.retrieval.top_k)
        self.threshold_spin = QDoubleSpinBox()
        self.threshold_spin.setRange(0.0, 1.0)
        self.threshold_spin.setSingleStep(0.05)
        self.threshold_spin.setValue(cfg.retrieval.similarity_threshold)
        self.chunk_size_spin = QSpinBox()
        self.chunk_size_spin.setRange(100, 2000)
        self.chunk_size_spin.setValue(cfg.retrieval.chunk_size)
        self.overlap_spin = QSpinBox()
        self.overlap_spin.setRange(0, 500)
        self.overlap_spin.setValue(cfg.retrieval.chunk_overlap)

        self.vision_enabled = QCheckBox("启用可选视觉理解")
        self.vision_enabled.setChecked(cfg.vision.enabled)
        self.vision_send = QCheckBox("允许将相关图片发送至配置的视觉服务")
        self.vision_send.setChecked(cfg.vision.send_images)
        self.vision_api = QLineEdit(cfg.vision.api_base)
        self.vision_key = QLineEdit(cfg.vision.api_key)
        self.vision_model = QLineEdit(cfg.vision.model)

        self.bg_enabled = QCheckBox("启用自定义背景")
        self.bg_enabled.setChecked(cfg.appearance.background_enabled)
        self.scope_combo = QComboBox()
        self.scope_combo.addItem("全局")
        self.scope_combo.addItem("当前知识库")
        if current_kb_id is None:
            self.scope_combo.setCurrentIndex(0)
            self.scope_combo.model().item(1).setEnabled(False)
        self.bg_path_edit = QLineEdit(cfg.appearance.background_path)
        self.browse_button = QPushButton("选择图片")
        self.browse_button.clicked.connect(self.choose_background)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["cover", "contain", "stretch", "tile"])
        self.mode_combo.setCurrentText(cfg.appearance.background_mode)
        self.mask_slider = QSlider(Qt.Horizontal)
        self.mask_slider.setRange(0, 90)
        self.mask_slider.setValue(cfg.appearance.mask_opacity)
        self.preview = QLabel("背景预览")
        self.preview.setMinimumSize(320, 170)
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setStyleSheet("border:1px solid #bbb; background-color:#fafafa;")
        self.load_preview()

        save_button = QPushButton("保存设置")
        save_button.clicked.connect(self.save_settings)
        cancel_button = QPushButton("取消")
        cancel_button.clicked.connect(self.reject)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(cancel_button)
        buttons.addWidget(save_button)

        tabs = QTabWidget()
        tabs.addTab(self._api_tab(), "API")
        tabs.addTab(self._storage_tab(), "存储")
        tabs.addTab(self._retrieval_tab(), "检索")
        tabs.addTab(self._vision_tab(), "图片理解")
        tabs.addTab(self._appearance_tab(), "外观")
        layout = QVBoxLayout(self)
        layout.addWidget(tabs)
        layout.addLayout(buttons)

    def _api_tab(self) -> QWidget:
        form = QFormLayout()
        form.addRow("AI 服务", self.provider_combo)
        form.addRow("模型强度", self.tier_combo)
        form.addRow("API Key", self.api_key_edit)
        form.addRow("API Base URL", self.api_base_edit)
        form.addRow("模型", self.model_edit)
        note = QLabel("切换 AI 服务后请确认 Base URL 和模型名。Key 仅保存在本地配置文件中。")
        note.setWordWrap(True)
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.addLayout(form)
        layout.addWidget(note)
        return box

    def _storage_tab(self) -> QWidget:
        row = QHBoxLayout()
        row.addWidget(self.storage_path_edit, 1)
        row.addWidget(self.storage_choose_btn)
        form = QFormLayout()
        form.addRow("数据存储目录", row)
        note = QLabel("更改目录后需要重启应用。知识库、向量库、文档、模型和背景图片都将使用新目录。")
        note.setWordWrap(True)
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.addLayout(form)
        layout.addWidget(note)
        return box

    def _provider_changed(self) -> None:
        provider_id = self.provider_combo.currentData()
        preset = AI_PROVIDERS.get(provider_id, AI_PROVIDERS["custom"])
        self.api_base_edit.setText(preset["base_url"])
        self._populate_tiers(provider_id, self.model_edit.text().strip())

    def _populate_tiers(self, provider_id: str, current_model: str = "") -> None:
        self.tier_combo.blockSignals(True)
        self.tier_combo.clear()
        preset = AI_PROVIDERS.get(provider_id, AI_PROVIDERS["custom"])
        for tier in preset.get("tiers", []):
            self.tier_combo.addItem(f"{tier['name']} · {tier['model']}", tier["id"])
        if not preset.get("tiers"):
            self.tier_combo.addItem("自定义模型", "custom")
            self.tier_combo.setEnabled(False)
        else:
            self.tier_combo.setEnabled(True)
            match = self.tier_combo.findText(
                next(
                    (f"{t['name']} · {t['model']}" for t in preset["tiers"] if t["model"] == current_model),
                    "",
                )
            )
            self.tier_combo.setCurrentIndex(max(0, match))
        self.tier_combo.blockSignals(False)
        if self.tier_combo.currentData():
            self._apply_tier(self.tier_combo.currentData())

    def _tier_changed(self) -> None:
        tier_id = self.tier_combo.currentData()
        if tier_id:
            self._apply_tier(tier_id)

    def _apply_tier(self, tier_id: str) -> None:
        provider_id = self.provider_combo.currentData()
        preset = AI_PROVIDERS.get(provider_id, AI_PROVIDERS["custom"])
        tier = next((t for t in preset.get("tiers", []) if t["id"] == tier_id), None)
        if tier:
            self.model_edit.setText(tier["model"])

    def choose_storage(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择数据存储目录")
        if path:
            self.new_storage_path = Path(path)
            self.storage_path_edit.setText(path)

    def _retrieval_tab(self) -> QWidget:
        form = QFormLayout()
        form.addRow("Top-K", self.top_k_spin)
        form.addRow("相似度阈值", self.threshold_spin)
        form.addRow("分块大小", self.chunk_size_spin)
        form.addRow("重叠量", self.overlap_spin)
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.addLayout(form)
        return box

    def _vision_tab(self) -> QWidget:
        form = QFormLayout()
        form.addRow(self.vision_enabled)
        form.addRow("API Base URL", self.vision_api)
        form.addRow("API Key", self.vision_key)
        form.addRow("视觉模型", self.vision_model)
        form.addRow(self.vision_send)
        note = QLabel("默认使用本地 OCR；启用后系统仅会将检索命中的相关图片发送至你填写的视觉服务。")
        note.setWordWrap(True)
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.addLayout(form)
        layout.addWidget(note)
        return box

    def _appearance_tab(self) -> QWidget:
        row = QHBoxLayout()
        row.addWidget(self.bg_path_edit, 1)
        row.addWidget(self.browse_button)
        form = QFormLayout()
        form.addRow(self.bg_enabled)
        form.addRow("作用范围", self.scope_combo)
        form.addRow("背景文件", row)
        form.addRow("显示模式", self.mode_combo)
        form.addRow("蒙层透明度", self.mask_slider)
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.addLayout(form)
        layout.addWidget(self.preview)
        return box

    def choose_background(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(
            self, "选择背景图片", "", "图片 (*.png *.jpg *.jpeg *.bmp *.webp)"
        )
        if not path:
            return
        self.bg_path_edit.setText(path)
        self.background_source = path
        self.load_preview()

    def load_preview(self) -> None:
        path = self.background_source or self.bg_path_edit.text().strip()
        if not path or not Path(path).exists():
            return
        pixmap = QPixmap(path)
        if not pixmap.isNull():
            self.preview.setPixmap(
                pixmap.scaled(
                    self.preview.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
            )

    def save_settings(self) -> None:
        cfg = self.context.config.config
        provider_id = self.provider_combo.currentData()
        preset = AI_PROVIDERS.get(provider_id, AI_PROVIDERS["custom"])
        api_key = self.api_key_edit.text().strip()
        cfg.provider_id = provider_id
        cfg.provider_name = preset["name"]
        cfg.model_name = self.model_edit.text().strip()
        cfg.model_tier = self.tier_combo.currentData() or "custom"
        if provider_id == "deepseek" and cfg.model_name not in {"deepseek-chat", "deepseek-reasoner"}:
            cfg.model_name = "deepseek-chat"
        cfg.provider_api_keys[provider_id] = api_key
        if provider_id == "deepseek":
            cfg.deepseek_api_key = api_key
            cfg.deepseek_model = cfg.model_name or cfg.deepseek_model
        cfg.deepseek_base_url = self.api_base_edit.text().strip() or "https://api.deepseek.com"
        cfg.retrieval.top_k = self.top_k_spin.value()
        cfg.retrieval.similarity_threshold = self.threshold_spin.value()
        cfg.retrieval.chunk_size = self.chunk_size_spin.value()
        cfg.retrieval.chunk_overlap = self.overlap_spin.value()
        cfg.vision.enabled = self.vision_enabled.isChecked()
        cfg.vision.send_images = self.vision_send.isChecked()
        cfg.vision.api_base = self.vision_api.text().strip()
        cfg.vision.api_key = self.vision_key.text().strip()
        cfg.vision.model = self.vision_model.text().strip()
        cfg.appearance.background_enabled = self.bg_enabled.isChecked()
        cfg.appearance.background_mode = self.mode_combo.currentText()
        cfg.appearance.mask_opacity = self.mask_slider.value()
        self.context.config.save()

        if self.new_storage_path:
            try:
                STORAGE_OVERRIDE_FILE.write_text(
                    str(self.new_storage_path.resolve()),
                    encoding="utf-8",
                )
                self.new_storage_path.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                QMessageBox.critical(self, "保存失败", str(exc))
                return

        try:
            kb_only = self.scope_combo.currentIndex() == 1 and self.current_kb_id
            if kb_only and cfg.appearance.background_enabled:
                path = self._store_background(self.current_kb_id)
                self._save_kb_background(path)
            elif cfg.appearance.background_enabled:
                path = self._store_background(None)
                cfg.appearance.background_path = str(path)
            elif kb_only:
                self._save_kb_background("")
            else:
                cfg.appearance.background_path = ""
        except Exception as exc:
            QMessageBox.critical(self, "背景保存失败", str(exc))
            return
        self.context.config.save()
        if self.new_storage_path:
            QMessageBox.information(self, "目录已更改", "请重启应用以使用新的数据存储目录。")
        self.accept()

    def _store_background(self, kb_id: int | None):
        source = self.background_source or self.bg_path_edit.text().strip()
        if not source:
            raise ValueError("请选择背景图片文件。")
        source_path = Path(source)
        suffix = source_path.suffix.lower()
        name = f"kb_{kb_id}{suffix}" if kb_id else f"global{suffix}"
        target = self.context.config.backgrounds_dir / name
        if source_path.resolve() == target.resolve():
            return target
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(source_path, target)
        except OSError as exc:
            raise RuntimeError(f"无法保存背景图片：{exc}") from exc
        return target

    def _save_kb_background(self, path: str) -> None:
        repo = self.context.repository()
        try:
            kb = repo.get_kb(self.current_kb_id)
            if not kb:
                return
            kb.background_setting = {
                "enabled": bool(path),
                "background_path": str(path),
                "background_mode": self.mode_combo.currentText(),
                "mask_opacity": self.mask_slider.value(),
            }
            repo.session.commit()
        finally:
            repo.close()
