#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import ast
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict

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
    return load_python_assignments(
        ROOT_DIR / "Veo" / "test.py",
        {"API_KEY", "BASE_URL", "TIMEOUT", "POLL_INTERVAL"},
    )


def load_keling_defaults() -> Dict[str, Any]:
    return load_python_assignments(
        ROOT_DIR / "keling" / "test.py",
        {"API_KEY", "BASE_URL", "TIMEOUT", "POLL_INTERVAL"},
    )


def build_output_path(provider: str, output_name: str, task_id: str) -> Path:
    safe_name = output_name.strip() or provider
    out_dir = ROOT_DIR / "UI" / "generated" / provider
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / f"{safe_name}_{task_id}.mp4"


def run_sora_generation(
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
    logger: Callable[[str], None],
) -> Dict[str, Any]:
    metadata: Dict[str, Any] = {"quality_level": "high"}
    if negative_prompt.strip():
        metadata["negative_prompt"] = negative_prompt.strip()

    logger("开始创建 Sora 视频任务")
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
    logger(f"Sora 任务已创建: {task_id}")
    client.wait_for_task_complete(task_id, poll_interval)
    output_path = build_output_path("sora", output_name, task_id)
    client.download_video(task_id, output_path)
    logger(f"Sora 视频已保存: {output_path}")
    return {"provider": "sora", "task_id": task_id, "file": str(output_path)}


def run_veo_generation(
    *,
    api_key: str,
    base_url: str,
    prompt: str,
    model: str,
    aspect_ratio: str,
    enhance_prompt: bool,
    enable_upsample: bool,
    timeout: int,
    poll_interval: int,
    output_name: str,
    logger: Callable[[str], None],
) -> Dict[str, Any]:
    logger("开始创建 Veo 视频任务")
    client = veo_module.VeoVideoClient(api_key=api_key, base_root=base_url, timeout=timeout)
    result = client.create_generation(
        prompt=prompt,
        model=model,
        aspect_ratio=aspect_ratio,
        enhance_prompt=enhance_prompt,
        enable_upsample=enable_upsample,
    )
    task_id = str(result.get("id") or result.get("task_id") or "").strip()
    if not task_id:
        raise RuntimeError(f"Veo 接口未返回 task_id: {result}")
    logger(f"Veo 任务已创建: {task_id}")
    client.wait_for_completion(task_id, poll_interval)
    output_path = build_output_path("veo", output_name, task_id)
    client.download_video(task_id, output_path)
    logger(f"Veo 视频已保存: {output_path}")
    return {"provider": "veo", "task_id": task_id, "file": str(output_path)}


def keling_text2video_url(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/v1/videos"):
        base = base[: -len("/v1/videos")]
    return f"{base}/kling/v1/videos/text2video"


def run_keling_generation(
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
    logger: Callable[[str], None],
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
    logger("开始创建可灵视频任务")
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
    logger(f"可灵任务已创建: {task_id}")

    status_client = sora_test_module.VideoGenerator(api_key=api_key, base_url=base_url)
    start_time = time.time()
    while time.time() - start_time < timeout:
        status_data = status_client.get_task_status(task_id) or {}
        status = str(status_data.get("status", "unknown"))
        progress = status_data.get("progress")
        logger(f"可灵状态: {status} progress={progress}")
        if status == "completed":
            output_path = build_output_path("keling", output_name, task_id)
            ok = status_client.download_video(task_id, str(output_path))
            if not ok:
                raise RuntimeError("可灵视频下载失败")
            logger(f"可灵视频已保存: {output_path}")
            return {"provider": "keling", "task_id": task_id, "file": str(output_path)}
        if status == "failed":
            raise RuntimeError(f"可灵任务失败: {status_data}")
        time.sleep(poll_interval)

    raise TimeoutError(f"可灵任务超时: {task_id}")


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
