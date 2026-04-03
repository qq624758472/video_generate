#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
from pathlib import Path

import batch_generate_jingang as jingang
from config_utils import DEFAULT_CONFIG_PATH, build_request_prompt, load_config
from generate_veo_video import VeoVideoClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="批量提交《金刚经》9个分镜的 Veo 任务。")
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH, help="外部 JSON 配置文件路径")
    return parser.parse_args()


def resolve_batch_paths(config: dict) -> tuple[Path, Path]:
    batch = config.get("batch", {})
    out_dir = Path(str(batch.get("output_dir", "outputs/generated_veo_batch")).strip() or "outputs/generated_veo_batch")
    tasks_path = out_dir / "tasks.json"
    return out_dir, tasks_path


def save_tasks(tasks: list[dict], tasks_path: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
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
    aspect_ratio = str(generation.get("aspect_ratio", "16:9")).strip()
    enhance_prompt = bool(generation.get("enhance_prompt", False))
    enable_upsample = bool(generation.get("enable_upsample", True))
    generation_negative_prompt = str(generation.get("negative_prompt", "")).strip()
    variants_per_scene = int(batch.get("variants_per_scene", 2))
    start_index = int(batch.get("start_index", 1))
    end_index = int(batch.get("end_index", 9))
    common_style = str(prompt_style.get("common_style", "")).strip()
    style_negative_prompt = str(prompt_style.get("negative_prompt", "")).strip()
    variant_notes_raw = prompt_style.get("variant_notes", {})
    variant_notes = {int(key): str(value) for key, value in variant_notes_raw.items()}

    if not api_key:
        print("缺少 API Key")
        return 1

    variant_plan = f"每个分镜提交 {variants_per_scene} 个变体视频任务。"
    print(variant_plan)

    client = VeoVideoClient(api_key=api_key, base_root=base_url, timeout=timeout)
    tasks: list[dict] = []

    start = max(start_index, 1) - 1
    end = min(end_index, len(jingang.SCENES))

    for scene_name, scene_prompt in jingang.SCENES[start:end]:
        for variant_index in range(1, variants_per_scene + 1):
            output_name = scene_name if variants_per_scene == 1 else f"{scene_name}_v{variant_index}"
            scene_based_prompt = (
                jingang.build_prompt(
                    scene_prompt,
                    common_style=common_style,
                    negative_prompt=style_negative_prompt,
                )
                if variants_per_scene == 1
                else jingang.build_variant_prompt(
                    scene_prompt,
                    variant_index,
                    common_style=common_style,
                    negative_prompt=style_negative_prompt,
                    variant_notes=variant_notes,
                )
            )
            original_prompt = build_request_prompt(scene_based_prompt, generation_negative_prompt)

            print(f"\n===== 提交 {output_name} =====")
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
                print(f"{output_name} 提交结果: {result}")
            else:
                print(f"{output_name} 提交失败: {result}")

            tasks.append(
                {
                    "output_name": output_name,
                    "scene_name": scene_name,
                    "variant_index": variant_index,
                    "variants_per_scene": variants_per_scene,
                    "task_id": task_id,
                    "status": status,
                    "model": model,
                    "aspect_ratio": aspect_ratio,
                    "submit_result": result,
                    "prompt": used_prompt,
                    "original_prompt": original_prompt,
                    "negative_prompt": generation_negative_prompt,
                    "retry_level": retry_level,
                    "plan_note": variant_plan,
                }
            )
            save_tasks(tasks, tasks_path, out_dir)

    print(f"\n任务清单已保存到: {tasks_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
