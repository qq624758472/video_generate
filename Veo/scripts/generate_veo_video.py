#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""单条 Veo 视频生成脚本。

支持两种模式：
1. 文生视频
2. 图生视频（配置里打开 image_to_video 并传 images）
"""

import argparse
import sys
import time
from pathlib import Path
from typing import Any, Dict

import requests

from config_utils import (
    DEFAULT_CONFIG_PATH,
    build_request_prompt,
    load_config,
    normalize_base_root,
    resolve_image_inputs,
)


DEFAULT_CREATE_ENDPOINT = "/v2/videos/generations"
DEFAULT_STATUS_ENDPOINT = "/v2/videos/generations/{task_id}"
DEFAULT_CONTENT_ENDPOINT = "/v1/videos/{task_id}/content"


class APIError(RuntimeError):
    # 把接口层错误包装成统一异常，主流程里更容易集中处理。
    pass


class VeoVideoClient:
    def __init__(self, api_key: str, base_root: str, timeout: int) -> None:
        # Session 会复用连接，也方便统一挂鉴权头。
        self.base_root = normalize_base_root(base_root)
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
        )

    def create_generation(
        self,
        prompt: str,
        model: str,
        aspect_ratio: str,
        enhance_prompt: bool,
        enable_upsample: bool,
        images: list[str] | None = None,
    ) -> Dict[str, Any]:
        # 创建生成任务。图生视频时额外带上 images 字段。
        payload = {
            "prompt": prompt,
            "model": model,
            "enhance_prompt": enhance_prompt,
            "enable_upsample": enable_upsample,
        }
        if aspect_ratio:
            payload["aspect_ratio"] = aspect_ratio
        if images:
            payload["images"] = images
        response = self.session.post(
            f"{self.base_root}{DEFAULT_CREATE_ENDPOINT}",
            json=payload,
            timeout=self.timeout,
        )
        return self._parse_response(response)

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        # 查询单个任务状态。
        response = self.session.get(
            f"{self.base_root}{DEFAULT_STATUS_ENDPOINT.format(task_id=task_id)}",
            timeout=30,
        )
        return self._parse_response(response)

    def list_generations(self) -> Dict[str, Any]:
        # 查询任务列表，调试或排查时很有用。
        response = self.session.get(
            f"{self.base_root}{DEFAULT_CREATE_ENDPOINT}",
            timeout=30,
        )
        return self._parse_response(response)

    def wait_for_completion(self, task_id: str, poll_interval: int) -> Dict[str, Any]:
        # 轮询直到任务完成、失败或超时。
        start_time = time.time()
        while time.time() - start_time < self.timeout:
            status_data = self.get_task_status(task_id)
            status = str(status_data.get("status", "unknown")).upper()
            progress = status_data.get("progress")
            print(f"任务状态: {status} progress={progress}")

            if status in {"COMPLETED", "SUCCESS", "SUCCEEDED"}:
                return status_data
            if status in {"FAILED", "FAILURE", "ERROR"}:
                raise APIError(f"任务失败: {status_data}")

            time.sleep(poll_interval)

        raise APIError(f"任务超时，task_id={task_id}")

    def download_video(self, task_id: str, save_path: Path) -> None:
        # 任务完成后，通过内容接口把 mp4 流式保存到本地。
        response = self.session.get(
            f"{self.base_root}{DEFAULT_CONTENT_ENDPOINT.format(task_id=task_id)}",
            stream=True,
            timeout=120,
        )
        if response.status_code >= 400:
            raise APIError(f"下载视频失败: HTTP {response.status_code} {self._safe_json(response)}")

        save_path.parent.mkdir(parents=True, exist_ok=True)
        with save_path.open("wb") as output_file:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    output_file.write(chunk)

    @staticmethod
    def _safe_json(response: requests.Response) -> Dict[str, Any]:
        # 某些失败响应不一定是 JSON，这里兜底保留原始文本。
        try:
            data = response.json()
        except ValueError:
            return {"raw_text": response.text}
        return data if isinstance(data, dict) else {"data": data}

    def _parse_response(self, response: requests.Response) -> Dict[str, Any]:
        # 统一在这里把 HTTP 错误转成 Python 异常。
        data = self._safe_json(response)
        if response.status_code >= 400:
            raise APIError(f"HTTP {response.status_code}: {data}")
        return data


def parse_args() -> argparse.Namespace:
    # --no-wait 用于“只提交、不阻塞等待结果”的场景。
    parser = argparse.ArgumentParser(description="使用 Veo 模型生成视频。")
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH, help="外部 JSON 配置文件路径")
    parser.add_argument("--no-wait", action="store_true")
    return parser.parse_args()


def main() -> int:
    # 主流程：读取配置 -> 校验参数 -> 提交任务 -> 视情况等待并下载。
    args = parse_args()
    config = load_config(Path(args.config).expanduser().resolve())
    api = config.get("api", {})
    generation = config.get("generation", {})

    api_key = str(api.get("api_key", "")).strip()
    base_url = normalize_base_root(str(api.get("base_url", "")).strip())
    timeout = int(api.get("timeout", 900))
    poll_interval = int(api.get("poll_interval", 5))
    model = str(generation.get("model", "veo3.1-fast")).strip()
    aspect_ratio = str(generation.get("aspect_ratio", "16:9")).strip()
    enhance_prompt = bool(generation.get("enhance_prompt", False))
    enable_upsample = bool(generation.get("enable_upsample", True))
    image_to_video = bool(generation.get("image_to_video", False))
    images = resolve_image_inputs(list(generation.get("images", [])))
    prompt = build_request_prompt(
        str(generation.get("prompt", "")).strip(),
        str(generation.get("negative_prompt", "")).strip(),
    )
    output_name = str(generation.get("output_name", "veo_video")).strip() or "veo_video"
    output_dir = Path(str(generation.get("output_dir", "outputs/generated_veo")).strip() or "outputs/generated_veo")

    if not api_key:
        print("缺少 API Key", file=sys.stderr)
        return 1
    if not prompt:
        print("缺少 prompt，请在 JSON 配置文件中填写 generation.prompt", file=sys.stderr)
        return 1
    if image_to_video and not images:
        print("已启用图生视频，但 generation.images 为空", file=sys.stderr)
        return 1

    client = VeoVideoClient(api_key=api_key, base_root=base_url, timeout=timeout)

    try:
        # 图生视频会把本地图片路径预处理成 data URL 后再提交。
        result = client.create_generation(
            prompt=prompt,
            model=model,
            aspect_ratio=aspect_ratio if not image_to_video or aspect_ratio else "",
            enhance_prompt=enhance_prompt,
            enable_upsample=enable_upsample,
            images=images if image_to_video else None,
        )
        print(f"创建结果: {result}")
        task_id = str(result.get("id") or result.get("task_id") or "").strip()
        if not task_id:
            print("接口未返回 task_id", file=sys.stderr)
            return 1

        if args.no_wait:
            return 0

        # 非 no-wait 模式下，脚本会一直等到出片后自动下载。
        client.wait_for_completion(task_id, poll_interval)
        output_path = output_dir / f"{output_name}_{task_id}.mp4"
        client.download_video(task_id, output_path)
        print(f"视频已保存: {output_path.resolve()}")
        return 0
    except Exception as exc:
        print(f"执行失败: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
