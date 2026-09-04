"""通过 ModelScope 将 bge-small-zh 下载到 E 盘数据目录。"""

from __future__ import annotations

import argparse
from urllib.parse import quote
from pathlib import Path

import requests


FILES = [
    "README.md",
    ".gitattributes",
    "config.json",
    "config_sentence_transformers.json",
    "configuration.json",
    "modules.json",
    "sentence_bert_config.json",
    "special_tokens_map.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "vocab.txt",
    "1_Pooling/config.json",
    "model.safetensors",
]
BASE_URL = "https://modelscope.cn/models/BAAI/bge-small-zh-v1.5/resolve/master"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data",
    )
    args = parser.parse_args()
    data_dir = args.data_dir.resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    target = data_dir / "models" / "bge-small-zh-v1.5"
    target.mkdir(parents=True, exist_ok=True)
    print(f"正在从 ModelScope 下载 bge-small-zh-v1.5 到 {target}")
    for relative_path in FILES:
        output = target / relative_path
        output.parent.mkdir(parents=True, exist_ok=True)
        encoded = quote(relative_path)
        url = f"{BASE_URL}/{encoded}"
        print(f"下载 {relative_path}")
        with requests.get(url, stream=True, timeout=120) as response:
            response.raise_for_status()
            with output.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=1024 * 512):
                    if chunk:
                        handle.write(chunk)
    print("模型下载完成")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
