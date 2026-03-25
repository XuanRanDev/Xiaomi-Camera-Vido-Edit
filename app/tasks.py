import os
import random
import re
import subprocess
from datetime import datetime
from pathlib import Path

from .ffmpeg_utils import build_atempo_filter


VIDEO_EXTENSIONS = (".mp4", ".avi", ".mkv", ".mov")
TIME_FOLDER_PATTERN = re.compile(r"^(\d{8})(\d{2})$")


def natural_key(value: str):
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", value)]


def log_default(message: str):
    print(message)


def run_command(command, log=log_default):
    log(" ".join(command))
    creationflags = 0
    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        creationflags = subprocess.CREATE_NO_WINDOW
    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=creationflags,
    )
    if result.returncode != 0:
        error_text = result.stderr.decode(errors="ignore")
        raise RuntimeError(error_text.strip() or "ffmpeg failed")


def run_command_stream(command, log=log_default, line_handler=None):
    log(" ".join(command))
    creationflags = 0
    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        creationflags = subprocess.CREATE_NO_WINDOW
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=creationflags,
        text=True,
        encoding="utf-8",
        errors="ignore",
    )
    error_lines = []
    for raw_line in process.stderr:
        line = raw_line.strip()
        if not line:
            continue
        error_lines.append(line)
        if len(error_lines) > 200:
            error_lines.pop(0)
        if line_handler:
            line_handler(line, log)
    process.wait()
    if process.returncode != 0:
        raise RuntimeError("\n".join(error_lines) or "ffmpeg failed")


def _parse_time_folder_name(folder_name: str):
    match = TIME_FOLDER_PATTERN.match(folder_name)
    if not match:
        return None
    day = match.group(1)
    hour = int(match.group(2))
    if hour < 0 or hour > 23:
        return None
    try:
        day_date = datetime.strptime(day, "%Y%m%d").date()
    except ValueError:
        return None
    return day, day_date, hour


def discover_time_lapse2_slots(base_folder: Path):
    if not base_folder.exists():
        raise FileNotFoundError(f"Base folder not found: {base_folder}")
    slots = []
    for root, dirs, _ in os.walk(base_folder):
        for folder_name in dirs:
            parsed = _parse_time_folder_name(folder_name)
            if not parsed:
                continue
            day, day_date, hour = parsed
            folder_path = Path(root) / folder_name
            slots.append((day, day_date, hour, folder_path))
    slots.sort(key=lambda item: (item[0], item[2], item[3].as_posix().lower()))
    return slots


def time_lapse(
    ffmpeg_path: str,
    base_folder: Path,
    output_file: Path,
    speed_factor: float,
    fps: int,
    hour_start: int,
    hour_end: int,
    log=log_default,
):
    if not base_folder.exists():
        raise FileNotFoundError(f"Base folder not found: {base_folder}")

    day_folders = {}
    for root, dirs, _ in os.walk(base_folder):
        for folder_name in dirs:
            if len(folder_name) < 10 or not folder_name[:10].isdigit():
                continue
            day = folder_name[:8]
            hour = int(folder_name[8:10])
            if hour < 0 or hour > 23:
                continue
            folder_path = Path(root) / folder_name
            day_folders.setdefault(day, []).append((hour, folder_path))

    if not day_folders:
        raise RuntimeError("No valid day folders found (expected yyyyMMddHH).")

    output_file = output_file.resolve()
    output_file.parent.mkdir(parents=True, exist_ok=True)
    temp_dir = output_file.parent / "temp" / "time-lapse"
    temp_dir.mkdir(parents=True, exist_ok=True)

    selected_videos = []
    for day in sorted(day_folders.keys()):
        folders = sorted(day_folders[day], key=lambda item: item[0])
        in_range = [folder for hour, folder in folders if hour_start <= hour < hour_end]
        candidates = in_range if in_range else [folder for _, folder in folders]

        available_files = []
        for folder in candidates:
            for file in folder.iterdir():
                if file.suffix.lower() in VIDEO_EXTENSIONS:
                    available_files.append(file)
        if not available_files:
            log(f"{day}: no videos found, skipped.")
            continue
        picked = random.choice(available_files)
        log(f"{day}: selected {picked}")
        selected_videos.append((day, picked))

    if not selected_videos:
        raise RuntimeError("No videos were selected.")

    processed_files = []
    for day, video in selected_videos:
        temp_output = (temp_dir / f"temp_{day}.mp4").resolve()
        command = [
            ffmpeg_path,
            "-y",
            "-i",
            str(video),
            "-filter:v",
            f"setpts={1 / speed_factor}*PTS",
            "-r",
            str(fps),
            "-an",
            "-fflags",
            "+genpts",
            str(temp_output),
        ]
        log(f"Speeding up {video}")
        run_command(command, log=log)
        processed_files.append(temp_output)

    list_file = temp_dir / "file_list.txt"
    with list_file.open("w", encoding="utf-8") as handle:
        for video in processed_files:
            handle.write(f"file '{video.resolve().as_posix()}'\n")

    command = [
        ffmpeg_path,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(list_file),
        "-c:v",
        "libx264",
        "-crf",
        "23",
        "-preset",
        "fast",
        str(output_file),
    ]
    log("Merging videos")
    run_command(command, log=log)

    for file in processed_files:
        file.unlink(missing_ok=True)
    list_file.unlink(missing_ok=True)
    log(f"Time-lapse output: {output_file}")


def time_lapse2(
    ffmpeg_path: str,
    base_folder: Path,
    output_file: Path,
    speed_factor: float,
    fps: int,
    hour_start: int,
    hour_end: int,
    date_start: str,
    date_end: str,
    use_gpu: bool,
    log=log_default,
):
    if hour_start > hour_end:
        raise ValueError("Hour range is invalid: start must be <= end.")
    if date_start and date_end and date_start > date_end:
        raise ValueError("Date range is invalid: start must be <= end.")

    slots = discover_time_lapse2_slots(base_folder)
    if not slots:
        raise RuntimeError("No valid hourly folders found (expected yyyyMMddHH).")

    selected_by_day = {}
    for day, _, hour, folder_path in slots:
        if date_start and day < date_start:
            continue
        if date_end and day > date_end:
            continue
        if hour < hour_start or hour > hour_end:
            continue
        selected_by_day.setdefault(day, []).append((hour, folder_path))

    if not selected_by_day:
        raise RuntimeError("No folders matched the selected date/hour range.")

    output_file = output_file.resolve()
    output_file.parent.mkdir(parents=True, exist_ok=True)
    temp_dir = output_file.parent / "temp" / "time-lapse-v2"
    temp_dir.mkdir(parents=True, exist_ok=True)

    selected_videos = []
    for day in sorted(selected_by_day.keys()):
        hour_folders = sorted(
            selected_by_day[day], key=lambda item: (item[0], item[1].as_posix().lower())
        )
        day_count = 0
        for hour, folder in hour_folders:
            video_files = [item for item in folder.iterdir() if item.suffix.lower() in VIDEO_EXTENSIONS]
            video_files.sort(key=lambda item: natural_key(item.name))
            for video in video_files:
                selected_videos.append((day, hour, video))
                day_count += 1
        log(f"{day}: selected {day_count} videos ({hour_start:02d}-{hour_end:02d}).")

    if not selected_videos:
        raise RuntimeError("No videos found in matched folders.")

    # Fast path: concat source videos first, then speed up in a single ffmpeg run.
    source_list_file = temp_dir / "source_list.txt"
    with source_list_file.open("w", encoding="utf-8") as handle:
        for _, _, video in selected_videos:
            handle.write(f"file '{video.resolve().as_posix()}'\n")

    def fast_line_handler(line: str, logger):
        if "Opening '" in line and "' for reading" in line:
            start = line.find("Opening '") + len("Opening '")
            end = line.find("' for reading", start)
            if end > start:
                current = Path(line[start:end]).name
                logger(f"当前读取: {current}")
            return
        if line.startswith("out_time="):
            logger(f"进度时间: {line.split('=', 1)[1]}")
            return
        if line.startswith("speed="):
            logger(f"编码速度: {line.split('=', 1)[1]}")
            return

    video_codec_args = [
        "-c:v",
        "libx264",
        "-crf",
        "23",
        "-preset",
        "veryfast",
    ]
    if use_gpu:
        video_codec_args = [
            "-c:v",
            "h264_nvenc",
            "-rc:v",
            "vbr",
            "-cq:v",
            "23",
            "-b:v",
            "0",
            "-preset",
            "p4",
            "-pix_fmt",
            "yuv420p",
        ]

    fast_command = [
        ffmpeg_path,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(source_list_file),
        "-vf",
        f"setpts={1 / speed_factor}*PTS,fps={fps}",
        "-an",
        "-progress",
        "pipe:2",
        "-nostats",
        *video_codec_args,
        str(output_file),
    ]
    try:
        mode_text = "GPU" if use_gpu else "CPU"
        log(f"Using fast single-pass mode for time-lapse2 ({mode_text})")
        log(f"Total videos: {len(selected_videos)}")
        run_command_stream(fast_command, log=log, line_handler=fast_line_handler)
        source_list_file.unlink(missing_ok=True)
        log(f"Time-lapse2 output: {output_file}")
        return
    except RuntimeError as fast_exc:
        log(f"Fast mode failed, fallback to compatibility mode: {fast_exc}")
        log(f"Compatibility mode encoder: {'GPU(NVENC)' if use_gpu else 'CPU(libx264)'}")

    fallback_encode_args = [
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
    ]
    if use_gpu:
        fallback_encode_args = [
            "-c:v",
            "h264_nvenc",
            "-rc:v",
            "vbr",
            "-cq:v",
            "24",
            "-b:v",
            "0",
            "-preset",
            "p1",
            "-pix_fmt",
            "yuv420p",
        ]

    processed_files = []
    for index, (day, hour, video) in enumerate(selected_videos, start=1):
        temp_output = (temp_dir / f"temp_{index:06d}.mp4").resolve()
        command = [
            ffmpeg_path,
            "-y",
            "-i",
            str(video),
            "-filter:v",
            f"setpts={1 / speed_factor}*PTS",
            "-r",
            str(fps),
            "-an",
            "-fflags",
            "+genpts",
            *fallback_encode_args,
            str(temp_output),
        ]
        log(f"[{index}/{len(selected_videos)}] speeding {day} {hour:02d} {video.name}")
        run_command(command, log=log)
        processed_files.append(temp_output)

    merged_list_file = temp_dir / "file_list.txt"
    with merged_list_file.open("w", encoding="utf-8") as handle:
        for video in processed_files:
            handle.write(f"file '{video.resolve().as_posix()}'\n")

    merge_command = [
        ffmpeg_path,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(merged_list_file),
        "-c",
        "copy",
        str(output_file),
    ]
    log("Merging videos for time-lapse2 (fallback mode)")
    run_command(merge_command, log=log)

    source_list_file.unlink(missing_ok=True)
    for file in processed_files:
        file.unlink(missing_ok=True)
    merged_list_file.unlink(missing_ok=True)
    log(f"Time-lapse2 output: {output_file}")


def inverted(
    ffmpeg_path: str,
    input_dir: Path,
    output_dir: Path,
    speed_factor: float,
    merge_output: Path,
    log=log_default,
):
    if not input_dir.exists():
        raise FileNotFoundError(f"Input folder not found: {input_dir}")
    output_dir = output_dir.resolve()
    merge_output = merge_output.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    merge_output.parent.mkdir(parents=True, exist_ok=True)

    video_files = [file for file in input_dir.iterdir() if file.suffix.lower() in VIDEO_EXTENSIONS]
    video_files.sort(key=lambda item: natural_key(item.name))
    if not video_files:
        raise RuntimeError("No videos found in input directory.")

    processed_files = []
    for video in video_files:
        output_file = (output_dir / f"processed_{video.name}").resolve()
        atempo = build_atempo_filter(speed_factor)
        audio_filter = f"areverse,{atempo}" if speed_factor != 1.0 else "areverse"
        command = [
            ffmpeg_path,
            "-y",
            "-i",
            str(video),
            "-vf",
            f"reverse,setpts={1 / speed_factor}*PTS",
            "-af",
            audio_filter,
            str(output_file),
        ]
        log(f"Processing {video}")
        run_command(command, log=log)
        processed_files.append(output_file)

    list_file = output_dir / "file_list.txt"
    with list_file.open("w", encoding="utf-8") as handle:
        for video in processed_files:
            handle.write(f"file '{video.resolve().as_posix()}'\n")

    command = [
        ffmpeg_path,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(list_file),
        "-c:v",
        "libx264",
        "-crf",
        "23",
        "-preset",
        "fast",
        "-c:a",
        "aac",
        str(merge_output),
    ]
    log("Merging reversed videos")
    run_command(command, log=log)

    list_file.unlink(missing_ok=True)
    log(f"Inverted output: {merge_output}")


def add_music(
    ffmpeg_path: str,
    video_file: Path,
    audio_file: Path,
    output_file: Path,
    replace_audio: bool,
    log=log_default,
):
    if not video_file.exists():
        raise FileNotFoundError(f"Video not found: {video_file}")
    if not audio_file.exists():
        raise FileNotFoundError(f"Audio not found: {audio_file}")
    output_file = output_file.resolve()
    output_file.parent.mkdir(parents=True, exist_ok=True)
    if replace_audio:
        command = [
            ffmpeg_path,
            "-y",
            "-i",
            str(video_file),
            "-stream_loop",
            "-1",
            "-i",
            str(audio_file),
            "-c:v",
            "copy",
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-shortest",
            str(output_file),
        ]
        log("Replacing audio with background music")
        run_command(command, log=log)
    else:
        command = [
            ffmpeg_path,
            "-y",
            "-i",
            str(video_file),
            "-stream_loop",
            "-1",
            "-i",
            str(audio_file),
            "-filter_complex",
            "[0:a][1:a]amix=inputs=2:duration=shortest:dropout_transition=2[a]",
            "-map",
            "0:v:0",
            "-map",
            "[a]",
            "-c:v",
            "copy",
            "-shortest",
            str(output_file),
        ]
        log("Mixing background music with original audio")
        run_command(command, log=log)
    log(f"BGM output: {output_file}")


def concat_two_videos(
    ffmpeg_path: str,
    video_a: Path,
    video_b: Path,
    output_file: Path,
    log=log_default,
):
    if not video_a.exists():
        raise FileNotFoundError(f"Video A not found: {video_a}")
    if not video_b.exists():
        raise FileNotFoundError(f"Video B not found: {video_b}")
    output_file = output_file.resolve()
    output_file.parent.mkdir(parents=True, exist_ok=True)
    list_file = output_file.parent / "concat_list.txt"
    with list_file.open("w", encoding="utf-8") as handle:
        handle.write(f"file '{video_a.resolve().as_posix()}'\n")
        handle.write(f"file '{video_b.resolve().as_posix()}'\n")

    command = [
        ffmpeg_path,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(list_file),
        "-c",
        "copy",
        str(output_file),
    ]
    log("Concatenating videos")
    run_command(command, log=log)
    list_file.unlink(missing_ok=True)
    log(f"Concat output: {output_file}")


def compress_video(
    ffmpeg_path: str,
    input_file: Path,
    output_file: Path,
    scale_percent: int,
    crf: int,
    preset: str,
    use_gpu: bool,
    log=log_default,
):
    if not input_file.exists():
        raise FileNotFoundError(f"Input video not found: {input_file}")
    output_file = output_file.resolve()
    output_file.parent.mkdir(parents=True, exist_ok=True)
    ratio = max(0.1, min(scale_percent / 100.0, 1.0))

    cpu_command = [
        ffmpeg_path,
        "-y",
        "-i",
        str(input_file),
        "-vf",
        f"scale=trunc(iw*{ratio}/2)*2:trunc(ih*{ratio}/2)*2",
        "-c:v",
        "libx264",
        "-crf",
        str(crf),
        "-preset",
        preset,
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        str(output_file),
    ]

    if use_gpu:
        gpu_command = [
            ffmpeg_path,
            "-y",
            "-i",
            str(input_file),
            "-vf",
            f"scale=trunc(iw*{ratio}/2)*2:trunc(ih*{ratio}/2)*2",
            "-c:v",
            "h264_nvenc",
            "-rc:v",
            "vbr",
            "-cq:v",
            str(crf),
            "-b:v",
            "0",
            "-preset",
            "p4",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            str(output_file),
        ]
        log("Compressing video (GPU)")
        try:
            run_command(gpu_command, log=log)
        except RuntimeError as exc:
            log(f"GPU encode failed, fallback to CPU: {exc}")
            run_command(cpu_command, log=log)
    else:
        log("Compressing video (CPU)")
        run_command(cpu_command, log=log)
    log(f"Compressed output: {output_file}")


def generate_compress_preview(
    ffmpeg_path: str,
    input_file: Path,
    output_image: Path,
    scale_percent: int,
    log=log_default,
):
    if not input_file.exists():
        raise FileNotFoundError(f"Input video not found: {input_file}")
    output_image.parent.mkdir(parents=True, exist_ok=True)
    ratio = max(0.1, min(scale_percent / 100.0, 1.0))

    command = [
        ffmpeg_path,
        "-y",
        "-ss",
        "00:00:01",
        "-i",
        str(input_file),
        "-frames:v",
        "1",
        "-vf",
        f"scale=trunc(iw*{ratio}/2)*2:trunc(ih*{ratio}/2)*2",
        "-q:v",
        "2",
        str(output_image),
    ]
    log("Generating compression preview")
    run_command(command, log=log)
    log(f"Preview image: {output_image}")
    return str(output_image)
