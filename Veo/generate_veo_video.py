#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import ast
import sys
import time
from pathlib import Path
from typing import Any, Dict

import requests


DEFAULT_BASE_URL = "https://foxi-ai.top"
DEFAULT_CREATE_ENDPOINT = "/v2/videos/generations"
DEFAULT_STATUS_ENDPOINT = "/v2/videos/generations/{task_id}"
DEFAULT_CONTENT_ENDPOINT = "/v1/videos/{task_id}/content"
DEFAULT_MODEL = "veo3.1-fast"
DEFAULT_ASPECT_RATIO = "16:9"
DEFAULT_TIMEOUT = 900
DEFAULT_POLL_INTERVAL = 5


class APIError(RuntimeError):
    pass


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
            if target.id not in {"API_KEY", "BASE_URL", "TIMEOUT", "POLL_INTERVAL"}:
                continue
            try:
                defaults[target.id] = ast.literal_eval(node.value)
            except Exception:
                continue
    return defaults


def normalize_base_root(base_url: str) -> str:
    base_url = base_url.rstrip("/")
    if base_url.endswith("/v1/videos"):
        return base_url[: -len("/v1/videos")]
    return base_url


class VeoVideoClient:
    def __init__(self, api_key: str, base_root: str, timeout: int) -> None:
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
    ) -> Dict[str, Any]:
        payload = {
            "prompt": prompt,
            "model": model,
            "aspect_ratio": aspect_ratio,
            "enhance_prompt": enhance_prompt,
            "enable_upsample": enable_upsample,
        }
        response = self.session.post(
            f"{self.base_root}{DEFAULT_CREATE_ENDPOINT}",
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

    def list_generations(self) -> Dict[str, Any]:
        response = self.session.get(
            f"{self.base_root}{DEFAULT_CREATE_ENDPOINT}",
            timeout=30,
        )
        return self._parse_response(response)

    def wait_for_completion(self, task_id: str, poll_interval: int) -> Dict[str, Any]:
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
    defaults = load_defaults_from_test_py(Path(__file__).with_name("test.py"))
    parser = argparse.ArgumentParser(description="使用 Veo 模型生成视频。")
    parser.add_argument("--api-key", default=str(defaults.get("API_KEY", "")).strip())
    parser.add_argument(
        "--base-url",
        default=normalize_base_root(str(defaults.get("BASE_URL", DEFAULT_BASE_URL)).strip() or DEFAULT_BASE_URL),
    )
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--aspect-ratio", default=DEFAULT_ASPECT_RATIO, choices=("16:9", "9:16"))
    parser.add_argument("--enhance-prompt", action="store_true")
    parser.add_argument("--enable-upsample", action="store_true")
    parser.add_argument("--timeout", type=int, default=int(defaults.get("TIMEOUT", DEFAULT_TIMEOUT)))
    parser.add_argument("--poll-interval", type=int, default=int(defaults.get("POLL_INTERVAL", DEFAULT_POLL_INTERVAL)))
    parser.add_argument("--output", default="")
    parser.add_argument("--no-wait", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.api_key:
        print("缺少 API Key", file=sys.stderr)
        return 1

    client = VeoVideoClient(api_key=args.api_key, base_root=args.base_url, timeout=args.timeout)

    try:
        result = client.create_generation(
            prompt=args.prompt,
            model=args.model,
            aspect_ratio=args.aspect_ratio,
            enhance_prompt=args.enhance_prompt,
            enable_upsample=args.enable_upsample,
        )
        print(f"创建结果: {result}")
        task_id = str(result.get("id") or result.get("task_id") or "").strip()
        if not task_id:
            print("接口未返回 task_id", file=sys.stderr)
            return 1

        if args.no_wait:
            return 0

        client.wait_for_completion(task_id, args.poll_interval)
        output_path = Path(args.output) if args.output else Path("generated_veo") / f"{task_id}.mp4"
        client.download_video(task_id, output_path)
        print(f"视频已保存: {output_path.resolve()}")
        return 0
    except Exception as exc:
        print(f"执行失败: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
