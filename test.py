# -*- coding: utf-8 -*-
import requests
import time
from typing import Optional, Dict, Any

# 配置项（请替换为你的实际信息）
API_KEY = "sk-GlrEijDLTnkpseGkJ7zamMKRFkH2ddbL7Cm1Mnnu67j8NpNo"  # 替换为真实的Bearer Token
BASE_URL = "https://foxi-ai.cn/v1/videos"
TIMEOUT = 300  # 最大等待时间（秒），可根据需求调整
POLL_INTERVAL = 5  # 轮询任务状态的间隔（秒）

class VideoGenerator:
    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {self.api_key}"
        }

    def create_video_task(
        self,
        model: str,
        prompt: str,
        image: Optional[str] = None,
        duration: Optional[int] = 5,
        width: Optional[int] = 1080,
        height: Optional[int] = 1920,
        fps: Optional[int] = 24,
        seed: Optional[int] = None,
        n: Optional[int] = 1,
        response_format: Optional[str] = "json",
        user: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        创建视频生成任务（第一个接口）
        :param model: 模型ID（如sora-2、sora-16:9-720p-5s）
        :param prompt: 文本提示词（必填）
        :param image: 图片URL/Base64（可选，图生视频时用）
        :param duration: 视频时长（秒）
        :param width: 视频宽度
        :param height: 视频高度
        :param fps: 帧率
        :param seed: 随机种子（可选）
        :param n: 生成视频数量
        :param response_format: 响应格式
        :param user: 用户标识
        :param metadata: 扩展参数（如negative_prompt）
        :return: 任务ID（创建成功）/None（失败）
        """
        # 构造请求体（JSON格式，确保数字字段保持为int）
        payload = {
            "model": model,
            "prompt": prompt,
            "duration": duration,
            "width": width,
            "height": height,
            "fps": fps,
            "n": n,
            "response_format": response_format
        }
        # 可选参数补充
        if image:
            payload["image"] = image
        if seed is not None:
            payload["seed"] = seed
        if user:
            payload["user"] = user
        if metadata:
            payload["metadata"] = metadata

        try:
            print(f"开始创建视频任务，模型：{model}，提示词：{prompt}")
            response = requests.post(
                url=self.base_url,
                json=payload,
                headers=self.headers,
                timeout=60
            )
            response.raise_for_status()  # 抛出HTTP错误（4xx/5xx）
            result = response.json()
            task_id = result.get("id")
            
            if not task_id:
                print(f"创建任务失败：未返回任务ID，响应：{result}")
                return None
            
            print(f"任务创建成功，任务ID：{task_id}")
            return task_id

        except requests.exceptions.RequestException as e:
            print(f"创建任务请求失败：{str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"错误响应内容：{e.response.text}")
            return None

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        查询视频任务状态（第二个接口）
        :param task_id: 任务ID
        :return: 任务状态字典/None（失败）
        """
        try:
            url = f"{self.base_url}/{task_id}"
            response = requests.get(
                url=url,
                headers=self.headers,
                timeout=30
            )
            response.raise_for_status()
            status_data = response.json()
            return status_data

        except requests.exceptions.RequestException as e:
            print(f"查询任务{task_id}状态失败：{str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"错误响应内容：{e.response.text}")
            return None

    def download_video(self, task_id: str, save_path: str) -> bool:
        """
        下载视频内容（第三个接口，仅任务完成时调用）
        :param task_id: 任务ID
        :param save_path: 视频保存路径（如./output.mp4）
        :return: True（成功）/False（失败）
        """
        try:
            url = f"{self.base_url}/{task_id}/content"
            print(f"开始下载视频，任务ID：{task_id}，保存路径：{save_path}")
            
            # 流式下载（避免大文件占用内存）
            response = requests.get(
                url=url,
                headers=self.headers,
                stream=True,
                timeout=120
            )
            response.raise_for_status()

            # 写入文件
            with open(save_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            print(f"视频下载完成，已保存至：{save_path}")
            return True

        except requests.exceptions.RequestException as e:
            print(f"下载视频失败：{str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"错误响应内容：{e.response.text}")
            return False

    def wait_for_task_complete(self, task_id: str) -> Optional[str]:
        """
        轮询等待任务完成
        :param task_id: 任务ID
        :return: 任务状态（completed/failed）/None（超时）
        """
        start_time = time.time()
        while time.time() - start_time < TIMEOUT:
            status_data = self.get_task_status(task_id)
            if not status_data:
                time.sleep(POLL_INTERVAL)
                continue
            
            status = status_data.get("status")
            progress = status_data.get("progress", 0)
            print(f"任务进度：{progress}%，状态：{status}")

            # 任务完成/失败
            if status == "completed":
                return "completed"
            elif status == "failed":
                error = status_data.get("error", {})
                print(f"任务失败：{error.get('message', '未知错误')}（错误码：{error.get('code')}）")
                return "failed"
            
            # 任务进行中，继续轮询
            time.sleep(POLL_INTERVAL)
        
        # 超时
        print(f"任务超时（超过{TIMEOUT}秒），任务ID：{task_id}")
        return None

# ==================== 示例：使用封装类生成视频 ====================
if __name__ == "__main__":
    # 初始化生成器
    generator = VideoGenerator(
        api_key=API_KEY,
        base_url=BASE_URL
    )

    # 1. 创建视频任务（以sora-2为例，可替换为其他模型）
    task_id = generator.create_video_task(
        model="sora-2",  # 替换为你要使用的模型ID
        prompt="清晨森林中溪流流动，阳光透过树叶洒落，慢动作运镜，暖色调",  # 文本提示词
        duration=5,  # 视频时长5秒
        width=1080,  # 宽度
        height=1920,  # 高度（9:16竖屏）
        fps=24,  # 帧率
        metadata={  # 扩展参数（示例：负向提示词）
            "negative_prompt": "无多余人物、无模糊画面、无水印",
            "quality_level": "high"
        }
    )

    if not task_id:
        print("创建任务失败，退出程序")
        exit(1)

    # 2. 等待任务完成
    task_status = generator.wait_for_task_complete(task_id)
    if task_status != "completed":
        print("任务未完成，无法下载视频")
        exit(1)

    # 3. 下载视频（保存到本地）
    save_path = f"./generated_video_{task_id}.mp4"
    generator.download_video(
        task_id=task_id,
        save_path=save_path
    )
