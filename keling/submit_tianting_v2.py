import json
import time
from pathlib import Path

import batch_generate_tianting as tianting
import generate_cameo_video as cameo


OUT_DIR = Path("generated_jingang_tianting_v2")
TASKS_PATH = OUT_DIR / "tasks.json"
MODEL_NAME = "kling-video-multi-elements"


def save_tasks(tasks: list[dict]) -> None:
    OUT_DIR.mkdir(exist_ok=True)
    TASKS_PATH.write_text(json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8")


def build_client() -> cameo.CameoVideoClient:
    defaults = cameo.load_defaults_from_test_py(Path(__file__).with_name("test.py"))
    api_key = str(defaults.get("API_KEY", "")).strip()
    base_url = cameo.normalize_base_root(str(defaults.get("BASE_URL", cameo.DEFAULT_BASE_URL)).strip())
    return cameo.CameoVideoClient(api_key=api_key, base_root=base_url, timeout=600)


def main() -> None:
    tasks: list[dict] = []
    client = build_client()

    for output_name, scene_prompt in tianting.SCENES:
        prompt = tianting.build_prompt(scene_prompt)
        print(f"\n===== 提交 {output_name} =====")
        result = client.create_generation(
            prompt=prompt,
            model=MODEL_NAME,
            images=[],
            aspect_ratio="16:9",
            hd=False,
            duration="15",
            notify_hook="",
            watermark=False,
            private=False,
            character_url="",
            character_timestamps="",
        )
        task_id = str(result.get("id") or result.get("task_id") or "").strip()
        task = {
            "output_name": output_name,
            "task_id": task_id,
            "status": "submitted" if task_id else "submit_failed",
            "downloaded": False,
            "submit_result": result,
            "prompt": prompt,
            "model": MODEL_NAME,
        }
        tasks.append(task)
        save_tasks(tasks)
        print(f"{output_name} 提交结果: {result}")
        time.sleep(1)


if __name__ == "__main__":
    main()
