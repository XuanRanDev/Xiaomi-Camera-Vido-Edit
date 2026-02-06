import os
import random
import re
import subprocess
from datetime import datetime
from pathlib import Path

from .ffmpeg_utils import build_atempo_filter


VIDEO_EXTENSIONS = (".mp4", ".avi", ".mkv", ".mov")


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
    log=log_default,
):
    if not input_file.exists():
        raise FileNotFoundError(f"Input video not found: {input_file}")
    output_file = output_file.resolve()
    output_file.parent.mkdir(parents=True, exist_ok=True)
    ratio = max(0.1, min(scale_percent / 100.0, 1.0))

    command = [
        ffmpeg_path,
        "-y",
        "-i",
        str(input_file),
        "-vf",
        f"scale=iw*{ratio}:ih*{ratio}",
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
    log("Compressing video")
    run_command(command, log=log)
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
        f"scale=iw*{ratio}:ih*{ratio}",
        "-q:v",
        "2",
        str(output_image),
    ]
    log("Generating compression preview")
    run_command(command, log=log)
    log(f"Preview image: {output_image}")
    return str(output_image)
