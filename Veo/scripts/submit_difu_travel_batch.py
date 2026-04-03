#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
from pathlib import Path

import batch_generate_difu_travel as difu
from config_utils import DEFAULT_CONFIG_PATH, build_request_prompt, load_config
from generate_veo_video import VeoVideoClient
from submit_jingang_batch import resolve_batch_paths, save_tasks, submit_with_retry


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="批量提交地府游记 10 个分镜的 Veo 任务。")
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH, help="外部 JSON 配置文件路径")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config(Path(args.config).expanduser().resolve())
    api = config.get("api", {})
    generation = config.get("generation", {})
    batch = config.get("batch", {})
    prompt_style = config.get("prompt_style", {})
    out_dir, tasks_path = resolve_batch_paths(config)

    api_key = str(api.get("api_key", "")).strip()
    base_url = str(api.get("base_url", "")).strip()
    timeout = int(api.get("timeout", 900))
    model = str(generation.get("model", "veo3.1-fast")).strip()
    aspect_ratio = str(generation.get("aspect_ratio", "9:16")).strip()
    enhance_prompt = bool(generation.get("enhance_prompt", False))
    enable_upsample = bool(generation.get("enable_upsample", True))
    generation_negative_prompt = str(generation.get("negative_prompt", "")).strip()
    start_index = int(batch.get("start_index", 1))
    end_index = int(batch.get("end_index", 10))
    common_style = str(prompt_style.get("common_style", "")).strip()
    style_negative_prompt = str(prompt_style.get("negative_prompt", "")).strip()

    if not api_key:
        print("缺少 API Key")
        return 1

    print("每个场景提交 1 个视频任务。")

    client = VeoVideoClient(api_key=api_key, base_root=base_url, timeout=timeout)
    tasks: list[dict] = []

    start = max(start_index, 1) - 1
    end = min(end_index, len(difu.SCENES))

    for scene_name, scene_prompt in difu.SCENES[start:end]:
        original_prompt = build_request_prompt(
            difu.build_prompt(
                scene_prompt,
                common_style=common_style,
                negative_prompt=style_negative_prompt,
            ),
            generation_negative_prompt,
        )

        print(f"\n===== 提交 {scene_name} =====")
        result, task_id, used_prompt, retry_level = submit_with_retry(
            client=client,
            prompt=original_prompt,
            model=model,
            aspect_ratio=aspect_ratio,
            enhance_prompt=enhance_prompt,
            enable_upsample=enable_upsample,
        )
        status = "submitted" if task_id else "submit_failed"
        if task_id:
            print(f"{scene_name} 提交结果: {result}")
        else:
            print(f"{scene_name} 提交失败: {result}")

        tasks.append(
            {
                "output_name": scene_name,
                "scene_name": scene_name,
                "variant_index": 1,
                "variants_per_scene": 1,
                "task_id": task_id,
                "status": status,
                "model": model,
                "aspect_ratio": aspect_ratio,
                "submit_result": result,
                "prompt": used_prompt,
                "original_prompt": original_prompt,
                "negative_prompt": generation_negative_prompt,
                "retry_level": retry_level,
                "plan_note": "地府游记 10 个不同场景，每个场景提交 1 个视频任务。",
            }
        )
        save_tasks(tasks, tasks_path, out_dir)

    print(f"\n任务清单已保存到: {tasks_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
