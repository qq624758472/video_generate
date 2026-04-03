#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""从 tasks.json 读取任务并批量提交到 Veo。"""

import argparse
from pathlib import Path

from batch_task_utils import load_tasks, resolve_batch_paths, save_tasks, submit_with_retry
from config_utils import DEFAULT_CONFIG_PATH, build_request_prompt, load_config, resolve_image_inputs
from generate_veo_video import VeoVideoClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="从 tasks.json 读取任务并批量提交。")
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH, help="外部 JSON 配置文件路径")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config(Path(args.config).expanduser().resolve())
    api = config.get("api", {})
    generation = config.get("generation", {})
    out_dir, tasks_path = resolve_batch_paths(config)

    api_key = str(api.get("api_key", "")).strip()
    base_url = str(api.get("base_url", "")).strip()
    timeout = int(api.get("timeout", 900))
    default_model = str(generation.get("model", "veo3.1-fast")).strip()
    default_aspect_ratio = str(generation.get("aspect_ratio", "16:9")).strip()
    default_enhance_prompt = bool(generation.get("enhance_prompt", False))
    default_enable_upsample = bool(generation.get("enable_upsample", True))
    default_negative_prompt = str(generation.get("negative_prompt", "")).strip()

    if not api_key:
        print("缺少 API Key")
        return 1

    tasks = load_tasks(tasks_path)
    if not tasks:
        print(f"任务清单为空: {tasks_path}")
        return 1

    client = VeoVideoClient(api_key=api_key, base_root=base_url, timeout=timeout)

    for index, task in enumerate(tasks, start=1):
        output_name = str(task.get("output_name", f"task_{index:03d}")).strip() or f"task_{index:03d}"
        prompt = str(task.get("prompt", "")).strip()
        negative_prompt = str(task.get("negative_prompt", default_negative_prompt)).strip()
        model = str(task.get("model", default_model)).strip()
        aspect_ratio = str(task.get("aspect_ratio", default_aspect_ratio)).strip()
        enhance_prompt = bool(task.get("enhance_prompt", default_enhance_prompt))
        enable_upsample = bool(task.get("enable_upsample", default_enable_upsample))
        image_to_video = bool(task.get("image_to_video", False))
        images = resolve_image_inputs(list(task.get("images", []))) if image_to_video else None
        status = str(task.get("status", "")).strip().lower()

        if task.get("task_id") and status not in {"failed", "submit_failed", ""}:
            print(f"{output_name}: 已有 task_id，跳过")
            continue
        if not prompt:
            task["status"] = "invalid"
            task["error"] = "缺少 prompt"
            print(f"{output_name}: 缺少 prompt，跳过")
            save_tasks(tasks, tasks_path, out_dir)
            continue
        if image_to_video and not images:
            task["status"] = "invalid"
            task["error"] = "已启用图生视频，但 images 为空"
            print(f"{output_name}: images 为空，跳过")
            save_tasks(tasks, tasks_path, out_dir)
            continue

        final_prompt = build_request_prompt(prompt, negative_prompt)
        print(f"\n===== 提交 {output_name} =====")
        result, task_id, used_prompt, retry_level = submit_with_retry(
            client=client,
            prompt=final_prompt,
            model=model,
            aspect_ratio=aspect_ratio,
            enhance_prompt=enhance_prompt,
            enable_upsample=enable_upsample,
            images=images,
        )
        task["task_id"] = task_id
        task["status"] = "submitted" if task_id else "submit_failed"
        task["submit_result"] = result
        task["prompt"] = used_prompt
        task["original_prompt"] = final_prompt
        task["retry_level"] = retry_level
        task["model"] = model
        task["aspect_ratio"] = aspect_ratio
        task["enhance_prompt"] = enhance_prompt
        task["enable_upsample"] = enable_upsample
        task["image_to_video"] = image_to_video
        task["images"] = list(task.get("images", []))
        task["negative_prompt"] = negative_prompt
        if task_id:
            task["error"] = ""
            print(f"{output_name}: 提交成功 {task_id}")
        else:
            task["error"] = str(result)
            print(f"{output_name}: 提交失败 {result}")
        save_tasks(tasks, tasks_path, out_dir)

    print(f"\n任务清单已更新: {tasks_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
