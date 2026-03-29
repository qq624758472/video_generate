#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import time
from pathlib import Path

from config_utils import DEFAULT_CONFIG_PATH, build_request_prompt, load_config
from generate_veo_video import VeoVideoClient
from submit_jingang_batch import resolve_batch_paths, shorten_prompt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="轮询批量任务，成功即下载，失败则缩短提示词重提。")
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH, help="外部 JSON 配置文件路径")
    return parser.parse_args()


def load_tasks(tasks_path: Path) -> list[dict]:
    if not tasks_path.is_file():
        return []
    return json.loads(tasks_path.read_text(encoding="utf-8"))


def save_tasks(tasks: list[dict], tasks_path: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    tasks_path.write_text(json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8")


def submit_retry(client: VeoVideoClient, task: dict, negative_prompt: str) -> dict:
    original_prompt = str(task.get("original_prompt") or task.get("prompt") or "").strip()
    current_retry = int(task.get("retry_level", 0))
    next_retry = min(current_retry + 1, 3)
    prompt = build_request_prompt(shorten_prompt(original_prompt, next_retry), negative_prompt)

    result = client.create_generation(
        prompt=prompt,
        model=str(task.get("model", "veo3.1-fast")),
        aspect_ratio=str(task.get("aspect_ratio", "16:9")),
        enhance_prompt=False,
        enable_upsample=True,
    )
    task_id = str(result.get("id") or result.get("task_id") or "").strip()
    task["task_id"] = task_id
    task["submit_result"] = result
    task["prompt"] = prompt
    task["retry_level"] = next_retry
    task["status"] = "submitted" if task_id else "submit_failed"
    task["error"] = "" if task_id else "retry_submit_failed"
    task.pop("status_result", None)
    task.pop("file", None)
    return task


def main() -> int:
    args = parse_args()
    config = load_config(Path(args.config).expanduser().resolve())
    api = config.get("api", {})
    generation = config.get("generation", {})
    out_dir, tasks_path = resolve_batch_paths(config)
    download_dir = out_dir / "downloads"

    api_key = str(api.get("api_key", "")).strip()
    base_url = str(api.get("base_url", "")).strip()
    timeout = int(api.get("timeout", 900))
    poll_interval = int(api.get("poll_interval", 5))
    generation_negative_prompt = str(generation.get("negative_prompt", "")).strip()

    if not api_key:
        print("缺少 API Key")
        return 1

    client = VeoVideoClient(api_key=api_key, base_root=base_url, timeout=timeout)
    download_dir.mkdir(parents=True, exist_ok=True)

    while True:
        tasks = load_tasks(tasks_path)
        if not tasks:
            print("任务清单为空")
            return 1

        completed = 0
        for task in tasks:
            output_name = str(task.get("output_name", "")).strip()
            task_id = str(task.get("task_id", "")).strip()
            status = str(task.get("status", "submitted")).strip().lower()

            if task.get("file"):
                completed += 1
                continue

            if not task_id or status == "submit_failed":
                try:
                    print(f"{output_name}: 重新提交")
                    submit_retry(client, task, generation_negative_prompt)
                    print(f"{output_name}: 新任务 {task.get('task_id')}")
                except Exception as exc:
                    task["status"] = "submit_failed"
                    task["error"] = str(exc)
                    print(f"{output_name}: 重提失败 {exc}")
                save_tasks(tasks, tasks_path, out_dir)
                continue

            try:
                status_data = client.get_task_status(task_id)
            except Exception as exc:
                task["error"] = str(exc)
                print(f"{output_name}: 查询失败 {exc}")
                save_tasks(tasks, tasks_path, out_dir)
                continue

            raw_status = str(status_data.get("status", "unknown")).upper()
            progress = str(status_data.get("progress", "") or "")
            task["status_result"] = status_data
            task["progress"] = progress
            print(f"{output_name}: {raw_status} {progress}")

            if raw_status in {"COMPLETED", "SUCCESS", "SUCCEEDED"}:
                save_path = download_dir / f"{output_name}_{task_id}.mp4"
                try:
                    if not save_path.is_file():
                        client.download_video(task_id, save_path)
                    task["status"] = "completed"
                    task["file"] = str(save_path)
                    task["error"] = ""
                    completed += 1
                    print(f"{output_name}: 下载完成 {save_path}")
                except Exception as exc:
                    task["error"] = str(exc)
                    print(f"{output_name}: 下载失败 {exc}")
            elif raw_status in {"FAILED", "FAILURE", "ERROR"}:
                task["status"] = "failed"
                task["error"] = str(status_data.get("fail_reason") or status_data.get("error") or "任务失败")
                print(f"{output_name}: 失败，准备缩短提示词重提")
                try:
                    submit_retry(client, task, generation_negative_prompt)
                    print(f"{output_name}: 已重提为 {task.get('task_id')}")
                except Exception as exc:
                    task["status"] = "submit_failed"
                    task["error"] = str(exc)
                    print(f"{output_name}: 重提失败 {exc}")
            else:
                task["status"] = raw_status.lower()

            save_tasks(tasks, tasks_path, out_dir)

        if completed >= len(tasks):
            print(f"全部完成，共下载 {completed} 个视频。")
            return 0

        print(f"当前已完成 {completed}/{len(tasks)}，{poll_interval} 秒后继续轮询。")
        time.sleep(poll_interval)


if __name__ == "__main__":
    raise SystemExit(main())
