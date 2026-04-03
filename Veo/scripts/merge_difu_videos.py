#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""把地府游记批量生成的视频拼接成一个完整成片。"""

import subprocess
from pathlib import Path

import imageio_ffmpeg


INPUT_DIR = Path("/mnt/e/ai_work/py/Veo/outputs/generated_veo_difu_batch/downloads")
LIST_PATH = Path("/mnt/e/ai_work/py/Veo/outputs/generated_veo_difu_batch/concat_list.txt")
OUTPUT_PATH = Path("/mnt/e/ai_work/py/Veo/outputs/generated_veo_difu_batch/difu_travel_complete.mp4")


def write_concat_list(files: list[Path]) -> None:
    # ffmpeg concat demuxer 需要一个文本文件，逐行列出要拼接的文件。
    lines = [f"file '{path.as_posix()}'" for path in files]
    LIST_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_ffmpeg(args: list[str]) -> subprocess.CompletedProcess[str]:
    # 统一封装，便于后面先尝试 copy，再回退到重新编码。
    return subprocess.run(args, check=False, text=True, capture_output=True)


def main() -> int:
    # 先尝试无损拼接；如果源视频编码参数不一致，再回退到转码拼接。
    files = sorted(INPUT_DIR.glob("difu*.mp4"))
    if not files:
        raise SystemExit("未找到可合成的视频文件")

    write_concat_list(files)
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

    copy_cmd = [
        ffmpeg,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(LIST_PATH),
        "-c",
        "copy",
        str(OUTPUT_PATH),
    ]
    result = run_ffmpeg(copy_cmd)
    if result.returncode == 0:
        print(f"已生成: {OUTPUT_PATH}")
        return 0

    # copy 失败通常是因为分段视频编码参数不完全一致，这时改成重编码。
    reencode_cmd = [
        ffmpeg,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(LIST_PATH),
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "20",
        "-c:a",
        "aac",
        "-movflags",
        "+faststart",
        str(OUTPUT_PATH),
    ]
    result = run_ffmpeg(reencode_cmd)
    if result.returncode != 0:
        raise SystemExit(result.stderr.strip() or "ffmpeg 合成失败")

    print(f"已生成: {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
