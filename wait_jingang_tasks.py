import argparse
import json
import time
from pathlib import Path

import test


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="统一轮询《金刚经》分镜任务并下载。")
    parser.add_argument("--tasks-file", default="generated_jingang/tasks.json", help="任务清单文件")
    parser.add_argument("--poll-interval", type=int, default=10, help="轮询间隔秒数")
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
    out_dir = tasks_path.parent
    out_dir.mkdir(exist_ok=True)

    generator = test.VideoGenerator(
        api_key=test.API_KEY,
        base_url=test.BASE_URL,
    )

    while True:
        tasks = load_tasks(tasks_path)
        if not tasks:
            print("任务清单为空")
            time.sleep(args.poll_interval)
            continue

        pending = 0
        for item in tasks:
            if item.get("downloaded"):
                continue

            pending += 1
            task_id = item["task_id"]
            status_data = generator.get_task_status(task_id) or {}
            status = status_data.get("status", "unknown")
            progress = status_data.get("progress")
            item["status"] = status
            item["progress"] = progress
            print(f'{item["output_name"]}: {status} {progress}%')

            if status == "completed":
                save_path = out_dir / f'{item["output_name"]}_{task_id}.mp4'
                if save_path.is_file():
                    item["downloaded"] = True
                    item["file"] = str(save_path)
                    print(f'{item["output_name"]} 已存在 {save_path}')
                else:
                    ok = generator.download_video(task_id=task_id, save_path=str(save_path))
                    if ok:
                        item["downloaded"] = True
                        item["file"] = str(save_path)
                        print(f'{item["output_name"]} 下载完成 {save_path}')
            elif status == "failed":
                item["error"] = status_data.get("error")

        save_tasks(tasks_path, tasks)

        if pending == 0:
            print("所有任务都已下载完成")
            return

        time.sleep(args.poll_interval)


if __name__ == "__main__":
    main()
