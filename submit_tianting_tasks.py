import json
from pathlib import Path

import batch_generate_tianting as tianting
import test


def save_tasks(path: Path, tasks: list[dict]) -> None:
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    tasks_path = tianting.output_dir() / "tasks.json"
    tasks: list[dict] = []

    generator = test.VideoGenerator(
        api_key=test.API_KEY,
        base_url=test.BASE_URL,
    )

    for output_name, scene_prompt in tianting.SCENES:
        prompt = tianting.build_prompt(scene_prompt)
        metadata = {
            "quality_level": "high",
            "negative_prompt": tianting.NEGATIVE_PROMPT,
        }
        print(f"\n===== 提交 {output_name} =====")
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
            print(f"{output_name} 提交失败")
            continue

        tasks.append(
            {
                "output_name": output_name,
                "task_id": task_id,
                "status": "submitted",
                "downloaded": False,
            }
        )
        save_tasks(tasks_path, tasks)
        print(f"{output_name} 已记录到 {tasks_path}")


if __name__ == "__main__":
    main()
