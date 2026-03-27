# UI

这个目录存放基于 Qt Python 编写的图形界面版本。

包含内容：
- `app.py`：主界面入口
- `ui_backend.py`：界面层调用封装，统一连接 `sora`、`Veo`、`keling`

运行方式：

```bash
cd /mnt/e/ai_work/py/UI
python3 app.py
```

界面功能：
- Sora 文生视频
- Veo 文生视频
- 可灵文生视频
- 按任务 ID 查询状态
- 实时任务历史列表
- 关闭后重开自动读取历史
- 上次未完成的任务会自动继续查询状态

生成的视频默认保存到：

```bash
/mnt/e/ai_work/py/UI/generated/
```

任务历史默认保存到：

```bash
/mnt/e/ai_work/py/UI/task_history.json
```
