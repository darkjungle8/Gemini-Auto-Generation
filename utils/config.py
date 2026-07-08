import json
import os

DEFAULT_CONFIG = {
    "chrome_profile_base_dir": "",
    "output_dir": "",
    "excel_file": "",
    "parallel_windows": 1,
    "image_name_prefix": "gemini_img",
    "window_accounts": {},
    "retry_count": 3,
    "delay_min": 3,
    "delay_max": 7,
}


class Config:
    """Manages persistent configuration for the application."""

    def __init__(self, config_path=None):
        if config_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(base_dir, "config.json")
        self.config_path = config_path
        self.data = DEFAULT_CONFIG.copy()
        self.load()

    def load(self):
        """Load config from disk, merging with defaults."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    self.data.update(saved)
            except (json.JSONDecodeError, IOError):
                pass

    def save(self):
        """Persist current config to disk."""
        os.makedirs(os.path.dirname(self.config_path) or ".", exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value
        self.save()

    def update(self, updates: dict):
        self.data.update(updates)
        self.save()
