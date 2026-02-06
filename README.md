# 小米摄像头视频处理（PySide6 GUI）

这是一个基于 PySide6 的桌面 GUI 工具，用于批量处理小米摄像头（或类似结构）长期录制的视频。它将“每天选一条视频 → 统一加速/倒放 → 合并成一个成片”的流程完整可视化，并提供一键加 BGM 的功能。核心目标是帮助你把海量、分散的监控视频整理成可快速回顾的时间线成片。

## 这个项目是干什么的？
你可能有大量按天/小时存放的录像（例如 NAS/硬盘里的摄像头视频）。手动从每天视频里挑一段、加速、合并非常耗时。本项目提供三个清晰的处理流程，让你可以：
- **延时摄影**：从每一天里随机选一段视频，加速后合并成一个时间线视频，用于快速回顾一整年。
- **倒放变速**：对一批视频做倒放与变速处理，再合并为一个成片。
- **添加音乐**：给已有视频快速叠加背景音乐，输出成新视频。

## 解决了什么问题？
- **批量处理**：自动遍历目录、批量处理视频，减少人工操作。
- **高效预览**：把“全年录像”压缩成十几分钟，方便快速回顾。
- **可复用流程**：所有参数可保存、复用，不需要每次重复配置。
- **可视化操作**：避免命令行操作门槛，所有功能都能在 GUI 中完成。
- **安全无损**：只读取原视频，所有处理结果都会输出为新文件。

## 功能概览
### 1) 延时摄影（Time-lapse）
适用于大量按日期/小时命名的录像文件夹。
- **输入**：一个基础目录，其下是形如 `yyyyMMddHH` 的子目录。
- **处理**：
  - 按天分组，从每天的 8-20 点目录中随机选一条视频（如果没有符合时间段，会从当天目录中选一条备选）。
  - 对每条视频进行加速（默认 39x），统一帧率。
  - 将所有处理后的短视频按日期顺序合并。
- **输出**：一个时间线合并视频（默认 `output/final_video.mp4`）。

### 2) 倒放变速（Inverted）
适用于想把一批视频整体“倒放 + 变速 + 合并”的场景。
- **输入**：一个目录内的多段视频。
- **处理**：
  - 每条视频进行倒放处理，可设置变速倍率。
  - 处理后的文件按自然顺序合并。
- **输出**：倒放变速后的合并成片（默认 `output/inverted_merged.mp4`）。

### 3) 添加音乐（Add Music）
适用于对已有成片进行 BGM 添加。
- **输入**：一个视频文件 + 一个音频文件。
- **处理**：保留原视频流，可选择覆盖原声或与原声混合。
- **输出**：带背景音乐的视频（默认 `output/with_bgm.mp4`）。

### 4) 视频拼接（Concat Two Videos）
把两个视频按顺序直接拼接（视频 2 接在视频 1 后面），不做重新编码。
- **输入**：视频 1 + 视频 2。
- **处理**：仅拼接，不转码。
- **输出**：拼接成片（默认 `output/concat.mp4`）。

## 目录与输出规则
- 所有输出默认放在 `output/` 目录。
- 中间文件会放在 `output/temp/` 下（任务完成会自动清理）。

## 安装与运行
### 依赖
- Python 3.10+
- FFmpeg（系统 PATH 可用，或在 GUI 中手动选择）
- PySide6

### 安装依赖
```bash
pip install -r requirements.txt
```

### 运行
```bash
python -m app.main
```

## 配置说明
所有配置保存在项目根目录的 `config.json` 中，包含：
- FFmpeg 路径（如果系统 PATH 找不到，会提示手动选择）
- 各模块的输入/输出路径
- 速度倍数、帧率、时间范围等参数

配置会在关闭窗口时自动保存，下次打开自动恢复。

## 常见使用场景
- **年终回顾**：用延时摄影快速生成全年变化视频。
- **项目施工记录**：每天固定时间拍一段，按天合成为时间线视频。
- **趣味倒放**：批量做倒放变速视频，合成短片。
- **快速配乐**：成片后快速加 BGM。

## 注意事项
- 延时摄影模式要求子目录命名格式为 `yyyyMMddHH`，否则无法识别。
- FFmpeg 未安装或未配置时，请在 GUI 中选择 `ffmpeg.exe`。
- 处理大量视频时耗时较长，建议使用本地硬盘目录。

---

# Xiaomi Camera Video Edit (PySide6 GUI)

This is a PySide6 desktop GUI tool for batch-processing long-term Xiaomi camera videos (or any similar structure). It turns “pick one clip per day → speed up / reverse → merge into a single timeline” into a visual workflow, and also provides a one-click way to add background music.

## What is this project for?
If you have massive camera recordings stored by day/hour (e.g., on NAS or HDD), manually selecting clips, speeding them up, and merging them is tedious. This project provides three clear processing flows:
- **Time-lapse**: randomly pick one video per day, speed it up, and merge into a timeline.
- **Inverted**: reverse + speed change for each clip, then merge.
- **Add Music**: combine an existing video with a background audio track.

## What problems does it solve?
- **Batch processing**: automate traversal and processing of many clips.
- **Fast review**: compress months or a year of footage into minutes.
- **Reusable workflow**: all parameters are saved and reusable.
- **GUI-driven**: no command line required.
- **Non-destructive**: source videos are never modified; outputs are new files.

## Features
### 1) Time-lapse
Designed for folder structures with date-hour names.
- **Input**: a base folder containing subfolders like `yyyyMMddHH`.
- **Process**:
  - Group by day; randomly select one clip between 08:00–20:00 (fallback to any clip that day).
  - Speed up each clip (default 39x), normalize FPS.
  - Merge into a timeline in date order.
- **Output**: merged timeline video (default `output/final_video.mp4`).

### 2) Inverted
Reverse + speed up/down for a batch of clips.
- **Input**: a directory of video files.
- **Process**:
  - Reverse each clip, apply speed factor.
  - Merge processed clips in natural order.
- **Output**: merged reversed video (default `output/inverted_merged.mp4`).

### 3) Add Music
Add background music to an existing video.
- **Input**: one video file + one audio file.
- **Process**: keep the video stream, choose to replace or mix original audio.
- **Output**: video with BGM (default `output/with_bgm.mp4`).

### 4) Concat Two Videos
Append Video B after Video A without re-encoding.
- **Input**: Video A + Video B.
- **Process**: concat only, no transcoding.
- **Output**: concatenated video (default `output/concat.mp4`).

## Output structure
- All outputs go to `output/` by default.
- Temporary files are stored under `output/temp/` and cleaned after completion.

## Install & Run
### Requirements
- Python 3.10+
- FFmpeg (available in PATH, or selected in the GUI)
- PySide6

### Install dependencies
```bash
pip install -r requirements.txt
```

### Run
```bash
python -m app.main
```

## Configuration
All settings are stored in `config.json` at the project root:
- FFmpeg path (prompted if not found in PATH)
- Input/output paths per module
- Speed factor, FPS, time range, etc.

Settings are saved automatically on exit and restored on next launch.

## Typical use cases
- **Annual recap**: generate a yearly timeline video quickly.
- **Construction logs**: daily recordings merged into a single time-lapse.
- **Fun reverse edits**: batch reverse and speed-change clips.
- **Quick soundtrack**: add BGM to a finished video.

## Notes
- Time-lapse requires subfolders named `yyyyMMddHH`.
- If FFmpeg is not installed or missing from PATH, select `ffmpeg.exe` in the GUI.
- Processing large volumes of video can be time-consuming; local disk is recommended.
