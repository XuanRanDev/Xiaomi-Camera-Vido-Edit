import os
import sys
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtGui import QFont, QIcon

if __package__ in (None, ""):
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.config import AppConfig
from app.ffmpeg_utils import find_ffmpeg
from app.tasks import (
    time_lapse,
    inverted,
    add_music,
    concat_two_videos,
    compress_video,
    generate_compress_preview,
)


class Worker(QtCore.QThread):
    log_signal = QtCore.Signal(str)
    error_signal = QtCore.Signal(str)
    done_signal = QtCore.Signal()

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            self.func(*self.args, log=self.log_signal.emit, **self.kwargs)
            self.done_signal.emit()
        except Exception as exc:
            self.error_signal.emit(str(exc))


class ResultWorker(QtCore.QThread):
    log_signal = QtCore.Signal(str)
    error_signal = QtCore.Signal(str)
    result_signal = QtCore.Signal(object)
    done_signal = QtCore.Signal()

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            result = self.func(*self.args, log=self.log_signal.emit, **self.kwargs)
            self.result_signal.emit(result)
            self.done_signal.emit()
        except Exception as exc:
            self.error_signal.emit(str(exc))



def apply_theme(app: QtWidgets.QApplication):
    app.setStyle("Fusion")
    app.setFont(QFont("Microsoft YaHei UI", 10))
    app.setStyleSheet(
        """
        QMainWindow {
            background-color: #f3f0e8;
        }
        QGroupBox {
            border: 1px solid #d8d2c3;
            border-radius: 10px;
            margin-top: 12px;
            padding: 10px;
            background-color: #fffdf8;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 6px;
            color: #3b3a36;
            font-weight: 600;
        }
        #Header {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #2f5d50, stop:1 #1d3f36);
            border-radius: 12px;
            padding: 16px;
        }
        #HeaderTitle {
            color: #f7f3ea;
            font-size: 20px;
            font-weight: 700;
        }
        #HeaderSubtitle {
            color: #d9d2c2;
            font-size: 11px;
        }
        QLineEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox {
            background-color: #ffffff;
            border: 1px solid #d8d2c3;
            border-radius: 8px;
            padding: 6px 8px;
        }
        QPlainTextEdit {
            background-color: #0f1e1a;
            color: #d9e1d7;
            border: 1px solid #1c2e28;
        }
        QPushButton {
            background-color: #2f5d50;
            color: #f7f3ea;
            border: none;
            border-radius: 8px;
            padding: 6px 12px;
        }
        QPushButton:hover {
            background-color: #3a7262;
        }
        QPushButton:pressed {
            background-color: #25493f;
        }
        QTabWidget::pane {
            border: 1px solid #d8d2c3;
            border-radius: 10px;
            background-color: #fffdf8;
        }
        QTabBar::tab {
            background-color: #e7e1d5;
            border: 1px solid #d8d2c3;
            border-bottom: none;
            padding: 8px 14px;
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
            min-width: 90px;
        }
        QTabBar::tab:selected {
            background-color: #fffdf8;
            color: #1f2c27;
            font-weight: 600;
        }
        QCheckBox {
            spacing: 6px;
        }
        """
    )
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, config: AppConfig):
        super().__init__()
        self.config = config
        self.setWindowTitle("小米摄像头视频处理")
        self.resize(1060, 760)

        self.tabs = QtWidgets.QTabWidget()
        self.log_output = QtWidgets.QPlainTextEdit()
        self.log_output.setReadOnly(True)

        self.ffmpeg_path = QtWidgets.QLineEdit()
        self.ffmpeg_path.setPlaceholderText("如未配置 PATH，可在此选择 ffmpeg.exe")
        self.ffmpeg_browse = QtWidgets.QPushButton("浏览")
        self.ffmpeg_browse.clicked.connect(self.select_ffmpeg)

        ffmpeg_layout = QtWidgets.QHBoxLayout()
        ffmpeg_layout.addWidget(self.ffmpeg_path)
        ffmpeg_layout.addWidget(self.ffmpeg_browse)

        ffmpeg_group = QtWidgets.QGroupBox("FFmpeg")
        ffmpeg_group.setLayout(ffmpeg_layout)

        main_layout = QtWidgets.QVBoxLayout()
        main_layout.addWidget(ffmpeg_group)
        main_layout.addWidget(self.tabs, 1)
        main_layout.addWidget(self.log_output, 2)

        content = QtWidgets.QWidget()
        content.setLayout(main_layout)

        shell_layout = QtWidgets.QVBoxLayout()
        shell_layout.setSpacing(14)
        shell_layout.addWidget(self.build_header())
        shell_layout.addWidget(content, 1)

        container = QtWidgets.QWidget()
        container.setLayout(shell_layout)
        self.setCentralWidget(container)

        self.time_lapse_tab = self.build_time_lapse_tab()
        self.inverted_tab = self.build_inverted_tab()
        self.add_music_tab = self.build_add_music_tab()
        self.concat_tab = self.build_concat_tab()
        self.compress_tab = self.build_compress_tab()

        self.tabs.addTab(self.time_lapse_tab, "延时摄影")
        self.tabs.addTab(self.inverted_tab, "倒放变速")
        self.tabs.addTab(self.add_music_tab, "添加音乐")
        self.tabs.addTab(self.concat_tab, "视频拼接")
        self.tabs.addTab(self.compress_tab, "画质压缩")

        self.worker = None
        self.load_config()

    def load_config(self):
        self.ffmpeg_path.setText(self.config.data.get("ffmpeg_path", ""))

        tl = self.config.data["time_lapse"]
        self.tl_base_folder.setText(tl.get("base_folder", ""))
        self.tl_output_file.setText(tl.get("output_file", ""))
        self.tl_speed.setValue(float(tl.get("speed_factor", 39.0)))
        self.tl_fps.setValue(int(tl.get("fps", 30)))
        self.tl_hour_start.setValue(int(tl.get("hour_start", 8)))
        self.tl_hour_end.setValue(int(tl.get("hour_end", 20)))

        inv = self.config.data["inverted"]
        self.inv_input_dir.setText(inv.get("input_dir", ""))
        self.inv_output_dir.setText(inv.get("output_dir", ""))
        self.inv_speed.setValue(float(inv.get("speed_factor", 1.0)))
        self.inv_merge_output.setText(inv.get("merge_output", ""))

        am = self.config.data["add_music"]
        self.am_video_file.setText(am.get("video_file", ""))
        self.am_audio_file.setText(am.get("audio_file", ""))
        self.am_output_file.setText(am.get("output_file", ""))
        self.am_replace_audio.setChecked(bool(am.get("replace_audio", True)))

        concat = self.config.data["concat"]
        self.concat_video_a.setText(concat.get("video_a", ""))
        self.concat_video_b.setText(concat.get("video_b", ""))
        self.concat_output_file.setText(concat.get("output_file", ""))

        compress = self.config.data["compress"]
        self.compress_input_file.setText(compress.get("input_file", ""))
        self.compress_output_file.setText(compress.get("output_file", ""))
        self.compress_scale.setValue(int(compress.get("scale_percent", 70)))
        self.compress_scale_slider.setValue(int(compress.get("scale_percent", 70)))
        self.compress_crf.setValue(int(compress.get("crf", 28)))
        self.compress_preset.setCurrentText(compress.get("preset", "medium"))
        self.compress_use_gpu.setChecked(bool(compress.get("use_gpu", False)))
        self.update_compress_estimate()

    def save_config(self):
        self.config.data["ffmpeg_path"] = self.ffmpeg_path.text().strip()
        self.config.data["time_lapse"] = {
            "base_folder": self.tl_base_folder.text().strip(),
            "output_file": self.tl_output_file.text().strip(),
            "speed_factor": self.tl_speed.value(),
            "fps": self.tl_fps.value(),
            "hour_start": self.tl_hour_start.value(),
            "hour_end": self.tl_hour_end.value(),
        }
        self.config.data["inverted"] = {
            "input_dir": self.inv_input_dir.text().strip(),
            "output_dir": self.inv_output_dir.text().strip(),
            "speed_factor": self.inv_speed.value(),
            "merge_output": self.inv_merge_output.text().strip(),
        }
        self.config.data["add_music"] = {
            "video_file": self.am_video_file.text().strip(),
            "audio_file": self.am_audio_file.text().strip(),
            "output_file": self.am_output_file.text().strip(),
            "replace_audio": self.am_replace_audio.isChecked(),
        }
        self.config.data["concat"] = {
            "video_a": self.concat_video_a.text().strip(),
            "video_b": self.concat_video_b.text().strip(),
            "output_file": self.concat_output_file.text().strip(),
        }
        self.config.data["compress"] = {
            "input_file": self.compress_input_file.text().strip(),
            "output_file": self.compress_output_file.text().strip(),
            "scale_percent": self.compress_scale.value(),
            "crf": self.compress_crf.value(),
            "preset": self.compress_preset.currentText(),
            "use_gpu": self.compress_use_gpu.isChecked(),
        }
        self.config.save()

    def select_ffmpeg(self):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "选择 ffmpeg", "", "ffmpeg 可执行文件 (ffmpeg.exe);;所有文件 (*)"
        )
        if file_path:
            self.ffmpeg_path.setText(file_path)

    def resolve_ffmpeg_path(self):
        current = self.ffmpeg_path.text().strip()
        resolved = find_ffmpeg(current)
        if resolved:
            self.ffmpeg_path.setText(resolved)
            return resolved
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "未找到 FFmpeg，请选择", "", "ffmpeg 可执行文件 (ffmpeg.exe);;所有文件 (*)"
        )
        if file_path:
            self.ffmpeg_path.setText(file_path)
            return file_path
        return ""

    def add_log(self, message: str):
        self.log_output.appendPlainText(message)

    def format_bytes(self, size_bytes: int) -> str:
        units = ["B", "KB", "MB", "GB", "TB"]
        size = float(size_bytes)
        for unit in units:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} PB"

    def update_compress_estimate(self):
        input_path = self.compress_input_file.text().strip()
        if not input_path:
            self.compress_estimate.setText("估算大小：-")
            return
        path = Path(input_path)
        if not path.exists():
            self.compress_estimate.setText("估算大小：-")
            return
        ratio = max(0.1, min(self.compress_scale.value() / 100.0, 1.0))
        estimated = int(path.stat().st_size * ratio * ratio * 0.7)
        self.compress_estimate.setText(f"估算大小：约 {self.format_bytes(estimated)}")

    def build_header(self):
        frame = QtWidgets.QFrame()
        frame.setObjectName("Header")
        layout = QtWidgets.QVBoxLayout(frame)
        title = QtWidgets.QLabel("小米摄像头视频处理")
        title.setObjectName("HeaderTitle")
        subtitle = QtWidgets.QLabel("批量加速 / 倒放 / 拼接 / 配乐，所有输出都在 output 目录")
        subtitle.setObjectName("HeaderSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)
        return frame

    def build_time_lapse_tab(self):
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout(widget)

        self.tl_base_folder = QtWidgets.QLineEdit()
        self.tl_base_browse = QtWidgets.QPushButton("选择")
        self.tl_base_browse.clicked.connect(
            lambda: self.select_dir(self.tl_base_folder, "选择基础目录")
        )
        layout.addRow("基础目录", self.build_row(self.tl_base_folder, self.tl_base_browse))

        self.tl_output_file = QtWidgets.QLineEdit()
        self.tl_output_browse = QtWidgets.QPushButton("选择")
        self.tl_output_browse.clicked.connect(
            lambda: self.select_save_file(self.tl_output_file, "选择输出文件")
        )
        layout.addRow("输出文件", self.build_row(self.tl_output_file, self.tl_output_browse))

        self.tl_speed = QtWidgets.QDoubleSpinBox()
        self.tl_speed.setRange(0.1, 200.0)
        self.tl_speed.setDecimals(2)
        layout.addRow("倍速", self.tl_speed)

        self.tl_fps = QtWidgets.QSpinBox()
        self.tl_fps.setRange(1, 240)
        layout.addRow("帧率", self.tl_fps)

        self.tl_hour_start = QtWidgets.QSpinBox()
        self.tl_hour_start.setRange(0, 23)
        self.tl_hour_end = QtWidgets.QSpinBox()
        self.tl_hour_end.setRange(1, 24)
        hour_row = QtWidgets.QHBoxLayout()
        hour_row.addWidget(self.tl_hour_start)
        hour_row.addWidget(QtWidgets.QLabel("到"))
        hour_row.addWidget(self.tl_hour_end)
        layout.addRow("小时范围", self.wrap_layout(hour_row))

        self.tl_run = QtWidgets.QPushButton("开始延时摄影")
        self.tl_run.clicked.connect(self.run_time_lapse)
        layout.addRow(self.tl_run)

        return widget

    def build_inverted_tab(self):
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout(widget)

        self.inv_input_dir = QtWidgets.QLineEdit()
        self.inv_input_browse = QtWidgets.QPushButton("选择")
        self.inv_input_browse.clicked.connect(
            lambda: self.select_dir(self.inv_input_dir, "选择输入目录")
        )
        layout.addRow("输入目录", self.build_row(self.inv_input_dir, self.inv_input_browse))

        self.inv_output_dir = QtWidgets.QLineEdit()
        self.inv_output_browse = QtWidgets.QPushButton("选择")
        self.inv_output_browse.clicked.connect(
            lambda: self.select_dir(self.inv_output_dir, "选择输出目录")
        )
        layout.addRow("输出目录", self.build_row(self.inv_output_dir, self.inv_output_browse))

        self.inv_merge_output = QtWidgets.QLineEdit()
        self.inv_merge_browse = QtWidgets.QPushButton("选择")
        self.inv_merge_browse.clicked.connect(
            lambda: self.select_save_file(self.inv_merge_output, "选择合并输出")
        )
        layout.addRow("合并输出", self.build_row(self.inv_merge_output, self.inv_merge_browse))

        self.inv_speed = QtWidgets.QDoubleSpinBox()
        self.inv_speed.setRange(0.1, 10.0)
        self.inv_speed.setDecimals(2)
        layout.addRow("倍速", self.inv_speed)

        self.inv_run = QtWidgets.QPushButton("开始倒放变速")
        self.inv_run.clicked.connect(self.run_inverted)
        layout.addRow(self.inv_run)

        return widget

    def build_add_music_tab(self):
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout(widget)

        self.am_video_file = QtWidgets.QLineEdit()
        self.am_video_browse = QtWidgets.QPushButton("选择")
        self.am_video_browse.clicked.connect(
            lambda: self.select_open_file(self.am_video_file, "选择视频文件")
        )
        layout.addRow("视频文件", self.build_row(self.am_video_file, self.am_video_browse))

        self.am_audio_file = QtWidgets.QLineEdit()
        self.am_audio_browse = QtWidgets.QPushButton("选择")
        self.am_audio_browse.clicked.connect(
            lambda: self.select_open_file(self.am_audio_file, "选择音频文件")
        )
        layout.addRow("音频文件", self.build_row(self.am_audio_file, self.am_audio_browse))

        self.am_output_file = QtWidgets.QLineEdit()
        self.am_output_browse = QtWidgets.QPushButton("选择")
        self.am_output_browse.clicked.connect(
            lambda: self.select_save_file(self.am_output_file, "选择输出文件")
        )
        layout.addRow("输出文件", self.build_row(self.am_output_file, self.am_output_browse))

        self.am_replace_audio = QtWidgets.QCheckBox("覆盖原声")
        self.am_replace_audio.setChecked(True)
        layout.addRow(self.am_replace_audio)

        self.am_run = QtWidgets.QPushButton("开始添加音乐")
        self.am_run.clicked.connect(self.run_add_music)
        layout.addRow(self.am_run)

        return widget

    def build_concat_tab(self):
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout(widget)

        self.concat_video_a = QtWidgets.QLineEdit()
        self.concat_video_a_browse = QtWidgets.QPushButton("选择")
        self.concat_video_a_browse.clicked.connect(
            lambda: self.select_open_file(self.concat_video_a, "选择视频 1")
        )
        layout.addRow("视频 1", self.build_row(self.concat_video_a, self.concat_video_a_browse))

        self.concat_video_b = QtWidgets.QLineEdit()
        self.concat_video_b_browse = QtWidgets.QPushButton("选择")
        self.concat_video_b_browse.clicked.connect(
            lambda: self.select_open_file(self.concat_video_b, "选择视频 2")
        )
        layout.addRow("视频 2", self.build_row(self.concat_video_b, self.concat_video_b_browse))

        self.concat_output_file = QtWidgets.QLineEdit()
        self.concat_output_browse = QtWidgets.QPushButton("选择")
        self.concat_output_browse.clicked.connect(
            lambda: self.select_save_file(self.concat_output_file, "选择输出文件")
        )
        layout.addRow("输出文件", self.build_row(self.concat_output_file, self.concat_output_browse))

        self.concat_run = QtWidgets.QPushButton("开始拼接")
        self.concat_run.clicked.connect(self.run_concat)
        layout.addRow(self.concat_run)

        return widget

    def build_compress_tab(self):
        widget = QtWidgets.QWidget()
        outer_layout = QtWidgets.QHBoxLayout(widget)
        outer_layout.setSpacing(16)

        form_panel = QtWidgets.QWidget()
        form_layout = QtWidgets.QVBoxLayout(form_panel)
        form_layout.setSpacing(12)

        source_group = QtWidgets.QGroupBox("输入与输出")
        source_layout = QtWidgets.QFormLayout(source_group)

        self.compress_input_file = QtWidgets.QLineEdit()
        self.compress_input_browse = QtWidgets.QPushButton("选择")
        self.compress_input_browse.clicked.connect(
            lambda: self.select_open_file(self.compress_input_file, "选择视频文件")
        )
        source_layout.addRow("输入视频", self.build_row(self.compress_input_file, self.compress_input_browse))

        self.compress_output_file = QtWidgets.QLineEdit()
        self.compress_output_browse = QtWidgets.QPushButton("选择")
        self.compress_output_browse.clicked.connect(
            lambda: self.select_save_file(self.compress_output_file, "选择输出文件")
        )
        source_layout.addRow("输出文件", self.build_row(self.compress_output_file, self.compress_output_browse))

        params_group = QtWidgets.QGroupBox("压缩参数")
        params_layout = QtWidgets.QFormLayout(params_group)

        self.compress_scale_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.compress_scale_slider.setRange(20, 100)
        self.compress_scale = QtWidgets.QSpinBox()
        self.compress_scale.setRange(20, 100)
        self.compress_scale.setSuffix("%")
        self.compress_scale_slider.valueChanged.connect(self.compress_scale.setValue)
        self.compress_scale.valueChanged.connect(self.compress_scale_slider.setValue)
        self.compress_scale.valueChanged.connect(self.update_compress_estimate)

        scale_layout = QtWidgets.QHBoxLayout()
        scale_layout.addWidget(self.compress_scale_slider, 1)
        scale_layout.addWidget(self.compress_scale)
        params_layout.addRow("缩放比例", self.wrap_layout(scale_layout))

        self.compress_crf = QtWidgets.QSpinBox()
        self.compress_crf.setRange(18, 35)
        self.compress_crf.setToolTip("数值越小画质越好，文件越大")
        params_layout.addRow("画质 (CRF)", self.compress_crf)

        self.compress_preset = QtWidgets.QComboBox()
        self.compress_preset.addItems(
            [
                "ultrafast",
                "superfast",
                "veryfast",
                "faster",
                "fast",
                "medium",
                "slow",
                "slower",
                "veryslow",
            ]
        )
        params_layout.addRow("编码速度", self.compress_preset)

        self.compress_use_gpu = QtWidgets.QCheckBox("使用 GPU 加速 (NVENC)")
        params_layout.addRow(self.compress_use_gpu)

        self.compress_estimate = QtWidgets.QLabel("估算大小：-")
        params_layout.addRow(self.compress_estimate)

        actions_group = QtWidgets.QGroupBox("操作")
        actions_layout = QtWidgets.QHBoxLayout(actions_group)
        actions_layout.setSpacing(12)

        self.compress_preview = QtWidgets.QPushButton("预览画质")
        self.compress_preview.clicked.connect(self.run_compress_preview)
        self.compress_run = QtWidgets.QPushButton("开始压缩")
        self.compress_run.clicked.connect(self.run_compress)
        actions_layout.addWidget(self.compress_preview)
        actions_layout.addWidget(self.compress_run)

        form_layout.addWidget(source_group)
        form_layout.addWidget(params_group)
        form_layout.addWidget(actions_group)
        form_layout.addStretch(1)

        preview_group = QtWidgets.QGroupBox("预览")
        preview_layout = QtWidgets.QVBoxLayout(preview_group)
        self.compress_preview_label = QtWidgets.QLabel("预览图")
        self.compress_preview_label.setAlignment(QtCore.Qt.AlignCenter)
        self.compress_preview_label.setMinimumSize(360, 220)
        self.compress_preview_label.setFrameShape(QtWidgets.QFrame.StyledPanel)
        preview_hint = QtWidgets.QLabel("提示：预览仅代表缩放效果，实际压缩以输出为准。")
        preview_hint.setWordWrap(True)
        preview_layout.addWidget(self.compress_preview_label, 1)
        preview_layout.addWidget(preview_hint)

        outer_layout.addWidget(form_panel, 3)
        outer_layout.addWidget(preview_group, 2)

        self.compress_input_file.textChanged.connect(self.update_compress_estimate)
        self.compress_scale_slider.valueChanged.connect(self.update_compress_estimate)

        return widget

    def build_row(self, line_edit, button):
        layout = QtWidgets.QHBoxLayout()
        layout.addWidget(line_edit)
        layout.addWidget(button)
        return self.wrap_layout(layout)

    def wrap_layout(self, layout):
        widget = QtWidgets.QWidget()
        widget.setLayout(layout)
        return widget

    def select_dir(self, target, title):
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, title)
        if directory:
            target.setText(directory)

    def select_open_file(self, target, title):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(self, title)
        if file_path:
            target.setText(file_path)

    def select_save_file(self, target, title):
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, title)
        if file_path:
            target.setText(file_path)

    def run_time_lapse(self):
        ffmpeg_path = self.resolve_ffmpeg_path()
        if not ffmpeg_path:
            self.add_log("需要设置 FFmpeg 路径。")
            return
        self.save_config()
        self.add_log("开始延时摄影任务...")
        self.start_worker(
            time_lapse,
            ffmpeg_path,
            Path(self.tl_base_folder.text().strip()),
            Path(self.tl_output_file.text().strip()),
            self.tl_speed.value(),
            self.tl_fps.value(),
            self.tl_hour_start.value(),
            self.tl_hour_end.value(),
        )

    def run_inverted(self):
        ffmpeg_path = self.resolve_ffmpeg_path()
        if not ffmpeg_path:
            self.add_log("需要设置 FFmpeg 路径。")
            return
        self.save_config()
        self.add_log("开始倒放变速任务...")
        self.start_worker(
            inverted,
            ffmpeg_path,
            Path(self.inv_input_dir.text().strip()),
            Path(self.inv_output_dir.text().strip()),
            self.inv_speed.value(),
            Path(self.inv_merge_output.text().strip()),
        )

    def run_add_music(self):
        ffmpeg_path = self.resolve_ffmpeg_path()
        if not ffmpeg_path:
            self.add_log("需要设置 FFmpeg 路径。")
            return
        self.save_config()
        self.add_log("开始添加音乐任务...")
        self.start_worker(
            add_music,
            ffmpeg_path,
            Path(self.am_video_file.text().strip()),
            Path(self.am_audio_file.text().strip()),
            Path(self.am_output_file.text().strip()),
            self.am_replace_audio.isChecked(),
        )

    def run_concat(self):
        ffmpeg_path = self.resolve_ffmpeg_path()
        if not ffmpeg_path:
            self.add_log("需要设置 FFmpeg 路径。")
            return
        self.save_config()
        self.add_log("开始视频拼接任务...")
        self.start_worker(
            concat_two_videos,
            ffmpeg_path,
            Path(self.concat_video_a.text().strip()),
            Path(self.concat_video_b.text().strip()),
            Path(self.concat_output_file.text().strip()),
        )

    def run_compress_preview(self):
        ffmpeg_path = self.resolve_ffmpeg_path()
        if not ffmpeg_path:
            self.add_log("需要设置 FFmpeg 路径。")
            return
        self.save_config()
        self.add_log("生成压缩预览中...")
        output_image = Path("output") / "preview" / "compress_preview.jpg"
        self.start_result_worker(
            generate_compress_preview,
            ffmpeg_path,
            Path(self.compress_input_file.text().strip()),
            output_image,
            self.compress_scale.value(),
            self.handle_compress_preview,
        )

    def run_compress(self):
        ffmpeg_path = self.resolve_ffmpeg_path()
        if not ffmpeg_path:
            self.add_log("需要设置 FFmpeg 路径。")
            return
        self.save_config()
        self.add_log("开始压缩任务...")
        self.start_worker(
            compress_video,
            ffmpeg_path,
            Path(self.compress_input_file.text().strip()),
            Path(self.compress_output_file.text().strip()),
            self.compress_scale.value(),
            self.compress_crf.value(),
            self.compress_preset.currentText(),
            self.compress_use_gpu.isChecked(),
        )

    def start_worker(self, func, *args):
        if self.worker and self.worker.isRunning():
            self.add_log("已有任务在运行。")
            return
        self.worker = Worker(func, *args)
        self.worker.log_signal.connect(self.add_log)
        self.worker.error_signal.connect(self.add_log)
        self.worker.done_signal.connect(lambda: self.add_log("任务完成。"))
        self.worker.start()

    def start_result_worker(self, func, *args):
        if self.worker and self.worker.isRunning():
            self.add_log("已有任务在运行。")
            return
        result_handler = args[-1]
        run_args = args[:-1]
        self.worker = ResultWorker(func, *run_args)
        self.worker.log_signal.connect(self.add_log)
        self.worker.error_signal.connect(self.add_log)
        self.worker.result_signal.connect(result_handler)
        self.worker.done_signal.connect(lambda: self.add_log("任务完成。"))
        self.worker.start()

    def handle_compress_preview(self, image_path: str):
        pixmap = QtGui.QPixmap(image_path)
        if pixmap.isNull():
            self.add_log("预览图加载失败。")
            return
        scaled = pixmap.scaled(
            self.compress_preview_label.size(),
            QtCore.Qt.KeepAspectRatio,
            QtCore.Qt.SmoothTransformation,
        )
        self.compress_preview_label.setPixmap(scaled)

    def closeEvent(self, event):
        self.save_config()
        super().closeEvent(event)

def get_resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller 打包后的临时目录
        return os.path.join(sys._MEIPASS, relative_path)
    # 开发环境的当前目录
    return os.path.join(os.path.abspath("."), relative_path)


def main():
    root_dir = Path(__file__).resolve().parents[1]
    config = AppConfig(root_dir)
    config.load()

    app = QtWidgets.QApplication(sys.argv)

    icon_path = get_resource_path("icon.ico")
    app.setWindowIcon(QIcon(icon_path))

    apply_theme(app)
    window = MainWindow(config)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
