# Veo

这个目录存放 Veo 视频生成相关脚本、配置和输出文件。

## 当前保留文件

- `veo_config.json`：默认配置文件，适合日常单条生成或批量任务
- `veo_config_difu_9x16.json`：地府题材 9:16 版本配置
- `veo_config_difu_9x16_retry.json`：地府题材精简重试配置
- `veo_config_difu_travel_9x16.json`：地府“异世界旅游”9:16 配置
- `config_utils.py`：配置加载、默认值合并、提示词拼装、图片输入处理
- `test.py`：提供 API 默认值来源，`config_utils.py` 会从这里读取基础参数
- `generate_veo_video.py`：单条视频生成脚本
- `check_veo_task.py`：查询任务状态或任务列表
- `batch_generate_jingang.py`：金刚经批量分镜提示词
- `submit_jingang_batch.py`：批量提交金刚经分镜任务
- `wait_and_retry_batch.py`：轮询批量任务，下载成功结果，并在失败时缩短提示词后重提

## 常用命令

单条生成：

```bash
cd /mnt/e/ai_work/py/Veo
python3 generate_veo_video.py --config veo_config.json
```

查询任务状态：

```bash
cd /mnt/e/ai_work/py/Veo
python3 check_veo_task.py --config veo_config.json --task-id <task_id>
```

查询任务列表：

```bash
cd /mnt/e/ai_work/py/Veo
python3 check_veo_task.py --config veo_config.json
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

## 目录说明

- `generated_veo/`：单条生成视频输出目录
- `generated_veo_batch/`：批量任务输出目录
- `generated_veo_batch_v3fast/`：另一组批量输出目录
- `input/`：图生视频等输入素材目录

## 使用建议

- 优先通过 JSON 配置文件改 `model`、`aspect_ratio`、`prompt`、`negative_prompt`、`output_name` 和 `output_dir`
- 想保留不同项目参数时，直接新增独立配置文件，不要反复覆盖默认 `veo_config.json`
- 如果是 9:16 竖屏短视频，直接把 `generation.aspect_ratio` 设为 `9:16`
