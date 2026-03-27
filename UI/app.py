#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from PyQt6.QtCore import QThread, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import ui_backend


TASKS_PATH = Path(__file__).with_name("task_history.json")


class SubmitThread(QThread):
    done_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(str)

    def __init__(self, fn: Callable[..., dict], kwargs: dict[str, Any]) -> None:
        super().__init__()
        self.fn = fn
        self.kwargs = kwargs

    def run(self) -> None:
        try:
            result = self.fn(**self.kwargs)
            self.done_signal.emit(result)
        except Exception as exc:
            self.error_signal.emit(f"{exc}\n\n{traceback.format_exc()}")


class RefreshThread(QThread):
    done_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(str, str)

    def __init__(self, record: dict[str, Any]) -> None:
        super().__init__()
        self.record = dict(record)

    def run(self) -> None:
        task_id = str(self.record.get("task_id", ""))
        try:
            result = ui_backend.refresh_task_record(self.record)
            self.done_signal.emit(result)
        except Exception as exc:
            self.error_signal.emit(task_id, f"{exc}\n\n{traceback.format_exc()}")


class QueryThread(QThread):
    done_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(str)

    def __init__(self, provider: str, kwargs: dict[str, Any]) -> None:
        super().__init__()
        self.provider = provider
        self.kwargs = kwargs

    def run(self) -> None:
        try:
            result = ui_backend.query_task_status(self.provider, **self.kwargs)
            self.done_signal.emit(result)
        except Exception as exc:
            self.error_signal.emit(f"{exc}\n\n{traceback.format_exc()}")


class ProviderTab(QWidget):
    def __init__(self, title: str, submit_callback: Callable[[dict[str, Any]], None]) -> None:
        super().__init__()
        self.title = title
        self.submit_callback = submit_callback
        self.thread: SubmitThread | None = None
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(12, 12, 12, 12)
        self.layout.setSpacing(12)

        self.form_group = QGroupBox(f"{title} 参数")
        self.form_layout = QFormLayout(self.form_group)
        self.form_layout.setSpacing(10)
        self.layout.addWidget(self.form_group)

        self.button_row = QHBoxLayout()
        self.run_button = QPushButton(f"提交 {title} 任务")
        self.button_row.addWidget(self.run_button)
        self.button_row.addStretch(1)
        self.layout.addLayout(self.button_row)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.layout.addWidget(self.log_output, 1)

    def append_log(self, text: str) -> None:
        self.log_output.append(text)

    def set_log_text(self, text: str) -> None:
        self.log_output.setPlainText(text)

    def set_busy(self, busy: bool) -> None:
        self.run_button.setEnabled(not busy)

    def has_running_thread(self) -> bool:
        return self.thread is not None and self.thread.isRunning()


class SoraTab(ProviderTab):
    def __init__(self, submit_callback: Callable[[dict[str, Any]], None]) -> None:
        super().__init__("Sora", submit_callback)
        defaults = ui_backend.load_sora_defaults()

        self.api_key = QLineEdit(str(defaults.get("API_KEY", "")))
        self.base_url = QLineEdit(str(defaults.get("BASE_URL", "")))
        self.prompt = QPlainTextEdit()
        self.prompt.setPlainText(
            "A calm monk standing in a quiet temple courtyard at sunrise, realistic cinematic style, gentle motion"
        )
        self.model = QComboBox()
        self.model.addItems(["sora-2", "sora-2-pro"])
        self.duration = QSpinBox()
        self.duration.setRange(1, 60)
        self.duration.setValue(5)
        self.width = QSpinBox()
        self.width.setRange(256, 4096)
        self.width.setValue(1280)
        self.height = QSpinBox()
        self.height.setRange(256, 4096)
        self.height.setValue(720)
        self.fps = QSpinBox()
        self.fps.setRange(1, 60)
        self.fps.setValue(24)
        self.timeout = QSpinBox()
        self.timeout.setRange(30, 7200)
        self.timeout.setValue(int(defaults.get("TIMEOUT", 300)))
        self.poll_interval = QSpinBox()
        self.poll_interval.setRange(1, 120)
        self.poll_interval.setValue(int(defaults.get("POLL_INTERVAL", 5)))
        self.output_name = QLineEdit("sora_ui_test")
        self.negative_prompt = QLineEdit()

        self.form_layout.addRow("API Key", self.api_key)
        self.form_layout.addRow("Base URL", self.base_url)
        self.form_layout.addRow("任务名称", self.output_name)
        self.form_layout.addRow("Prompt", self.prompt)
        self.form_layout.addRow("Model", self.model)
        self.form_layout.addRow("Duration", self.duration)
        self.form_layout.addRow("Width", self.width)
        self.form_layout.addRow("Height", self.height)
        self.form_layout.addRow("FPS", self.fps)
        self.form_layout.addRow("Timeout", self.timeout)
        self.form_layout.addRow("Poll Interval", self.poll_interval)
        self.form_layout.addRow("Negative Prompt", self.negative_prompt)

        self.run_button.clicked.connect(self.start_task)

    def start_task(self) -> None:
        self.log_output.clear()
        kwargs = {
            "api_key": self.api_key.text().strip(),
            "base_url": self.base_url.text().strip(),
            "prompt": self.prompt.toPlainText().strip(),
            "model": self.model.currentText(),
            "duration": self.duration.value(),
            "width": self.width.value(),
            "height": self.height.value(),
            "fps": self.fps.value(),
            "timeout": self.timeout.value(),
            "poll_interval": self.poll_interval.value(),
            "output_name": self.output_name.text().strip(),
            "negative_prompt": self.negative_prompt.text().strip(),
        }
        self.thread = SubmitThread(ui_backend.submit_sora_generation, kwargs)
        self.thread.done_signal.connect(self.on_done)
        self.thread.error_signal.connect(self.on_error)
        self.thread.finished.connect(self.on_thread_finished)
        self.set_busy(True)
        self.append_log("正在提交 Sora 任务...")
        self.thread.start()

    def on_done(self, result: dict) -> None:
        self.append_log(f"任务已提交: {result['task_id']}")
        self.submit_callback(result)
        self.set_busy(False)

    def on_error(self, message: str) -> None:
        self.append_log(message)
        self.set_busy(False)

    def on_thread_finished(self) -> None:
        self.thread = None


class VeoTab(ProviderTab):
    def __init__(self, submit_callback: Callable[[dict[str, Any]], None]) -> None:
        super().__init__("Veo", submit_callback)
        defaults = ui_backend.load_veo_defaults()

        self.api_key = QLineEdit(str(defaults.get("API_KEY", "")))
        self.base_url = QLineEdit(ui_backend.normalize_base_root(str(defaults.get("BASE_URL", ""))))
        self.prompt = QPlainTextEdit()
        self.prompt.setPlainText(
            "Early morning in ancient India near Sravasti. Misty countryside, trees, soft sunrise light, distant monastery, very slow aerial shot, calm and realistic cinematic style."
        )
        self.model = QComboBox()
        self.model.addItems(["veo3.1-fast", "veo3-fast", "veo3", "veo3-pro", "veo2", "veo2-fast", "veo2-pro"])
        self.aspect_ratio = QComboBox()
        self.aspect_ratio.addItems(["16:9", "9:16"])
        self.enhance_prompt = QCheckBox("自动优化提示词")
        self.enable_upsample = QCheckBox("提升到 1080p")
        self.enable_upsample.setChecked(True)
        self.timeout = QSpinBox()
        self.timeout.setRange(30, 7200)
        self.timeout.setValue(int(defaults.get("TIMEOUT", 900)))
        self.poll_interval = QSpinBox()
        self.poll_interval.setRange(1, 120)
        self.poll_interval.setValue(int(defaults.get("POLL_INTERVAL", 5)))
        self.output_name = QLineEdit("veo_ui_test")

        self.form_layout.addRow("API Key", self.api_key)
        self.form_layout.addRow("Base URL", self.base_url)
        self.form_layout.addRow("任务名称", self.output_name)
        self.form_layout.addRow("Prompt", self.prompt)
        self.form_layout.addRow("Model", self.model)
        self.form_layout.addRow("Aspect Ratio", self.aspect_ratio)
        self.form_layout.addRow("", self.enhance_prompt)
        self.form_layout.addRow("", self.enable_upsample)
        self.form_layout.addRow("Timeout", self.timeout)
        self.form_layout.addRow("Poll Interval", self.poll_interval)

        self.run_button.clicked.connect(self.start_task)

    def start_task(self) -> None:
        self.log_output.clear()
        self.base_url.setText(ui_backend.normalize_base_root(self.base_url.text()))
        kwargs = {
            "api_key": self.api_key.text().strip(),
            "base_url": self.base_url.text().strip(),
            "prompt": self.prompt.toPlainText().strip(),
            "model": self.model.currentText(),
            "aspect_ratio": self.aspect_ratio.currentText(),
            "enhance_prompt": self.enhance_prompt.isChecked(),
            "enable_upsample": self.enable_upsample.isChecked(),
            "timeout": self.timeout.value(),
            "poll_interval": self.poll_interval.value(),
            "output_name": self.output_name.text().strip(),
        }
        self.thread = SubmitThread(ui_backend.submit_veo_generation, kwargs)
        self.thread.done_signal.connect(self.on_done)
        self.thread.error_signal.connect(self.on_error)
        self.thread.finished.connect(self.on_thread_finished)
        self.set_busy(True)
        self.append_log("正在提交 Veo 任务...")
        self.thread.start()

    def on_done(self, result: dict) -> None:
        self.append_log(f"任务已提交: {result['task_id']}")
        self.submit_callback(result)
        self.set_busy(False)

    def on_error(self, message: str) -> None:
        self.append_log(message)
        self.set_busy(False)

    def on_thread_finished(self) -> None:
        self.thread = None


class KelingTab(ProviderTab):
    def __init__(self, submit_callback: Callable[[dict[str, Any]], None]) -> None:
        super().__init__("可灵", submit_callback)
        defaults = ui_backend.load_keling_defaults()

        self.api_key = QLineEdit(str(defaults.get("API_KEY", "")))
        self.base_url = QLineEdit(str(defaults.get("BASE_URL", "")))
        self.prompt = QPlainTextEdit()
        self.prompt.setPlainText("A majestic heavenly palace in the clouds, cinematic fantasy style, slow camera motion.")
        self.negative_prompt = QLineEdit("low quality, blurry, text, watermark")
        self.model_name = QComboBox()
        self.model_name.addItems(["kling-v1"])
        self.aspect_ratio = QComboBox()
        self.aspect_ratio.addItems(["16:9", "9:16"])
        self.duration = QComboBox()
        self.duration.addItems(["5", "10"])
        self.mode = QComboBox()
        self.mode.addItems(["std"])
        self.cfg_scale = QDoubleSpinBox()
        self.cfg_scale.setRange(0.1, 2.0)
        self.cfg_scale.setSingleStep(0.1)
        self.cfg_scale.setValue(0.7)
        self.timeout = QSpinBox()
        self.timeout.setRange(30, 7200)
        self.timeout.setValue(int(defaults.get("TIMEOUT", 300)))
        self.poll_interval = QSpinBox()
        self.poll_interval.setRange(1, 120)
        self.poll_interval.setValue(int(defaults.get("POLL_INTERVAL", 5)))
        self.output_name = QLineEdit("keling_ui_test")

        self.form_layout.addRow("API Key", self.api_key)
        self.form_layout.addRow("Base URL", self.base_url)
        self.form_layout.addRow("任务名称", self.output_name)
        self.form_layout.addRow("Prompt", self.prompt)
        self.form_layout.addRow("Negative Prompt", self.negative_prompt)
        self.form_layout.addRow("Model Name", self.model_name)
        self.form_layout.addRow("Aspect Ratio", self.aspect_ratio)
        self.form_layout.addRow("Duration", self.duration)
        self.form_layout.addRow("Mode", self.mode)
        self.form_layout.addRow("CFG Scale", self.cfg_scale)
        self.form_layout.addRow("Timeout", self.timeout)
        self.form_layout.addRow("Poll Interval", self.poll_interval)

        self.run_button.clicked.connect(self.start_task)

    def start_task(self) -> None:
        self.log_output.clear()
        kwargs = {
            "api_key": self.api_key.text().strip(),
            "base_url": self.base_url.text().strip(),
            "prompt": self.prompt.toPlainText().strip(),
            "negative_prompt": self.negative_prompt.text().strip(),
            "model_name": self.model_name.currentText(),
            "aspect_ratio": self.aspect_ratio.currentText(),
            "duration": self.duration.currentText(),
            "cfg_scale": self.cfg_scale.value(),
            "mode": self.mode.currentText(),
            "timeout": self.timeout.value(),
            "poll_interval": self.poll_interval.value(),
            "output_name": self.output_name.text().strip(),
        }
        self.thread = SubmitThread(ui_backend.submit_keling_generation, kwargs)
        self.thread.done_signal.connect(self.on_done)
        self.thread.error_signal.connect(self.on_error)
        self.thread.finished.connect(self.on_thread_finished)
        self.set_busy(True)
        self.append_log("正在提交可灵任务...")
        self.thread.start()

    def on_done(self, result: dict) -> None:
        self.append_log(f"任务已提交: {result['task_id']}")
        self.submit_callback(result)
        self.set_busy(False)

    def on_error(self, message: str) -> None:
        self.append_log(message)
        self.set_busy(False)

    def on_thread_finished(self) -> None:
        self.thread = None


class QueryTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.thread: QueryThread | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        group = QGroupBox("任务查询")
        form = QFormLayout(group)

        self.provider = QComboBox()
        self.provider.addItems(["sora", "veo", "keling"])
        self.api_key = QLineEdit(ui_backend.load_sora_defaults().get("API_KEY", ""))
        self.base_url = QLineEdit(ui_backend.load_sora_defaults().get("BASE_URL", ""))
        self.task_id = QLineEdit()
        self.provider.currentTextChanged.connect(self.on_provider_changed)

        form.addRow("Provider", self.provider)
        form.addRow("API Key", self.api_key)
        form.addRow("Base URL", self.base_url)
        form.addRow("Task ID", self.task_id)
        layout.addWidget(group)

        row = QHBoxLayout()
        self.query_button = QPushButton("查询任务")
        row.addWidget(self.query_button)
        row.addStretch(1)
        layout.addLayout(row)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output, 1)

        self.query_button.clicked.connect(self.start_query)

    def on_provider_changed(self, provider: str) -> None:
        if provider == "veo":
            defaults = ui_backend.load_veo_defaults()
            base_url = ui_backend.normalize_base_root(str(defaults.get("BASE_URL", "")))
        elif provider == "keling":
            defaults = ui_backend.load_keling_defaults()
            base_url = str(defaults.get("BASE_URL", ""))
        else:
            defaults = ui_backend.load_sora_defaults()
            base_url = str(defaults.get("BASE_URL", ""))
        self.api_key.setText(str(defaults.get("API_KEY", "")))
        self.base_url.setText(base_url)

    def start_query(self) -> None:
        self.output.clear()
        provider = self.provider.currentText()
        if provider == "veo":
            self.base_url.setText(ui_backend.normalize_base_root(self.base_url.text()))
        kwargs = {
            "api_key": self.api_key.text().strip(),
            "base_url": self.base_url.text().strip(),
            "task_id": self.task_id.text().strip(),
        }
        self.thread = QueryThread(provider, kwargs)
        self.thread.done_signal.connect(self.on_done)
        self.thread.error_signal.connect(self.on_error)
        self.query_button.setEnabled(False)
        self.thread.start()

    def on_done(self, result: dict) -> None:
        self.output.setPlainText(json.dumps(result, ensure_ascii=False, indent=2))
        self.query_button.setEnabled(True)

    def on_error(self, message: str) -> None:
        self.output.setPlainText(message)
        self.query_button.setEnabled(True)

    def has_running_thread(self) -> bool:
        return self.thread is not None and self.thread.isRunning()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Video Generate UI")
        self.resize(1280, 900)
        self.tasks: list[dict[str, Any]] = []
        self.refresh_threads: dict[str, RefreshThread] = {}

        splitter = QSplitter(Qt.Orientation.Vertical)
        self.tabs = QTabWidget()
        self.sora_tab = SoraTab(self.add_task_record)
        self.veo_tab = VeoTab(self.add_task_record)
        self.keling_tab = KelingTab(self.add_task_record)
        self.query_tab = QueryTab()
        self.tabs.addTab(self.sora_tab, "Sora")
        self.tabs.addTab(self.veo_tab, "Veo")
        self.tabs.addTab(self.keling_tab, "可灵")
        self.tabs.addTab(self.query_tab, "任务查询")
        self.tabs.currentChanged.connect(self.on_tab_changed)
        splitter.addWidget(self.tabs)

        history_widget = QWidget()
        history_layout = QVBoxLayout(history_widget)
        history_layout.setContentsMargins(12, 12, 12, 12)
        history_layout.setSpacing(8)

        self.task_table = QTableWidget(0, 7)
        self.task_table.setHorizontalHeaderLabels(["时间", "类型", "任务名称", "任务ID", "状态", "结果路径", "错误"])
        self.task_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.task_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.task_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        history_layout.addWidget(self.task_table, 1)

        self.history_log = QTextEdit()
        self.history_log.setReadOnly(True)
        history_layout.addWidget(self.history_log, 1)
        splitter.addWidget(history_widget)
        splitter.setSizes([560, 320])

        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(splitter)
        self.setCentralWidget(container)

        self.load_tasks()
        self.render_task_table()
        self.refresh_provider_logs()

        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self.poll_active_tasks)
        self.poll_timer.start(5000)
        self.poll_active_tasks()

    def running_threads(self) -> list[QThread]:
        threads: list[QThread] = []
        for thread in self.refresh_threads.values():
            if thread.isRunning():
                threads.append(thread)
        for owner in (self.sora_tab, self.veo_tab, self.keling_tab):
            if owner.thread is not None and owner.thread.isRunning():
                threads.append(owner.thread)
        if self.query_tab.thread is not None and self.query_tab.thread.isRunning():
            threads.append(self.query_tab.thread)
        return threads

    def now_text(self) -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def append_history_log(self, text: str) -> None:
        self.history_log.append(f"[{self.now_text()}] {text}")

    def load_tasks(self) -> None:
        if not TASKS_PATH.is_file():
            self.tasks = []
            return
        try:
            self.tasks = json.loads(TASKS_PATH.read_text(encoding="utf-8"))
        except Exception:
            self.tasks = []

    def save_tasks(self) -> None:
        TASKS_PATH.write_text(json.dumps(self.tasks, ensure_ascii=False, indent=2), encoding="utf-8")

    def render_task_table(self) -> None:
        self.task_table.setRowCount(len(self.tasks))
        for row, task in enumerate(self.tasks):
            values = [
                str(task.get("created_at", "")),
                str(task.get("provider", "")),
                str(task.get("task_name", "")),
                str(task.get("task_id", "")),
                self.format_status(task),
                str(task.get("file", "")),
                str(task.get("error", "")),
            ]
            for col, value in enumerate(values):
                self.task_table.setItem(row, col, QTableWidgetItem(value))

    def build_provider_history_text(self, provider: str) -> str:
        provider = provider.strip().lower()
        lines: list[str] = []
        for task in reversed(self.tasks):
            if str(task.get("provider", "")).strip().lower() != provider:
                continue
            line = (
                f"{task.get('created_at', '')} | "
                f"{task.get('task_name', '')} | "
                f"{task.get('task_id', '')} | "
                f"{self.format_status(task)}"
            )
            file_path = str(task.get("file", "")).strip()
            error = str(task.get("error", "")).strip()
            if file_path:
                line += f" | {file_path}"
            elif error:
                line += f" | {error}"
            lines.append(line)
        if not lines:
            return f"暂无 {provider} 历史任务记录。"
        return "\n".join(lines)

    def refresh_provider_logs(self) -> None:
        self.sora_tab.set_log_text(self.build_provider_history_text("sora"))
        self.veo_tab.set_log_text(self.build_provider_history_text("veo"))
        self.keling_tab.set_log_text(self.build_provider_history_text("keling"))

    def on_tab_changed(self, index: int) -> None:
        widget = self.tabs.widget(index)
        if widget is self.sora_tab:
            self.sora_tab.set_log_text(self.build_provider_history_text("sora"))
        elif widget is self.veo_tab:
            self.veo_tab.set_log_text(self.build_provider_history_text("veo"))
        elif widget is self.keling_tab:
            self.keling_tab.set_log_text(self.build_provider_history_text("keling"))

    def format_status(self, task: dict[str, Any]) -> str:
        status = str(task.get("status", "")).strip()
        progress = str(task.get("progress", "")).strip()
        return f"{status} {progress}".strip()

    def add_task_record(self, task: dict[str, Any]) -> None:
        record = dict(task)
        now = self.now_text()
        record["created_at"] = now
        record["updated_at"] = now
        self.tasks.insert(0, record)
        self.save_tasks()
        self.render_task_table()
        self.refresh_provider_logs()
        self.append_history_log(f"已记录任务 {record['task_name']} ({record['task_id']})")
        self.poll_task(record)

    def update_task_record(self, task_id: str, updated: dict[str, Any]) -> None:
        for index, task in enumerate(self.tasks):
            if str(task.get("task_id")) != task_id:
                continue
            merged = dict(task)
            merged.update(updated)
            merged["updated_at"] = self.now_text()
            self.tasks[index] = merged
            self.save_tasks()
            self.render_task_table()
            self.refresh_provider_logs()
            return

    def active_tasks(self) -> list[dict[str, Any]]:
        active = []
        for task in self.tasks:
            status = str(task.get("status", "unknown")).strip().lower()
            if status not in {"completed", "failed"}:
                active.append(task)
        return active

    def poll_active_tasks(self) -> None:
        for task in self.active_tasks():
            task_id = str(task.get("task_id", "")).strip()
            if not task_id or task_id in self.refresh_threads:
                continue
            self.poll_task(task)

    def poll_task(self, task: dict[str, Any]) -> None:
        task_id = str(task.get("task_id", "")).strip()
        if not task_id:
            return
        thread = RefreshThread(task)
        self.refresh_threads[task_id] = thread
        thread.done_signal.connect(self.on_refresh_done)
        thread.error_signal.connect(self.on_refresh_error)
        thread.finished.connect(lambda tid=task_id: self.on_refresh_thread_finished(tid))
        thread.start()

    def on_refresh_done(self, updated: dict[str, Any]) -> None:
        task_id = str(updated.get("task_id", "")).strip()
        self.update_task_record(task_id, updated)
        status = str(updated.get("status", ""))
        path = str(updated.get("file", "")).strip()
        if status == "completed":
            self.append_history_log(f"任务完成: {task_id} {path}")
        else:
            self.append_history_log(f"任务状态更新: {task_id} -> {self.format_status(updated)}")

    def on_refresh_error(self, task_id: str, message: str) -> None:
        for task in self.tasks:
            if str(task.get("task_id", "")) != task_id:
                continue
            status = str(task.get("status", "unknown")).strip().lower()
            if status in {"completed", "failed"}:
                break
            task["error"] = message.splitlines()[0]
            task["updated_at"] = self.now_text()
            self.save_tasks()
            self.render_task_table()
            self.refresh_provider_logs()
            self.append_history_log(f"任务刷新失败: {task_id} {task['error']}")
            break

    def on_refresh_thread_finished(self, task_id: str) -> None:
        if task_id in self.refresh_threads:
            self.refresh_threads.pop(task_id)

    def closeEvent(self, event: QCloseEvent) -> None:
        running = self.running_threads()
        if running:
            self.append_history_log("检测到后台任务仍在运行，已阻止关闭窗口。")
            QMessageBox.warning(
                self,
                "任务仍在运行",
                "当前仍有后台提交或状态查询任务在运行，请等待它们结束后再关闭窗口。",
            )
            event.ignore()
            return

        self.poll_timer.stop()
        super().closeEvent(event)


def main() -> int:
    app = QApplication([])
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
