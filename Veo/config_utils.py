#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import ast
import json
from pathlib import Path
from typing import Any, Dict


DEFAULT_BASE_URL = "https://foxi-ai.top"
DEFAULT_TIMEOUT = 900
DEFAULT_POLL_INTERVAL = 5
DEFAULT_CONFIG_PATH = "veo_config.json"


def load_defaults_from_test_py(script_path: Path) -> Dict[str, Any]:
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
    base_url = base_url.rstrip("/")
    if base_url.endswith("/v1/videos"):
        return base_url[: -len("/v1/videos")]
    return base_url


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def default_config_from_test(script_dir: Path) -> Dict[str, Any]:
    defaults = load_defaults_from_test_py(script_dir / "test.py")
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
            "prompt": "",
            "negative_prompt": "",
            "output_name": "veo_video",
            "output_dir": "generated_veo",
        },
        "batch": {
            "variants_per_scene": 2,
            "start_index": 1,
            "end_index": 9,
            "output_dir": "generated_veo_batch",
        },
        "prompt_style": {
            "common_style": "",
            "negative_prompt": "",
            "variant_notes": {},
        },
    }


def load_config(config_path: Path) -> Dict[str, Any]:
    script_dir = config_path.resolve().parent
    config = default_config_from_test(script_dir)
    if config_path.is_file():
        user_config = json.loads(config_path.read_text(encoding="utf-8"))
        config = deep_merge(config, user_config)
    return config


def build_request_prompt(prompt: str, negative_prompt: str) -> str:
    prompt = " ".join((prompt or "").split()).strip()
    negative_prompt = " ".join((negative_prompt or "").split()).strip()
    if not negative_prompt:
        return prompt
    return f"{prompt} Avoid: {negative_prompt}."
