# Veo

这个目录现在按职责拆分成了独立子目录，方便管理脚本、配置和生成结果。

## 目录结构

- `configs/`：所有 Veo JSON 配置文件
- `scripts/`：所有 Veo Python 脚本
- `outputs/`：所有生成结果与批量任务输出
- `input/`：图生视频等输入素材

## 当前约定

- 默认配置文件：`configs/veo_config.json`
- 默认单条输出目录：`outputs/generated_veo/`
- 默认批量输出目录：`outputs/generated_veo_batch/`
- 默认批量任务文件：`outputs/generated_veo_batch/tasks.json`

## 常用脚本

- `scripts/config_utils.py`：配置加载、默认值合并、提示词拼装、图片输入处理
- `scripts/batch_task_utils.py`：批量任务共用工具，负责读写 `tasks.json`
- `scripts/test.py`：提供 API 默认值来源
- `scripts/generate_veo_video.py`：单条视频生成
- `scripts/check_veo_task.py`：查询任务状态或任务列表
- `scripts/submit_batch_tasks.py`：从 `tasks.json` 读取并批量提交任务
- `scripts/wait_and_retry_batch.py`：轮询批量任务并自动下载/重提
- `scripts/merge_difu_videos.py`：拼接地府游记批量视频

## 常用命令

单条生成：

```bash
cd /mnt/e/ai_work/py/Veo
python3 scripts/generate_veo_video.py --config configs/veo_config.json
```

查询任务状态：

```bash
cd /mnt/e/ai_work/py/Veo
python3 scripts/check_veo_task.py --config configs/veo_config.json --task-id <task_id>
```

查询任务列表：

```bash
cd /mnt/e/ai_work/py/Veo
python3 scripts/check_veo_task.py --config configs/veo_config.json
```

批量提交：

```bash
cd /mnt/e/ai_work/py/Veo
python3 scripts/submit_batch_tasks.py --config configs/veo_config.json
```

批量轮询、下载、失败重提：

```bash
cd /mnt/e/ai_work/py/Veo
python3 scripts/wait_and_retry_batch.py --config configs/veo_config.json
```

拼接地府游记视频：

```bash
cd /mnt/e/ai_work/py/Veo
python3 scripts/merge_difu_videos.py
```

## 使用建议

- 新项目优先新增独立配置文件到 `configs/`，不要反复覆盖默认 `configs/veo_config.json`
- 批量任务不要再把提示词写进 Python，统一写到 `tasks.json`
- 可以参考 `configs/veo_tasks.example.json` 组织任务字段
- 想改模型、比例、提示词、输出文件名时，优先修改 JSON 配置
- 9:16 竖屏短视频直接把 `generation.aspect_ratio` 设为 `9:16`
- 建议始终在 `/mnt/e/ai_work/py/Veo` 根目录执行命令，这样相对路径最稳定
