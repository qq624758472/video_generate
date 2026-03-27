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
from typing import Any, Dict, Optional

import requests


DEFAULT_BASE_URL = "https://foxi-ai.top"
DEFAULT_IMAGE_PATH = "20260324105357_54_88.jpg"
DEFAULT_CONFIG_PATH = "charactersID.conf"
DEFAULT_VIDEO_PATH = "character_source_video.mp4"
DEFAULT_MODEL = "sora-characters"
DEFAULT_PROMPT = (
    "Create a stable short video of the subject in 2D anime style. "
    "The character must look like an illustration with clear cel shading and must not look like a real human. "
    "Keep the same subject consistent, centered, with no cuts, no extra subjects, and only gentle natural motion."
)
DEFAULT_TIMESTAMPS = "1,2"
DEFAULT_DURATION = 5
DEFAULT_WIDTH = 1080
DEFAULT_HEIGHT = 1920
DEFAULT_FPS = 24
DEFAULT_TIMEOUT = 300
DEFAULT_POLL_INTERVAL = 5


class APIError(RuntimeError):
    """Raised when the remote API returns an error response."""


def prepare_image_input(image_path: Path) -> str:
    mime_type, _ = mimetypes.guess_type(image_path.name)
    mime_type = mime_type or "image/jpeg"
    encoded = base64.b64encode(image_path.read_bytes()).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"


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


def first_non_empty_string(*values: Any) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def extract_video_url(task_data: Dict[str, Any], base_url: str, task_id: str) -> str:
    data = task_data.get("data")
    nested = data if isinstance(data, dict) else {}
    return first_non_empty_string(
        task_data.get("url"),
        task_data.get("video_url"),
        task_data.get("content_url"),
        nested.get("url"),
        nested.get("video_url"),
        nested.get("content_url"),
        f"{base_url.rstrip('/')}/v1/videos/{task_id}/content",
    )


class SoraCharacterClient:
    def __init__(self, api_key: str, base_url: str, timeout: int) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
        )

    def create_video_task(
        self,
        model: str,
        prompt: str,
        image: str,
        duration: int,
        width: int,
        height: int,
        fps: int,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        payload: Dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "image": image,
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
            f"{self.base_url}/v1/videos",
            json=payload,
            timeout=self.timeout,
        )
        data = self._parse_response(response)
        print(f"创建视频任务响应: {data}", file=sys.stderr, flush=True)
        task_id = data.get("id")
        if not task_id:
            raise APIError(f"视频任务创建成功但未返回任务ID: {data}")
        return task_id

    def get_video_task(self, task_id: str) -> Dict[str, Any]:
        response = self.session.get(
            f"{self.base_url}/v1/videos/{task_id}",
            timeout=self.timeout,
        )
        return self._parse_response(response)

    def download_video(self, video_url: str, output_path: Path) -> None:
        response = self.session.get(video_url, timeout=self.timeout, stream=True)
        if response.status_code >= 400:
            raise APIError(f"下载视频失败: HTTP {response.status_code} {self._safe_json(response)}")

        with output_path.open("wb") as output_file:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    output_file.write(chunk)

    def wait_for_video_task(self, task_id: str, poll_interval: int) -> Dict[str, Any]:
        while True:
            data = self.get_video_task(task_id)
            status = data.get("status")
            progress = data.get("progress", 0)
            print(f"任务 {task_id} 状态: {status}, 进度: {progress}%")

            if status == "completed":
                return data
            if status == "failed":
                error = data.get("error") or {}
                raise APIError(
                    f"视频任务失败: {error.get('code', 'unknown')} {error.get('message', data)}"
                )

            time.sleep(poll_interval)

    def create_character(self, timestamps: str, url: str = "", from_task: str = "") -> Dict[str, Any]:
        payload: Dict[str, Any] = {"timestamps": timestamps}
        if not url and not from_task:
            raise ValueError("url 和 from_task 至少要提供一个")
        if url:
            payload["url"] = url
        if from_task:
            payload["from_task"] = from_task
        print(f"创建角色请求体: {payload}", file=sys.stderr, flush=True)

        response = self.session.post(
            f"{self.base_url}/sora/v1/characters",
            json=payload,
            timeout=self.timeout,
        )
        data = self._parse_response(response)
        print(f"创建角色响应: {data}", file=sys.stderr, flush=True)
        return data

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
            error = data.get("error")
            if isinstance(error, dict):
                raise APIError(
                    f"HTTP {response.status_code} {error.get('code', 'unknown')}: "
                    f"{error.get('message', data)}"
                )
            raise APIError(f"HTTP {response.status_code}: {data}")
        return data


def save_character_id(config_path: Path, character_id: str) -> None:
    config_path.write_text(f"CHARACTER_ID={character_id}\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="使用本地图片生成视频任务，再调用 /sora/v1/characters 创建角色。"
    )
    parser.add_argument("--image", default=DEFAULT_IMAGE_PATH, help="本地图片路径")
    parser.add_argument("--api-key", default="", help="API Key，优先级高于环境变量")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="API 基础地址")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="创建视频任务使用的模型名")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT, help="视频任务提示词")
    parser.add_argument("--timestamps", default=DEFAULT_TIMESTAMPS, help="角色截取时间段，如 1,2")
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH, help="角色 ID 保存文件")
    parser.add_argument("--video-path", default=DEFAULT_VIDEO_PATH, help="下载视频到本地的文件路径")
    parser.add_argument("--duration", type=int, default=DEFAULT_DURATION, help="视频时长")
    parser.add_argument("--width", type=int, default=DEFAULT_WIDTH, help="视频宽度")
    parser.add_argument("--height", type=int, default=DEFAULT_HEIGHT, help="视频高度")
    parser.add_argument("--fps", type=int, default=DEFAULT_FPS, help="视频帧率")
    parser.add_argument(
        "--negative-prompt",
        default="",
        help="可选的 negative_prompt，会放到 metadata 中",
    )
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="单次请求超时秒数")
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=DEFAULT_POLL_INTERVAL,
        help="查询视频任务状态的轮询间隔秒数",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    test_defaults = load_defaults_from_test_py(Path(__file__).with_name("test.py"))

    api_key = (
        args.api_key
        or os.environ.get("OPENAI_API_KEY")
        or os.environ.get("SORA_API_KEY")
        or test_defaults.get("API_KEY", "")
    )
    if not api_key:
        print("缺少 API Key，请先设置 OPENAI_API_KEY 或 SORA_API_KEY。", file=sys.stderr)
        return 1

    base_url = args.base_url
    test_base_url = str(test_defaults.get("BASE_URL", "")).strip()
    if args.base_url == DEFAULT_BASE_URL and test_base_url:
        if test_base_url.endswith("/v1/videos"):
            base_url = test_base_url[: -len("/v1/videos")]
        else:
            base_url = test_base_url.rstrip("/")

    image_path = Path(args.image).expanduser().resolve()
    if not image_path.is_file():
        print(f"图片不存在: {image_path}", file=sys.stderr)
        return 1

    config_path = Path(args.config).expanduser().resolve()
    video_path = Path(args.video_path).expanduser().resolve()
    client = SoraCharacterClient(
        api_key=api_key,
        base_url=base_url,
        timeout=args.timeout,
    )

    metadata: Dict[str, Any] = {"quality_level": "high"}
    if args.negative_prompt:
        metadata["negative_prompt"] = args.negative_prompt

    try:
        print(f"读取本地图片: {image_path}")
        prepared_image = prepare_image_input(image_path)

        print(f"创建视频任务，模型: {args.model}")
        task_id = client.create_video_task(
            model=args.model,
            prompt=args.prompt,
            image=prepared_image,
            duration=args.duration,
            width=args.width,
            height=args.height,
            fps=args.fps,
            metadata=metadata,
        )
        print(f"视频任务创建成功，任务ID: {task_id}", file=sys.stderr, flush=True)

        task_data = client.wait_for_video_task(task_id, args.poll_interval)
        print("视频任务已完成，开始创建角色")
        video_url = extract_video_url(task_data, base_url, task_id)
        print(f"下载视频到本地: {video_path}")
        client.download_video(video_url, video_path)
        print(f"视频已保存: {video_path}")

        character = client.create_character(
            timestamps=args.timestamps,
            url=video_url,
            from_task=task_id,
        )
        character_id = character.get("id")
        if not character_id:
            raise APIError(f"角色创建成功但未返回角色ID: {character}")

        save_character_id(config_path, character_id)
        print(f"Character ID: {character_id}")
        print(f"已写入文件: {config_path}")
        return 0
    except (APIError, requests.RequestException, ValueError) as exc:
        print(f"创建角色失败: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
