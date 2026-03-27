import json
import time
from pathlib import Path

import generate_cameo_video as cameo


OUT_DIR = Path("generated_jingang_tianting_v2")
TASKS_PATH = OUT_DIR / "tasks.json"


def load_tasks() -> list[dict]:
    if not TASKS_PATH.is_file():
        return []
    return json.loads(TASKS_PATH.read_text(encoding="utf-8"))


def save_tasks(tasks: list[dict]) -> None:
    OUT_DIR.mkdir(exist_ok=True)
    TASKS_PATH.write_text(json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8")


def build_client() -> cameo.CameoVideoClient:
    defaults = cameo.load_defaults_from_test_py(Path(__file__).with_name("test.py"))
    api_key = str(defaults.get("API_KEY", "")).strip()
    base_url = cameo.normalize_base_root(str(defaults.get("BASE_URL", cameo.DEFAULT_BASE_URL)).strip())
    return cameo.CameoVideoClient(api_key=api_key, base_root=base_url, timeout=600)


def main() -> None:
    client = build_client()

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
            try:
                status_data = client.get_task_status(task_id)
            except Exception as exc:
                item["status"] = "status_error"
                item["error"] = str(exc)
                print(f'{item["output_name"]}: status_error {exc}')
                continue

            status = status_data.get("status", "unknown")
            progress = status_data.get("progress")
            item["status"] = status
            item["progress"] = progress
            item["status_result"] = status_data
            print(f'{item["output_name"]}: {status} {progress}%')

            if status == "completed":
                save_path = OUT_DIR / f'{item["output_name"]}_{task_id}.mp4'
                try:
                    if not save_path.is_file():
                        client.download_video(task_id, save_path)
                    item["downloaded"] = True
                    item["file"] = str(save_path)
                    print(f'{item["output_name"]} 下载完成 {save_path}')
                except Exception as exc:
                    item["download_error"] = str(exc)
                    print(f'{item["output_name"]} 下载失败 {exc}')
            elif status == "failed":
                item["error"] = status_data.get("error")

        save_tasks(tasks)

        if pending == 0:
            print("所有任务都已处理完成")
            return

        time.sleep(10)


if __name__ == "__main__":
    main()
