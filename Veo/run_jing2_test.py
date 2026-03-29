#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pathlib import Path

import batch_generate_jingang as jingang
from config_utils import build_request_prompt, load_config
from generate_veo_video import VeoVideoClient


CONFIG_PATH = "veo_config.json"


def main() -> int:
    config = load_config(Path(__file__).with_name(CONFIG_PATH).resolve())
    api = config.get("api", {})
    generation = config.get("generation", {})
    prompt_style = config.get("prompt_style", {})

    api_key = str(api.get("api_key", "")).strip()
    base_url = str(api.get("base_url", "")).strip()
    timeout = int(api.get("timeout", 900))
    poll_interval = int(api.get("poll_interval", 5))

    if not api_key:
        print("缺少 API Key")
        return 1

    _, scene_prompt = jingang.SCENES[1]
    prompt = build_request_prompt(
        jingang.build_prompt(
            scene_prompt,
            common_style=str(prompt_style.get("common_style", "")).strip(),
            negative_prompt=str(prompt_style.get("negative_prompt", "")).strip(),
        ),
        str(generation.get("negative_prompt", "")).strip(),
    )

    client = VeoVideoClient(api_key=api_key, base_root=base_url, timeout=timeout)
    result = client.create_generation(
        prompt=prompt,
        model=str(generation.get("model", "veo3.1-fast")).strip(),
        aspect_ratio=str(generation.get("aspect_ratio", "16:9")).strip(),
        enhance_prompt=bool(generation.get("enhance_prompt", False)),
        enable_upsample=bool(generation.get("enable_upsample", True)),
    )
    print(f"创建结果: {result}")

    task_id = str(result.get("id") or result.get("task_id") or "").strip()
    if not task_id:
        print("未返回 task_id")
        return 1

    client.wait_for_completion(task_id, poll_interval)
    output_dir = Path(str(generation.get("output_dir", "generated_veo")).strip() or "generated_veo")
    output_name = str(generation.get("output_name", "jing2_test")).strip() or "jing2_test"
    out_path = output_dir / f"{output_name}_{task_id}.mp4"
    client.download_video(task_id, out_path)
    print(f"测试视频已保存: {out_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
