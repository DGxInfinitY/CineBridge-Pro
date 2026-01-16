import os
import sys
import platform
from datetime import datetime
from PyQt6.QtCore import QStandardPaths

# Global Flags
DEBUG_MODE = False
GUI_LOG_QUEUE = []

class AppConfig:
    """Centralized configuration for paths and OS standards."""
    APP_NAME = "cinebridge-pro"
    
    @staticmethod
    def get_data_dir():
        # Standard location for app data (Linux: ~/.local/share, Windows: AppData/Local)
        path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
        if not path: # Fallback
            path = os.path.join(os.path.expanduser("~"), ".cinebridge-pro")
        return path

    @staticmethod
    def get_log_path():
        return os.path.join(AppConfig.get_data_dir(), "logs", "cinebridge.log")

    @staticmethod
    def get_preset_dir():
        return os.path.join(AppConfig.get_data_dir(), "presets")

    @staticmethod
    def get_history_dir():
        return os.path.join(AppConfig.get_data_dir(), "history")

class AppLogger:
    _log_path = "" # Initialized in init_log

    @staticmethod
    def init_log():
        """Ensures log directory exists and writes a session header."""
        AppLogger._log_path = AppConfig.get_log_path()
        log_dir = os.path.dirname(AppLogger._log_path)
        try:
            os.makedirs(log_dir, exist_ok=True)
            with open(AppLogger._log_path, "a") as f:
                f.write(f"\n{'='*60}\n")
                f.write(f"SESSION START: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Platform: {platform.system()} | Python: {sys.version}\n")
                f.write(f"{ '='*60}\n")
        except Exception as e:
            print(f"CRITICAL: Could not initialize log file: {e}")

    @staticmethod
    def log(msg, level="DEBUG"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted = f"[{level}] {timestamp} | {msg}"
        
        try:
            if AppLogger._log_path:
                with open(AppLogger._log_path, "a") as f:
                    f.write(formatted + "\n")
        except: pass

        # Access global DEBUG_MODE
        global DEBUG_MODE
        if DEBUG_MODE or level in ["INFO", "ERROR"]:
            gui_msg = f"[{level} {timestamp}] {msg}"
            print(formatted)
            GUI_LOG_QUEUE.append(gui_msg)
            if len(GUI_LOG_QUEUE) > 500: GUI_LOG_QUEUE.pop(0)

def debug_log(msg): AppLogger.log(msg, "DEBUG")
def info_log(msg): AppLogger.log(msg, "INFO")
def error_log(msg): AppLogger.log(msg, "ERROR")
