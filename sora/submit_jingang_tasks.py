import argparse
import json
from pathlib import Path

import batch_generate_jingang as jingang
import test


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="批量提交《金刚经》分镜任务，不等待完成。")
    parser.add_argument("--start-index", type=int, default=1, help="从第几个分镜开始，1-based")
    parser.add_argument("--end-index", type=int, default=9, help="到第几个分镜结束，1-based")
    parser.add_argument("--tasks-file", default="generated_jingang/tasks.json", help="任务清单文件")
    return parser.parse_args()


def load_tasks(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def save_tasks(path: Path, tasks: list[dict]) -> None:
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    args = parse_args()
    tasks_path = Path(args.tasks_file)
    tasks = load_tasks(tasks_path)
    existing_names = {item["output_name"] for item in tasks}

    generator = test.VideoGenerator(
        api_key=test.API_KEY,
        base_url=test.BASE_URL,
    )

    start_index = max(args.start_index, 1) - 1
    end_index = min(args.end_index, len(jingang.SCENES))

    for output_name, scene_prompt in jingang.SCENES[start_index:end_index]:
        if output_name in existing_names:
            print(f"{output_name} 已存在于任务清单，跳过提交")
            continue

        prompt = jingang.build_prompt(scene_prompt)
        metadata = {
            "quality_level": "high",
            "negative_prompt": jingang.NEGATIVE_PROMPT,
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
        existing_names.add(output_name)
        save_tasks(tasks_path, tasks)
        print(f"{output_name} 已记录到 {tasks_path}")


if __name__ == "__main__":
    main()
