#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""查询 Veo 任务状态。

传入 task_id 时查询单个任务；不传时列出当前账号下的任务列表。
"""

import argparse
import json
from pathlib import Path

from config_utils import DEFAULT_CONFIG_PATH, load_config
from generate_veo_video import VeoVideoClient


def parse_args() -> argparse.Namespace:
    # 保持命令行很轻量，只需要配置文件和可选 task_id。
    parser = argparse.ArgumentParser(description="查询 Veo 任务状态或任务列表。")
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH, help="外部 JSON 配置文件路径")
    parser.add_argument("--task-id", default="", help="任务 ID；不传则查询任务列表")
    return parser.parse_args()


def main() -> int:
    # 配置里主要读取 API Key、Base URL、超时等公共参数。
    args = parse_args()
    config = load_config(Path(args.config).expanduser().resolve())
    api = config.get("api", {})
    client = VeoVideoClient(
        api_key=str(api.get("api_key", "")).strip(),
        base_root=str(api.get("base_url", "")).strip(),
        timeout=int(api.get("timeout", 900)),
    )
    if args.task_id:
        # 查单个任务时，返回值通常会包含状态、进度、失败原因等信息。
        data = client.get_task_status(args.task_id)
    else:
        # 不传 task_id 时，直接让服务端返回任务列表。
        data = client.list_generations()
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
