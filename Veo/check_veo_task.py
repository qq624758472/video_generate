#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
from pathlib import Path

from generate_veo_video import VeoVideoClient, load_defaults_from_test_py, normalize_base_root


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="查询 Veo 任务状态或任务列表。")
    parser.add_argument("--task-id", default="", help="任务 ID；不传则查询任务列表")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    defaults = load_defaults_from_test_py(Path(__file__).with_name("test.py"))
    api_key = str(defaults.get("API_KEY", "")).strip()
    base_url = normalize_base_root(str(defaults.get("BASE_URL", "")).strip())
    timeout = int(defaults.get("TIMEOUT", 900))

    client = VeoVideoClient(api_key=api_key, base_root=base_url, timeout=timeout)
    if args.task_id:
        data = client.get_task_status(args.task_id)
    else:
        data = client.list_generations()
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
