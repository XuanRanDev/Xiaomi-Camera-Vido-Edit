import shutil
from pathlib import Path


def find_ffmpeg(config_path: str) -> str:
    if config_path:
        path = Path(config_path)
        if path.exists():
            return str(path)
    resolved = shutil.which("ffmpeg")
    return resolved or ""


def build_atempo_filter(speed_factor: float) -> str:
    if speed_factor <= 0:
        return "atempo=1.0"
    if speed_factor == 1.0:
        return "atempo=1.0"
    parts = []
    remaining = speed_factor
    while remaining > 2.0:
        parts.append("atempo=2.0")
        remaining /= 2.0
    while remaining < 0.5:
        parts.append("atempo=0.5")
        remaining /= 0.5
    parts.append(f"atempo={remaining:.4f}")
    return ",".join(parts)

