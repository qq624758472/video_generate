import json
import time
from pathlib import Path

import test


OUT_DIR = Path("generated_jingang_tianting_kling")
TASKS_PATH = OUT_DIR / "tasks.json"


def load_tasks() -> list[dict]:
    if not TASKS_PATH.is_file():
        return []
    return json.loads(TASKS_PATH.read_text(encoding="utf-8"))


def save_tasks(tasks: list[dict]) -> None:
    OUT_DIR.mkdir(exist_ok=True)
    TASKS_PATH.write_text(json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    generator = test.VideoGenerator(
        api_key=test.API_KEY,
        base_url=test.BASE_URL,
    )

    while True:
        tasks = load_tasks()
        if not tasks:
            print("任务清单为空")
            return

        pending = 0
        for item in tasks:
            if not item.get("task_id") or item.get("downloaded"):
                continue

            pending += 1
            task_id = item["task_id"]
            status_data = generator.get_task_status(task_id) or {}
            status = status_data.get("status", "unknown")
            progress = status_data.get("progress")
            item["status"] = status
            item["progress"] = progress
            item["status_result"] = status_data
            print(f'{item["output_name"]}: {status} {progress}%')

            if status == "completed":
                save_path = OUT_DIR / f'{item["output_name"]}_{task_id}.mp4'
                if not save_path.is_file():
                    ok = generator.download_video(task_id, str(save_path))
                    if not ok:
                        item["download_error"] = "download_failed"
                        continue
                item["downloaded"] = True
                item["file"] = str(save_path)
                print(f'{item["output_name"]} 下载完成 {save_path}')
            elif status == "failed":
                item["error"] = status_data.get("error")

        save_tasks(tasks)

        if pending == 0:
            print("所有任务都已处理完成")
            return

        time.sleep(10)


if __name__ == "__main__":
    main()
