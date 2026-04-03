#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Veo 脚本共用的配置与输入处理工具函数。"""

import ast
import base64
import json
import mimetypes
from pathlib import Path
from typing import Any, Dict


DEFAULT_BASE_URL = "https://foxi-ai.top"
DEFAULT_TIMEOUT = 900
DEFAULT_POLL_INTERVAL = 5
DEFAULT_CONFIG_PATH = "configs/veo_config.json"


def load_defaults_from_test_py(script_path: Path) -> Dict[str, Any]:
    # 从 test.py 里静态读取默认 API 配置，避免 import 时执行额外逻辑。
    defaults: Dict[str, Any] = {}
    if not script_path.is_file():
        return defaults

    try:
        tree = ast.parse(script_path.read_text(encoding="utf-8"), filename=str(script_path))
    except (OSError, SyntaxError):
        return defaults

    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue
            if target.id not in {"API_KEY", "BASE_URL", "TIMEOUT", "POLL_INTERVAL"}:
                continue
            try:
                defaults[target.id] = ast.literal_eval(node.value)
            except Exception:
                continue
    return defaults


def normalize_base_root(base_url: str) -> str:
    # 统一裁成接口根路径，避免后续拼接 endpoint 时重复 /v1/videos。
    base_url = base_url.rstrip("/")
    if base_url.endswith("/v1/videos"):
        return base_url[: -len("/v1/videos")]
    return base_url


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    # 递归合并配置，保证只覆盖用户显式传入的字段。
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def default_config_from_test(script_dir: Path) -> Dict[str, Any]:
    # 先构建一份完整默认配置，再让外部 JSON 覆盖其中一部分字段。
    test_script = script_dir / "test.py"
    if not test_script.is_file():
        test_script = script_dir.parent / "scripts" / "test.py"
    defaults = load_defaults_from_test_py(test_script)
    return {
        "api": {
            "api_key": str(defaults.get("API_KEY", "")).strip(),
            "base_url": normalize_base_root(str(defaults.get("BASE_URL", DEFAULT_BASE_URL)).strip() or DEFAULT_BASE_URL),
            "timeout": int(defaults.get("TIMEOUT", DEFAULT_TIMEOUT)),
            "poll_interval": int(defaults.get("POLL_INTERVAL", DEFAULT_POLL_INTERVAL)),
        },
        "generation": {
            "model": "veo3.1-fast",
            "aspect_ratio": "16:9",
            "enhance_prompt": False,
            "enable_upsample": True,
            "image_to_video": False,
            "images": [],
            "prompt": "",
            "negative_prompt": "",
            "output_name": "veo_video",
            "output_dir": "outputs/generated_veo",
        },
        "batch": {
            "variants_per_scene": 2,
            "start_index": 1,
            "end_index": 9,
            "output_dir": "outputs/generated_veo_batch",
        },
        "prompt_style": {
            "common_style": "",
            "negative_prompt": "",
            "variant_notes": {},
        },
    }


def load_config(config_path: Path) -> Dict[str, Any]:
    # 读取用户配置前，先补齐所有默认值，避免业务脚本里到处判空。
    script_dir = config_path.resolve().parent
    config = default_config_from_test(script_dir)
    if config_path.is_file():
        user_config = json.loads(config_path.read_text(encoding="utf-8"))
        config = deep_merge(config, user_config)
    return config


def build_request_prompt(prompt: str, negative_prompt: str) -> str:
    # 把多余空白压平，并按统一格式把负面提示词拼到 prompt 末尾。
    prompt = " ".join((prompt or "").split()).strip()
    negative_prompt = " ".join((negative_prompt or "").split()).strip()
    if not negative_prompt:
        return prompt
    return f"{prompt} Avoid: {negative_prompt}."


def to_data_url(value: str) -> str:
    # 如果传入的是本地图片路径，这里自动转成 Veo 可接受的 data URL。
    raw = (value or "").strip()
    if not raw:
        return raw
    if raw.startswith(("http://", "https://", "data:")):
        return raw

    path = Path(raw).expanduser().resolve()
    if not path.is_file():
        return raw

    mime_type, _ = mimetypes.guess_type(path.name)
    mime_type = mime_type or "image/jpeg"
    encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"


def resolve_image_inputs(images: list[str]) -> list[str]:
    # 统一处理多张输入图，保留 URL / data URL，转换本地文件路径。
    return [to_data_url(item) for item in images if str(item).strip()]
