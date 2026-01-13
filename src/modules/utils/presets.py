import os
import json
from .common import debug_log, info_log, error_log
from ..config import AppConfig

class PresetManager:
    @staticmethod
    def _get_dir():
        return AppConfig.get_preset_dir()

    @staticmethod
    def ensure_dir():
        os.makedirs(PresetManager._get_dir(), exist_ok=True)

    @staticmethod
    def save_preset(name, settings):
        PresetManager.ensure_dir()
        filename = f"{name}.json"
        path = os.path.join(PresetManager._get_dir(), filename)
        try:
            with open(path, 'w') as f:
                json.dump(settings, f, indent=4)
            info_log(f"Presets: Saved '{name}' to {path}")
            return True
        except Exception as e:
            error_log(f"Presets: Failed to save {name}: {e}")
            return False

    @staticmethod
    def list_presets():
        PresetManager.ensure_dir()
        presets = {}
        try:
            for f in os.listdir(PresetManager._get_dir()):
                if f.endswith(".json"):
                    name = f.replace(".json", "")
                    path = os.path.join(PresetManager._get_dir(), f)
                    try:
                        with open(path, 'r') as p: presets[name] = json.load(p)
                    except: continue
            return presets
        except: return {}

    @staticmethod
    def delete_preset(name):
        path = os.path.join(PresetManager._get_dir(), f"{name}.json")
        if os.path.exists(path):
            os.remove(path)
            info_log(f"Presets: Deleted '{name}'")
            return True
        return False
