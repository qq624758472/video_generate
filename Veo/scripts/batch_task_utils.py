#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""批量任务通用工具。

这里不内置任何场景提示词，只负责：
- 定位 tasks.json
- 读写任务清单
- 缩短 prompt 后重试提交
"""

import json
from pathlib import Path

from generate_veo_video import VeoVideoClient


def resolve_batch_paths(config: dict) -> tuple[Path, Path]:
    batch = config.get("batch", {})
    out_dir = Path(str(batch.get("output_dir", "outputs/generated_veo_batch")).strip() or "outputs/generated_veo_batch")
    tasks_path_raw = str(batch.get("tasks_path", "")).strip()
    tasks_path = Path(tasks_path_raw) if tasks_path_raw else out_dir / "tasks.json"
    return out_dir, tasks_path


def load_tasks(tasks_path: Path) -> list[dict]:
    if not tasks_path.is_file():
        return []
    data = json.loads(tasks_path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    raise ValueError(f"任务文件格式不正确，应该是 JSON 数组: {tasks_path}")


def save_tasks(tasks: list[dict], tasks_path: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    tasks_path.parent.mkdir(parents=True, exist_ok=True)
    tasks_path.write_text(json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8")


def shorten_prompt(prompt: str, level: int) -> str:
    compact = " ".join(prompt.split())
    if level <= 0:
        return compact
    if level == 1:
        return compact[:700]
    if level == 2:
        return compact[:450]
    return compact[:260]


def submit_with_retry(
    *,
    client: VeoVideoClient,
    prompt: str,
    model: str,
    aspect_ratio: str,
    enhance_prompt: bool,
    enable_upsample: bool,
    images: list[str] | None = None,
) -> tuple[dict, str, str, int]:
    last_result: dict = {}
    last_error = ""
    used_prompt = prompt

    for retry_level in range(4):
        used_prompt = shorten_prompt(prompt, retry_level)
        try:
            result = client.create_generation(
                prompt=used_prompt,
                model=model,
                aspect_ratio=aspect_ratio,
                enhance_prompt=enhance_prompt,
                enable_upsample=enable_upsample,
                images=images,
            )
            task_id = str(result.get("id") or result.get("task_id") or "").strip()
            if task_id:
                return result, task_id, used_prompt, retry_level
            last_result = result
            last_error = "接口未返回 task_id"
        except Exception as exc:
            last_result = {"error": str(exc)}
            last_error = str(exc)
        print(f"提交失败，尝试缩短提示词后重试，级别={retry_level + 1}，原因: {last_error}")

    return last_result or {"error": last_error}, "", used_prompt, 3
