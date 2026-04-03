#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
from pathlib import Path

from config_utils import DEFAULT_CONFIG_PATH, load_config
from generate_veo_video import VeoVideoClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="查询 Veo 任务状态或任务列表。")
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH, help="外部 JSON 配置文件路径")
    parser.add_argument("--task-id", default="", help="任务 ID；不传则查询任务列表")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config(Path(args.config).expanduser().resolve())
    api = config.get("api", {})
    client = VeoVideoClient(
        api_key=str(api.get("api_key", "")).strip(),
        base_root=str(api.get("base_url", "")).strip(),
        timeout=int(api.get("timeout", 900)),
    )
    if args.task_id:
        data = client.get_task_status(args.task_id)
    else:
        data = client.list_generations()
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
