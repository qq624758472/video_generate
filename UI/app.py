#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import traceback
from functools import partial
from typing import Any, Callable

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import ui_backend


class TaskThread(QThread):
    log_signal = pyqtSignal(str)
    done_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(str)

    def __init__(self, fn: Callable[..., dict], kwargs: dict[str, Any]) -> None:
        super().__init__()
        self.fn = fn
        self.kwargs = kwargs

    def run(self) -> None:
        try:
            result = self.fn(logger=self.log_signal.emit, **self.kwargs)
            self.done_signal.emit(result)
        except Exception as exc:
            message = f"{exc}\n\n{traceback.format_exc()}"
            self.error_signal.emit(message)


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
    def __init__(self, title: str) -> None:
        super().__init__()
        self.title = title
        self.thread: TaskThread | None = None
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(12, 12, 12, 12)
        self.layout.setSpacing(12)

        self.form_group = QGroupBox(f"{title} 参数")
        self.form_layout = QFormLayout(self.form_group)
        self.form_layout.setSpacing(10)
        self.layout.addWidget(self.form_group)

        self.button_row = QHBoxLayout()
        self.run_button = QPushButton(f"开始生成 {title} 视频")
        self.button_row.addWidget(self.run_button)
        self.button_row.addStretch(1)
        self.layout.addLayout(self.button_row)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.layout.addWidget(self.log_output, 1)

    def append_log(self, text: str) -> None:
        self.log_output.append(text)

    def set_busy(self, busy: bool) -> None:
        self.run_button.setEnabled(not busy)


class SoraTab(ProviderTab):
    def __init__(self) -> None:
        super().__init__("Sora")
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
        self.form_layout.addRow("Prompt", self.prompt)
        self.form_layout.addRow("Model", self.model)
        self.form_layout.addRow("Duration", self.duration)
        self.form_layout.addRow("Width", self.width)
        self.form_layout.addRow("Height", self.height)
        self.form_layout.addRow("FPS", self.fps)
        self.form_layout.addRow("Timeout", self.timeout)
        self.form_layout.addRow("Poll Interval", self.poll_interval)
        self.form_layout.addRow("Output Name", self.output_name)
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
        self.thread = TaskThread(ui_backend.run_sora_generation, kwargs)
        self.thread.log_signal.connect(self.append_log)
        self.thread.done_signal.connect(self.on_done)
        self.thread.error_signal.connect(self.on_error)
        self.set_busy(True)
        self.thread.start()

    def on_done(self, result: dict) -> None:
        self.append_log(json.dumps(result, ensure_ascii=False, indent=2))
        self.set_busy(False)

    def on_error(self, message: str) -> None:
        self.append_log(message)
        self.set_busy(False)


class VeoTab(ProviderTab):
    def __init__(self) -> None:
        super().__init__("Veo")
        defaults = ui_backend.load_veo_defaults()

        self.api_key = QLineEdit(str(defaults.get("API_KEY", "")))
        self.base_url = QLineEdit(ui_backend.veo_module.normalize_base_root(str(defaults.get("BASE_URL", ""))))
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
        self.form_layout.addRow("Prompt", self.prompt)
        self.form_layout.addRow("Model", self.model)
        self.form_layout.addRow("Aspect Ratio", self.aspect_ratio)
        self.form_layout.addRow("", self.enhance_prompt)
        self.form_layout.addRow("", self.enable_upsample)
        self.form_layout.addRow("Timeout", self.timeout)
        self.form_layout.addRow("Poll Interval", self.poll_interval)
        self.form_layout.addRow("Output Name", self.output_name)

        self.run_button.clicked.connect(self.start_task)

    def start_task(self) -> None:
        self.log_output.clear()
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
        self.thread = TaskThread(ui_backend.run_veo_generation, kwargs)
        self.thread.log_signal.connect(self.append_log)
        self.thread.done_signal.connect(self.on_done)
        self.thread.error_signal.connect(self.on_error)
        self.set_busy(True)
        self.thread.start()

    def on_done(self, result: dict) -> None:
        self.append_log(json.dumps(result, ensure_ascii=False, indent=2))
        self.set_busy(False)

    def on_error(self, message: str) -> None:
        self.append_log(message)
        self.set_busy(False)


class KelingTab(ProviderTab):
    def __init__(self) -> None:
        super().__init__("可灵")
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
        self.form_layout.addRow("Prompt", self.prompt)
        self.form_layout.addRow("Negative Prompt", self.negative_prompt)
        self.form_layout.addRow("Model Name", self.model_name)
        self.form_layout.addRow("Aspect Ratio", self.aspect_ratio)
        self.form_layout.addRow("Duration", self.duration)
        self.form_layout.addRow("Mode", self.mode)
        self.form_layout.addRow("CFG Scale", self.cfg_scale)
        self.form_layout.addRow("Timeout", self.timeout)
        self.form_layout.addRow("Poll Interval", self.poll_interval)
        self.form_layout.addRow("Output Name", self.output_name)

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
        self.thread = TaskThread(ui_backend.run_keling_generation, kwargs)
        self.thread.log_signal.connect(self.append_log)
        self.thread.done_signal.connect(self.on_done)
        self.thread.error_signal.connect(self.on_error)
        self.set_busy(True)
        self.thread.start()

    def on_done(self, result: dict) -> None:
        self.append_log(json.dumps(result, ensure_ascii=False, indent=2))
        self.set_busy(False)

    def on_error(self, message: str) -> None:
        self.append_log(message)
        self.set_busy(False)


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
            base_url = ui_backend.veo_module.normalize_base_root(str(defaults.get("BASE_URL", "")))
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


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Video Generate UI")
        self.resize(1100, 820)

        tabs = QTabWidget()
        tabs.addTab(SoraTab(), "Sora")
        tabs.addTab(VeoTab(), "Veo")
        tabs.addTab(KelingTab(), "可灵")
        tabs.addTab(QueryTab(), "任务查询")
        self.setCentralWidget(tabs)


def main() -> int:
    app = QApplication([])
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
