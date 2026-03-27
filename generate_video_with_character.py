#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import ast
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

import requests


DEFAULT_BASE_URL = "https://foxi-ai.top/v1/videos"
DEFAULT_CONFIG_PATH = "charactersID.conf"
DEFAULT_MODEL = "sora-2"
DEFAULT_DURATION = 5
DEFAULT_WIDTH = 1080
DEFAULT_HEIGHT = 1920
DEFAULT_FPS = 24
DEFAULT_TIMEOUT = 300
DEFAULT_POLL_INTERVAL = 5
DEFAULT_OUTPUT_NAME = "character_scene"
DEFAULT_PROMPT = "@qzpydhgw.cozyspark standing on a stage, anime style, gentle motion"


class APIError(RuntimeError):
    """Raised when the remote API returns an error response."""


def load_defaults_from_test_py(script_path: Path) -> Dict[str, Any]:
    defaults: Dict[str, Any] = {}
    if not script_path.is_file():
        return defaults

    try:
        tree = ast.parse(script_path.read_text(encoding="utf-8"), filename=str(script_path))
    except (OSError, SyntaxError):
        return defaults

    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue
            if target.id not in {"API_KEY", "BASE_URL"}:
                continue
            try:
                defaults[target.id] = ast.literal_eval(node.value)
            except Exception:
                continue
    return defaults


def load_character_config(config_path: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    if not config_path.is_file():
        return values

    for raw_line in config_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


class VideoGenerator:
    def __init__(self, api_key: str, base_url: str, timeout: int) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {api_key}"})

    def create_video_task(
        self,
        model: str,
        prompt: str,
        duration: int,
        width: int,
        height: int,
        fps: int,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        payload: Dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "duration": duration,
            "width": width,
            "height": height,
            "fps": fps,
            "n": 1,
            "response_format": "json",
        }
        if metadata:
            payload["metadata"] = metadata

        response = self.session.post(
            self.base_url,
            json=payload,
            timeout=self.timeout,
        )
        data = self._parse_response(response)
        task_id = data.get("id")
        if not task_id:
            raise APIError(f"创建任务失败，未返回任务ID: {data}")
        print(f"视频任务创建成功，任务ID: {task_id}")
        return task_id

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        response = self.session.get(
            f"{self.base_url}/{task_id}",
            timeout=30,
        )
        return self._parse_response(response)

    def wait_for_task_complete(self, task_id: str, poll_interval: int) -> None:
        start_time = time.time()
        while time.time() - start_time < self.timeout:
            status_data = self.get_task_status(task_id)
            status = status_data.get("status")
            progress = status_data.get("progress", 0)
            print(f"任务进度: {progress}%，状态: {status}")

            if status == "completed":
                return
            if status == "failed":
                error = status_data.get("error", {})
                raise APIError(
                    f"任务失败: {error.get('message', '未知错误')}（错误码: {error.get('code')}）"
                )

            time.sleep(poll_interval)

        raise APIError(f"任务超时，任务ID: {task_id}")

    def download_video(self, task_id: str, save_path: Path) -> None:
        response = self.session.get(
            f"{self.base_url}/{task_id}/content",
            stream=True,
            timeout=120,
        )
        if response.status_code >= 400:
            raise APIError(f"下载视频失败: HTTP {response.status_code} {self._safe_json(response)}")

        with save_path.open("wb") as output_file:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    output_file.write(chunk)

    @staticmethod
    def _safe_json(response: requests.Response) -> Dict[str, Any]:
        try:
            data = response.json()
        except ValueError:
            return {"raw_text": response.text}
        return data if isinstance(data, dict) else {"data": data}

    def _parse_response(self, response: requests.Response) -> Dict[str, Any]:
        data = self._safe_json(response)
        if response.status_code >= 400:
            raise APIError(f"HTTP {response.status_code}: {data}")
        return data


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="使用已创建角色的 @username 生成下一段视频。")
    parser.add_argument("--api-key", default="", help="API Key，优先级高于环境变量")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="视频接口地址")
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH, help="角色配置文件")
    parser.add_argument("--username", default="", help="角色 username，不传则从配置文件读取")
    parser.add_argument("--prompt", default="", help="完整提示词；不传则基于 username 生成默认提示词")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="视频模型名")
    parser.add_argument("--duration", type=int, default=DEFAULT_DURATION, help="视频时长")
    parser.add_argument("--width", type=int, default=DEFAULT_WIDTH, help="视频宽度")
    parser.add_argument("--height", type=int, default=DEFAULT_HEIGHT, help="视频高度")
    parser.add_argument("--fps", type=int, default=DEFAULT_FPS, help="视频帧率")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="请求超时")
    parser.add_argument("--poll-interval", type=int, default=DEFAULT_POLL_INTERVAL, help="轮询间隔")
    parser.add_argument("--output-name", default=DEFAULT_OUTPUT_NAME, help="输出视频文件标识")
    parser.add_argument("--negative-prompt", default="", help="可选 negative_prompt")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    test_defaults = load_defaults_from_test_py(Path(__file__).with_name("test.py"))
    config_values = load_character_config(Path(args.config).expanduser().resolve())

    api_key = args.api_key or os.environ.get("OPENAI_API_KEY") or os.environ.get("SORA_API_KEY") or test_defaults.get("API_KEY", "")
    if not api_key:
        print("缺少 API Key。", file=sys.stderr)
        return 1

    base_url = args.base_url
    test_base_url = str(test_defaults.get("BASE_URL", "")).strip()
    if args.base_url == DEFAULT_BASE_URL and test_base_url:
        base_url = test_base_url

    username = args.username or config_values.get("USERNAME", "") or "qzpydhgw.cozyspark"
    prompt = args.prompt or f"@{username} standing on a stage, anime style, gentle motion"

    metadata: Dict[str, Any] = {"quality_level": "high"}
    if args.negative_prompt:
        metadata["negative_prompt"] = args.negative_prompt

    generator = VideoGenerator(api_key=api_key, base_url=base_url, timeout=args.timeout)

    try:
        task_id = generator.create_video_task(
            model=args.model,
            prompt=prompt,
            duration=args.duration,
            width=args.width,
            height=args.height,
            fps=args.fps,
            metadata=metadata,
        )
        generator.wait_for_task_complete(task_id, args.poll_interval)
        save_path = Path(f"./generated_video_{args.output_name}_{task_id}.mp4").resolve()
        generator.download_video(task_id, save_path)
        print(f"提示词: {prompt}")
        print(f"视频已保存: {save_path}")
        return 0
    except (APIError, requests.RequestException) as exc:
        print(f"生成视频失败: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
