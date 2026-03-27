#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import ast
import base64
import mimetypes
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests


DEFAULT_CONFIG_PATH = "charactersID.conf"
DEFAULT_BASE_URL = "https://foxi-ai.top"
DEFAULT_ENDPOINT = "/v2/videos/generations"
DEFAULT_STATUS_ENDPOINT = "/v1/videos/{task_id}"
DEFAULT_CONTENT_ENDPOINT = "/v1/videos/{task_id}/content"
DEFAULT_MODEL = "sora-2"
DEFAULT_ASPECT_RATIO = "16:9"
DEFAULT_DURATION = "10"
DEFAULT_TIMEOUT = 300
DEFAULT_POLL_INTERVAL = 5
DEFAULT_OUTPUT_NAME = "cameo_scene"
DEFAULT_PROMPT = "@qzpydhgw.cozyspark appears in the scene in anime style"
DEFAULT_CHARACTER_TIMESTAMPS = "1,2"


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


def load_key_value_config(config_path: Path) -> Dict[str, str]:
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


def to_data_url(value: str) -> str:
    if value.startswith(("http://", "https://", "data:")):
        return value

    path = Path(value).expanduser().resolve()
    if not path.is_file():
        return value

    mime_type, _ = mimetypes.guess_type(path.name)
    mime_type = mime_type or "image/jpeg"
    encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"


def normalize_base_root(base_url: str) -> str:
    base_url = base_url.rstrip("/")
    if base_url.endswith("/v1/videos"):
        return base_url[: -len("/v1/videos")]
    return base_url


class CameoVideoClient:
    def __init__(self, api_key: str, base_root: str, timeout: int) -> None:
        self.base_root = base_root.rstrip("/")
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
        images: List[str],
        aspect_ratio: str,
        hd: bool,
        duration: str,
        notify_hook: str,
        watermark: bool,
        private: bool,
        character_url: str,
        character_timestamps: str,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "prompt": prompt,
            "model": model,
            "aspect_ratio": aspect_ratio,
            "hd": hd,
            "duration": duration,
            "watermark": watermark,
            "private": private,
        }
        if images:
            payload["images"] = images
        if notify_hook:
            payload["notify_hook"] = notify_hook
        if character_url:
            payload["character_url"] = character_url
        if character_timestamps:
            payload["character_timestamps"] = character_timestamps

        response = self.session.post(
            f"{self.base_root}{DEFAULT_ENDPOINT}",
            json=payload,
            timeout=self.timeout,
        )
        return self._parse_response(response)

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        response = self.session.get(
            f"{self.base_root}{DEFAULT_STATUS_ENDPOINT.format(task_id=task_id)}",
            timeout=30,
        )
        return self._parse_response(response)

    def wait_for_completion(self, task_id: str, poll_interval: int) -> Dict[str, Any]:
        start_time = time.time()
        while time.time() - start_time < self.timeout:
            status_data = self.get_task_status(task_id)
            status = status_data.get("status")
            progress = status_data.get("progress", 0)
            print(f"任务进度: {progress}%，状态: {status}")

            if status == "completed":
                return status_data
            if status == "failed":
                error = status_data.get("error", {})
                raise APIError(
                    f"任务失败: {error.get('message', '未知错误')}（错误码: {error.get('code')}）"
                )

            time.sleep(poll_interval)

        raise APIError(f"任务超时，任务ID: {task_id}")

    def download_video(self, task_id: str, save_path: Path) -> None:
        response = self.session.get(
            f"{self.base_root}{DEFAULT_CONTENT_ENDPOINT.format(task_id=task_id)}",
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
    parser = argparse.ArgumentParser(description="调用 /v2/videos/generations 生成角色客串视频。")
    parser.add_argument("--api-key", default="", help="API Key，优先级高于环境变量")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="服务基础地址，例如 https://foxi-ai.top")
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH, help="角色配置文件")
    parser.add_argument("--prompt", default="", help="完整提示词；不传则自动基于配置里的 USERNAME 生成")
    parser.add_argument("--model", default=DEFAULT_MODEL, choices=("sora-2", "sora-2-pro"), help="模型名")
    parser.add_argument("--images", nargs="*", default=[], help="可选图片列表，支持 URL、本地路径、data URL")
    parser.add_argument("--aspect-ratio", default=DEFAULT_ASPECT_RATIO, choices=("16:9", "9:16"), help="输出比例")
    parser.add_argument("--hd", action="store_true", help="是否高清，仅 sora-2-pro 支持")
    parser.add_argument("--duration", default=DEFAULT_DURATION, choices=("10", "15", "25"), help="视频时长")
    parser.add_argument("--notify-hook", default="", help="回调地址")
    parser.add_argument("--watermark", action="store_true", help="生成带水印视频")
    parser.add_argument("--private", action="store_true", help="生成私有视频")
    parser.add_argument("--character-url", default="", help="角色视频 URL")
    parser.add_argument(
        "--character-timestamps",
        default=DEFAULT_CHARACTER_TIMESTAMPS,
        help="角色出现时间范围，例如 1,2",
    )
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="请求总超时秒数")
    parser.add_argument("--poll-interval", type=int, default=DEFAULT_POLL_INTERVAL, help="轮询间隔秒数")
    parser.add_argument("--output-name", default=DEFAULT_OUTPUT_NAME, help="输出文件标识")
    parser.add_argument("--no-wait", action="store_true", help="只创建任务，不等待完成")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    test_defaults = load_defaults_from_test_py(Path(__file__).with_name("test.py"))
    config_values = load_key_value_config(Path(args.config).expanduser().resolve())

    api_key = (
        args.api_key
        or os.environ.get("OPENAI_API_KEY")
        or os.environ.get("SORA_API_KEY")
        or str(test_defaults.get("API_KEY", "")).strip()
    )
    if not api_key:
        print("缺少 API Key。", file=sys.stderr)
        return 1

    base_url = args.base_url
    test_base_url = str(test_defaults.get("BASE_URL", "")).strip()
    if args.base_url == DEFAULT_BASE_URL and test_base_url:
        base_url = normalize_base_root(test_base_url)

    username = config_values.get("USERNAME", "").strip()
    prompt = args.prompt or (
        f"@{username} appears in the scene in anime style" if username else DEFAULT_PROMPT
    )
    images = [to_data_url(item) for item in args.images]

    client = CameoVideoClient(api_key=api_key, base_root=base_url, timeout=args.timeout)

    try:
        result = client.create_generation(
            prompt=prompt,
            model=args.model,
            images=images,
            aspect_ratio=args.aspect_ratio,
            hd=args.hd,
            duration=args.duration,
            notify_hook=args.notify_hook,
            watermark=args.watermark,
            private=args.private,
            character_url=args.character_url,
            character_timestamps=args.character_timestamps,
        )
        print(f"创建响应: {result}")

        task_id = str(result.get("id") or result.get("task_id") or "").strip()
        if not task_id:
            print("未返回任务ID，已输出原始响应。")
            return 0

        if args.no_wait:
            print(f"任务ID: {task_id}")
            return 0

        client.wait_for_completion(task_id, args.poll_interval)
        save_path = Path(f"./generated_video_{args.output_name}_{task_id}.mp4").resolve()
        client.download_video(task_id, save_path)
        print(f"提示词: {prompt}")
        print(f"视频已保存: {save_path}")
        return 0
    except (APIError, requests.RequestException) as exc:
        print(f"生成角色客串视频失败: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
