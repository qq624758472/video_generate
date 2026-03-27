import json
from pathlib import Path

import batch_generate_tianting as tianting
import test


TASKS_PATH = tianting.output_dir() / "tasks.json"


def load_tasks() -> list[dict]:
    if not TASKS_PATH.is_file():
        return []
    return json.loads(TASKS_PATH.read_text(encoding="utf-8"))


def save_tasks(tasks: list[dict]) -> None:
    TASKS_PATH.write_text(json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    tasks = load_tasks()
    if not tasks:
        print("未找到任务清单")
        return

    prompt_map = {name: prompt for name, prompt in tianting.SCENES}
    generator = test.VideoGenerator(
        api_key=test.API_KEY,
        base_url=test.BASE_URL,
    )

    updated = False
    for item in tasks:
        if item.get("status") != "failed":
            continue

        output_name = item["output_name"]
        scene_prompt = prompt_map[output_name]
        prompt = tianting.build_prompt(scene_prompt)
        metadata = {
            "quality_level": "high",
            "negative_prompt": tianting.NEGATIVE_PROMPT,
        }

        print(f"\n===== 重新提交 {output_name} =====")
        task_id = generator.create_video_task(
            model="sora-2",
            prompt=prompt,
            duration=15,
            width=1920,
            height=1080,
            fps=24,
            metadata=metadata,
        )
        if not task_id:
            print(f"{output_name} 重新提交失败")
            continue

        item["task_id"] = task_id
        item["status"] = "submitted"
        item["downloaded"] = False
        item.pop("progress", None)
        item.pop("error", None)
        item.pop("file", None)
        updated = True
        save_tasks(tasks)
        print(f"{output_name} 已更新任务号 {task_id}")

    if not updated:
        print("没有需要重新提交的失败任务")


if __name__ == "__main__":
    main()
