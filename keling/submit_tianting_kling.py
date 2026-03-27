import json
import time
from pathlib import Path

import requests

import batch_generate_tianting as tianting
import test


OUT_DIR = Path("generated_jingang_tianting_kling")
TASKS_PATH = OUT_DIR / "tasks.json"
MODEL_NAME = "kling-v1"
MODE = "std"
DURATION = "10"
ASPECT_RATIO = "16:9"
CFG_SCALE = 0.7


def build_create_url() -> str:
    base = test.BASE_URL.rstrip("/")
    if base.endswith("/v1/videos"):
        base = base[: -len("/v1/videos")]
    return f"{base}/kling/v1/videos/text2video"


def save_tasks(tasks: list[dict]) -> None:
    OUT_DIR.mkdir(exist_ok=True)
    TASKS_PATH.write_text(json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8")


def submit_task(prompt: str, negative_prompt: str) -> dict:
    payload = {
        "model_name": MODEL_NAME,
        "prompt": prompt[:500],
        "negative_prompt": negative_prompt[:200],
        "cfg_scale": CFG_SCALE,
        "mode": MODE,
        "aspect_ratio": ASPECT_RATIO,
        "duration": DURATION,
    }
    response = requests.post(
        build_create_url(),
        json=payload,
        headers={
            "Authorization": f"Bearer {test.API_KEY}",
            "Content-Type": "application/json",
        },
        timeout=300,
    )
    response.raise_for_status()
    return response.json()


def main() -> None:
    tasks: list[dict] = []

    for output_name, scene_prompt in tianting.SCENES:
        prompt = tianting.build_prompt(scene_prompt)
        print(f"\n===== 提交 {output_name} =====")
        result = submit_task(prompt=prompt, negative_prompt=tianting.NEGATIVE_PROMPT)
        task_id = str(result.get("id") or result.get("task_id") or "").strip()
        task = {
            "output_name": output_name,
            "task_id": task_id,
            "status": "submitted" if task_id else "submit_failed",
            "downloaded": False,
            "submit_result": result,
            "prompt": prompt,
            "model": MODEL_NAME,
            "mode": MODE,
            "duration": DURATION,
            "aspect_ratio": ASPECT_RATIO,
        }
        tasks.append(task)
        save_tasks(tasks)
        print(f"{output_name} 提交结果: {result}")
        time.sleep(1)


if __name__ == "__main__":
    main()
