# 本地文档知识库桌面助手

一个基于 PySide6 的跨平台本地知识库桌面应用。它把“文档管理、本地检索、AI 问答、原文阅读、Markdown 生成、图片理解”放在同一个 Obsidian 风格的轻量界面里，适合课件、论文、讲义和本地资料的整理与研究。

## 功能特性

- 多知识库管理：创建、切换、重命名、删除，知识库之间相互隔离。
- 多格式文档导入：支持 PDF、DOCX、PPTX、TXT、Markdown 和常见图片。
- 本地解析与向量化：文档解析、分块、向量入库均在本地完成。
- 中文 RAG 问答：结合 DeepSeek 等 OpenAI 兼容服务，答案附带可追溯引用。
- 图片理解：PDF/Office 中嵌入图片的提取、RapidOCR 本地识别和可选视觉模型。
- 原文阅读器：侧栏点击文件即可阅读，PDF 支持翻页、缩放、页码跳转与搜索。
- 原文保存：支持将当前文件另存为副本，并自动恢复上次阅读位置。
- Markdown 能力：聊天内容渲染、会话导出、AI 生成知识文档。
- 多 AI 供应商：DeepSeek、OpenAI、Kimi/Moonshot、智谱 AI 和自定义服务。
- 模型强度切换：按供应商提供 Flash/Pro 等档位，右上角可快速切换。
- 自定义存储路径：知识库、向量库、模型、背景图可统一存放在指定目录。
- 统一界面主题：浅色二次元可爱风格，支持全窗口背景图覆盖。
- 打包发布：提供 PyInstaller 配置，可生成 Windows 独立可执行程序。

## 技术栈

- 桌面界面：PySide6 / Qt for Python
- 开发语言：Python 3.10+
- 关系数据库：SQLite + SQLAlchemy
- 向量数据库：Chroma
- 文档解析：pdfplumber、python-docx、python-pptx、PyMuPDF
- 嵌入模型：BAAI/bge-small-zh-v1.5
- OCR：RapidOCR
- 大模型 API：OpenAI 兼容接口
- 打包：PyInstaller

## 快速开始

### 1. 准备环境

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 下载本地嵌入模型

默认使用 `BAAI/bge-small-zh-v1.5`。可以直接通过 Hugging Face 或国内镜像下载，也可以运行：

```powershell
.\.venv\Scripts\python.exe scripts\download_models.py
```

模型文件保存到应用的数据目录中，不会写入仓库。

### 3. 启动应用

```powershell
.\.venv\Scripts\python.exe main.py
```

Windows 下也可以直接运行 `启动.bat`。该脚本会优先启动 `dist` 内已打包程序；没有打包程序时，会自动检测/使用 winget 安装 Python、创建 `.venv`、安装依赖、下载嵌入模型，然后启动源码版本。

### 4. 配置 AI

打开“设置 → API”，选择 AI 服务并填写 API Key，再选择模型强度：

| AI 服务 | Flash | Pro |
| --- | --- | --- |
| DeepSeek | deepseek-chat | deepseek-reasoner |
| OpenAI | gpt-4o-mini | gpt-4o |
| Kimi / Moonshot | moonshot-v1-8k | moonshot-v1-32k |
| 智谱 AI | glm-4-flash | glm-4-plus |

右上角会显示当前服务商和模型名称，可直接切换模型档位。

## 数据与隐私

- 原始文档、SQLite、向量库、OCR 结果和对话记录默认保存在本地数据目录。
- 只有用户显式配置 AI 后才会上传必要的检索片段。
- 上传到 GitHub 的版本不会包含 `.venv`、`data/`、`dist/`、模型权重、配置文件或个人资料。
- 可以通过“设置 → 存储”将数据目录迁移到任意磁盘位置。

## 项目结构

```text
.
├── app/
│   ├── core/               # 配置、文档解析、问答、Markdown、视觉服务
│   ├── data/               # SQLAlchemy 模型、Repository、向量存储
│   └── gui/                # 主窗口、文件侧栏、阅读器、聊天与设置
├── docs/                   # 项目任务书与前端功能说明
├── knowledge-reader/       # 前端 UI 参考稿
├── scripts/                # 模型下载与测试脚本
├── tests/                  # 自动化测试
├── main.py                 # 程序入口
├── requirements.txt
└── LocalKB.spec            # PyInstaller 打包配置
```

## 测试

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
```

## 打包

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm LocalKB.spec
```

输出目录为 `dist/本地文档知识库桌面助手/`。

## 文档

- 项目任务书：[docs/项目任务书-本地文档知识库桌面助手.md](docs/项目任务书-本地文档知识库桌面助手.md)
- 前端功能说明：[docs/前端功能介绍-原文阅读与侧栏设计.md](docs/前端功能介绍-原文阅读与侧栏设计.md)

