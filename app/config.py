import json
from pathlib import Path


DEFAULT_CONFIG = {
    "ffmpeg_path": "",
    "time_lapse": {
        "base_folder": "",
        "output_file": "output/final_video.mp4",
        "speed_factor": 39.0,
        "fps": 30,
        "hour_start": 8,
        "hour_end": 18,
    },
    "time_lapse2": {
        "base_folder": "",
        "output_file": "output/final_video_v2.mp4",
        "speed_factor": 20.0,
        "fps": 30,
        "hour_start": 7,
        "hour_end": 18,
        "date_start": "",
        "date_end": "",
        "use_gpu": False,
    },
    "inverted": {
        "input_dir": "",
        "output_dir": "output/inverted",
        "speed_factor": 1.0,
        "merge_output": "output/inverted_merged.mp4",
    },
    "add_music": {
        "video_file": "",
        "audio_file": "",
        "output_file": "output/with_bgm.mp4",
        "replace_audio": True,
    },
    "concat": {
        "video_a": "",
        "video_b": "",
        "output_file": "output/concat.mp4",
    },
    "compress": {
        "input_file": "",
        "output_file": "output/compressed.mp4",
        "scale_percent": 70,
        "crf": 28,
        "preset": "medium",
        "use_gpu": False,
    },
}


class AppConfig:
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.path = self.root_dir / "config.json"
        self.data = json.loads(json.dumps(DEFAULT_CONFIG))

    def load(self):
        if not self.path.exists():
            return
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                loaded = json.load(handle)
            self._merge(self.data, loaded)
        except (json.JSONDecodeError, OSError):
            return

    def save(self):
        try:
            with self.path.open("w", encoding="utf-8") as handle:
                json.dump(self.data, handle, indent=2, ensure_ascii=False)
        except OSError:
            return

    def _merge(self, base: dict, incoming: dict):
        for key, value in incoming.items():
            if isinstance(value, dict) and isinstance(base.get(key), dict):
                self._merge(base[key], value)
            else:
                base[key] = value
