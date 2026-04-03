#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import ast
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict
from urllib.parse import urlsplit, urlunsplit

import requests


ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR / "sora") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "sora"))
if str(ROOT_DIR / "Veo") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "Veo"))
if str(ROOT_DIR / "keling") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "keling"))

import generate_video_with_character as sora_module  # noqa: E402
import generate_veo_video as veo_module  # noqa: E402
import test as sora_test_module  # noqa: E402
from config_utils import load_config as load_veo_config_file, DEFAULT_CONFIG_PATH as VEO_CONFIG_NAME  # noqa: E402


STATUS_RUNNING = {
    "submitted",
    "queued",
    "processing",
    "running",
    "in_progress",
    "not_start",
    "pending",
    "unknown",
}
STATUS_SUCCESS = {"completed", "success", "succeeded"}
STATUS_FAILED = {"failed", "failure", "error", "cancelled"}


def load_python_assignments(script_path: Path, names: set[str]) -> Dict[str, Any]:
    values: Dict[str, Any] = {}
    if not script_path.is_file():
        return values

    try:
        tree = ast.parse(script_path.read_text(encoding="utf-8"), filename=str(script_path))
    except (OSError, SyntaxError):
        return values

    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name) or target.id not in names:
                continue
            try:
                values[target.id] = ast.literal_eval(node.value)
            except Exception:
                continue
    return values


def load_sora_defaults() -> Dict[str, Any]:
    return load_python_assignments(
        ROOT_DIR / "sora" / "test.py",
        {"API_KEY", "BASE_URL", "TIMEOUT", "POLL_INTERVAL"},
    )


def load_veo_defaults() -> Dict[str, Any]:
    config = load_veo_config_file(ROOT_DIR / "Veo" / VEO_CONFIG_NAME)
    api = config.get("api", {})
    generation = config.get("generation", {})
    return {
        "API_KEY": str(api.get("api_key", "")).strip(),
        "BASE_URL": str(api.get("base_url", "")).strip(),
        "TIMEOUT": int(api.get("timeout", 900)),
        "POLL_INTERVAL": int(api.get("poll_interval", 5)),
        "MODEL": str(generation.get("model", "veo3.1-fast")).strip(),
        "ASPECT_RATIO": str(generation.get("aspect_ratio", "16:9")).strip(),
        "ENHANCE_PROMPT": bool(generation.get("enhance_prompt", False)),
        "ENABLE_UPSAMPLE": bool(generation.get("enable_upsample", True)),
        "PROMPT": str(generation.get("prompt", "")).strip(),
        "NEGATIVE_PROMPT": str(generation.get("negative_prompt", "")).strip(),
        "OUTPUT_NAME": str(generation.get("output_name", "veo_video")).strip(),
        "IMAGE_TO_VIDEO": bool(generation.get("image_to_video", False)),
        "IMAGES": list(generation.get("images", [])),
    }


def veo_config_path() -> Path:
    return ROOT_DIR / "Veo" / VEO_CONFIG_NAME


def save_veo_config(config_updates: Dict[str, Any]) -> None:
    path = veo_config_path()
    config = load_veo_config_file(path)
    api_updates = config_updates.get("api", {})
    generation_updates = config_updates.get("generation", {})
    config.setdefault("api", {}).update(api_updates)
    config.setdefault("generation", {}).update(generation_updates)
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


def load_keling_defaults() -> Dict[str, Any]:
    return load_python_assignments(
        ROOT_DIR / "keling" / "test.py",
        {"API_KEY", "BASE_URL", "TIMEOUT", "POLL_INTERVAL"},
    )


def normalize_base_root(base_url: str) -> str:
    value = (base_url or "").strip()
    if not value:
        return ""

    value = re.sub(
        r"^(https?://[^/]+?)(v1/videos|v2/videos/generations|kling/v1/videos)(.*)$",
        r"\1/\2\3",
        value,
    )

    # Repair common malformed inputs such as https://foxi-ai.topv1/videos
    # by restoring the missing slash before versioned paths.
    for marker in ("v1/videos", "v2/videos", "kling/v1/videos"):
        token = marker.replace("/", "")
        if token in value and marker not in value:
            value = value.replace(token, f"/{marker}")

    if value.startswith("http:/") and not value.startswith("http://"):
        value = value.replace("http:/", "http://", 1)
    if value.startswith("https:/") and not value.startswith("https://"):
        value = value.replace("https:/", "https://", 1)

    parts = urlsplit(value)
    if parts.scheme and parts.netloc:
        path = parts.path or ""
        if path.endswith("/v1/videos"):
            path = path[: -len("/v1/videos")]
        elif path.endswith("/v2/videos/generations"):
            path = path[: -len("/v2/videos/generations")]
        normalized = urlunsplit((parts.scheme, parts.netloc, path.rstrip("/"), "", ""))
        return normalized.rstrip("/")

    return veo_module.normalize_base_root(value)


def build_output_path(provider: str, output_name: str, task_id: str) -> Path:
    safe_name = output_name.strip() or provider
    out_dir = ROOT_DIR / "UI" / "generated" / provider
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / f"{safe_name}_{task_id}.mp4"


def normalize_status(provider: str, status: str) -> str:
    value = (status or "unknown").strip().lower()
    if value in STATUS_SUCCESS:
        return "completed"
    if value in STATUS_FAILED:
        return "failed"
    if value in STATUS_RUNNING:
        return value
    return value or "unknown"


def keling_text2video_url(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/v1/videos"):
        base = base[: -len("/v1/videos")]
    return f"{base}/kling/v1/videos/text2video"


def submit_sora_generation(
    *,
    api_key: str,
    base_url: str,
    prompt: str,
    model: str,
    duration: int,
    width: int,
    height: int,
    fps: int,
    timeout: int,
    poll_interval: int,
    output_name: str,
    negative_prompt: str,
) -> Dict[str, Any]:
    metadata: Dict[str, Any] = {"quality_level": "high"}
    if negative_prompt.strip():
        metadata["negative_prompt"] = negative_prompt.strip()

    client = sora_module.VideoGenerator(api_key=api_key, base_url=base_url, timeout=timeout)
    task_id = client.create_video_task(
        model=model,
        prompt=prompt,
        duration=duration,
        width=width,
        height=height,
        fps=fps,
        metadata=metadata,
    )
    return {
        "provider": "sora",
        "task_id": task_id,
        "task_name": output_name.strip() or "sora_task",
        "prompt": prompt,
        "status": "submitted",
        "progress": "",
        "file": "",
        "error": "",
        "api_key": api_key,
        "base_url": base_url,
        "timeout": timeout,
        "poll_interval": poll_interval,
        "params": {
            "model": model,
            "duration": duration,
            "width": width,
            "height": height,
            "fps": fps,
            "negative_prompt": negative_prompt,
        },
    }


def submit_veo_generation(
    *,
    api_key: str,
    base_url: str,
    prompt: str,
    negative_prompt: str,
    model: str,
    aspect_ratio: str,
    enhance_prompt: bool,
    enable_upsample: bool,
    image_to_video: bool,
    images: list[str],
    timeout: int,
    poll_interval: int,
    output_name: str,
) -> Dict[str, Any]:
    normalized_base = normalize_base_root(base_url)
    if not normalized_base:
        raise RuntimeError("Veo Base URL 不能为空")
    client = veo_module.VeoVideoClient(api_key=api_key, base_root=normalized_base, timeout=timeout)
    result = client.create_generation(
        prompt=veo_module.build_request_prompt(prompt, negative_prompt),
        model=model,
        aspect_ratio=aspect_ratio,
        enhance_prompt=enhance_prompt,
        enable_upsample=enable_upsample,
        images=veo_module.resolve_image_inputs(images) if image_to_video else None,
    )
    task_id = str(result.get("id") or result.get("task_id") or "").strip()
    if not task_id:
        raise RuntimeError(f"Veo 接口未返回 task_id: {result}")
    return {
        "provider": "veo",
        "task_id": task_id,
        "task_name": output_name.strip() or "veo_task",
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "status": "submitted",
        "progress": "",
        "file": "",
        "error": "",
        "api_key": api_key,
        "base_url": normalized_base,
        "timeout": timeout,
        "poll_interval": poll_interval,
        "params": {
            "model": model,
            "aspect_ratio": aspect_ratio,
            "enhance_prompt": enhance_prompt,
            "enable_upsample": enable_upsample,
            "image_to_video": image_to_video,
            "images": images,
            "negative_prompt": negative_prompt,
        },
    }


def submit_keling_generation(
    *,
    api_key: str,
    base_url: str,
    prompt: str,
    negative_prompt: str,
    model_name: str,
    aspect_ratio: str,
    duration: str,
    cfg_scale: float,
    mode: str,
    timeout: int,
    poll_interval: int,
    output_name: str,
) -> Dict[str, Any]:
    payload = {
        "model_name": model_name,
        "prompt": prompt[:500],
        "negative_prompt": negative_prompt[:200],
        "cfg_scale": cfg_scale,
        "mode": mode,
        "aspect_ratio": aspect_ratio,
        "duration": duration,
    }
    response = requests.post(
        keling_text2video_url(base_url),
        json=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        timeout=timeout,
    )
    response.raise_for_status()
    result = response.json()
    task_id = str(result.get("id") or result.get("task_id") or "").strip()
    if not task_id:
        raise RuntimeError(f"可灵接口未返回 task_id: {result}")
    return {
        "provider": "keling",
        "task_id": task_id,
        "task_name": output_name.strip() or "keling_task",
        "prompt": prompt,
        "status": "submitted",
        "progress": "",
        "file": "",
        "error": "",
        "api_key": api_key,
        "base_url": base_url,
        "timeout": timeout,
        "poll_interval": poll_interval,
        "params": {
            "model_name": model_name,
            "aspect_ratio": aspect_ratio,
            "duration": duration,
            "cfg_scale": cfg_scale,
            "mode": mode,
            "negative_prompt": negative_prompt,
        },
    }


def query_task_status(
    provider: str,
    *,
    api_key: str,
    base_url: str,
    task_id: str,
) -> Dict[str, Any]:
    if provider == "veo":
        client = veo_module.VeoVideoClient(api_key=api_key, base_root=base_url, timeout=30)
        return client.get_task_status(task_id)

    client = sora_test_module.VideoGenerator(api_key=api_key, base_url=base_url)
    data = client.get_task_status(task_id)
    return data or {}


def refresh_task_record(record: Dict[str, Any]) -> Dict[str, Any]:
    provider = str(record.get("provider", "")).strip().lower()
    api_key = str(record.get("api_key", "")).strip()
    base_url = str(record.get("base_url", "")).strip()
    task_id = str(record.get("task_id", "")).strip()
    task_name = str(record.get("task_name", "")).strip() or provider

    if not provider or not api_key or not base_url or not task_id:
        raise RuntimeError("任务记录缺少必要字段")

    raw = query_task_status(provider, api_key=api_key, base_url=base_url, task_id=task_id)
    status = normalize_status(provider, str(raw.get("status", "unknown")))
    progress = str(raw.get("progress", "") or "")

    updated = dict(record)
    updated["status"] = status
    updated["progress"] = progress
    updated["status_result"] = raw

    if status == "completed":
        output_path = str(updated.get("file", "")).strip()
        if not output_path:
            output_path = str(build_output_path(provider, task_name, task_id))
        path_obj = Path(output_path)
        if not path_obj.is_file():
            if provider == "veo":
                client = veo_module.VeoVideoClient(api_key=api_key, base_root=base_url, timeout=120)
                client.download_video(task_id, path_obj)
            else:
                client = sora_test_module.VideoGenerator(api_key=api_key, base_url=base_url)
                ok = client.download_video(task_id, str(path_obj))
                if not ok:
                    raise RuntimeError(f"{provider} 视频下载失败")
        updated["file"] = str(path_obj)
        updated["error"] = ""
    elif status == "failed":
        updated["file"] = ""
        updated["error"] = str(raw.get("fail_reason") or raw.get("error") or "任务失败")

    return updated
