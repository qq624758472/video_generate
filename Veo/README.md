# Veo

这个目录存放 Veo 视频生成脚本。

常用文件：
- `veo_config.json`：统一参数配置文件
- `config_utils.py`：配置加载与提示词拼装工具
- `test.py`：API Key 和基础基础来源
- `generate_veo_video.py`：通用 Veo 文生视频脚本
- `batch_generate_jingang.py`：金刚经场景提示词
- `run_jing2_test.py`：第二分镜测试脚本
- `submit_jingang_batch.py`：批量提交 9 个分镜任务
- `wait_and_retry_batch.py`：轮询批量任务，成功下载，失败缩短提示词后重提

运行单条生成：

```bash
cd /mnt/e/ai_work/py/Veo
python3 generate_veo_video.py --config veo_config.json
```

批量提交：

```bash
cd /mnt/e/ai_work/py/Veo
python3 submit_jingang_batch.py --config veo_config.json
```

批量轮询、下载、失败重提：

```bash
cd /mnt/e/ai_work/py/Veo
python3 wait_and_retry_batch.py --config veo_config.json
```

说明：
- 提示词和反提示词都改成从 `veo_config.json` 读取
- 可调参数都从 JSON 配置读取
- 后续改参数优先改 JSON，不需要再改 Python 代码
