#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pathlib import Path

import batch_generate_jingang as jingang
from generate_veo_video import VeoVideoClient, load_defaults_from_test_py, normalize_base_root


MODEL_NAME = "veo3.1-fast"
OUTPUT_NAME = "jing2_test"


def main() -> int:
    defaults = load_defaults_from_test_py(Path(__file__).with_name("test.py"))
    api_key = str(defaults.get("API_KEY", "")).strip()
    base_url = normalize_base_root(str(defaults.get("BASE_URL", "")).strip())
    timeout = int(defaults.get("TIMEOUT", 900))
    poll_interval = int(defaults.get("POLL_INTERVAL", 5))

    if not api_key:
        print("缺少 API Key")
        return 1

    _, prompt = jingang.get_scene("jing2")
    client = VeoVideoClient(api_key=api_key, base_root=base_url, timeout=timeout)
    result = client.create_generation(
        prompt=prompt,
        model=MODEL_NAME,
        aspect_ratio="16:9",
        enhance_prompt=False,
        enable_upsample=True,
    )
    print(f"创建结果: {result}")

    task_id = str(result.get("id") or result.get("task_id") or "").strip()
    if not task_id:
        print("未返回 task_id")
        return 1

    client.wait_for_completion(task_id, poll_interval)
    out_dir = Path("generated_veo")
    out_path = out_dir / f"{OUTPUT_NAME}_{task_id}.mp4"
    client.download_video(task_id, out_path)
    print(f"测试视频已保存: {out_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
