import os
import sys
import shutil
import platform
import subprocess
from PyQt6.QtCore import QSettings
from ..config import debug_log, error_log

class EnvUtils:
    @staticmethod
    def get_clean_env():
        env = os.environ.copy()
        if hasattr(sys, '_MEIPASS') and platform.system() == 'Linux':
            if 'LD_LIBRARY_PATH_ORIG' in env: env['LD_LIBRARY_PATH'] = env['LD_LIBRARY_PATH_ORIG']
            elif 'LD_LIBRARY_PATH' in env: del env['LD_LIBRARY_PATH']
        return env

    @staticmethod
    def open_file(path):
        if not os.path.exists(path): return
        try:
            if platform.system() == "Windows": os.startfile(path)
            elif platform.system() == "Darwin": subprocess.Popen(["open", path])
            else: subprocess.Popen(["xdg-open", path])
        except Exception as e: error_log(f"UI: Failed to open file {path}: {e}")

class DependencyManager:
    @staticmethod
    def get_ffmpeg_path():
        settings = QSettings("CineBridgePro", "Config")
        custom_path = settings.value("ffmpeg_custom_path", "")
        if custom_path and os.path.exists(custom_path): return custom_path
        if hasattr(sys, '_MEIPASS'):
            bundle_path = os.path.join(sys._MEIPASS, "ffmpeg")
            if platform.system() == "Windows": bundle_path += ".exe"
            if os.path.exists(bundle_path): return bundle_path
        script_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        local_bin = os.path.join(script_dir, "bin", "ffmpeg") 
        if platform.system() == "Windows": local_bin += ".exe"
        if os.path.exists(local_bin): return local_bin
        return shutil.which("ffmpeg")
    
    @staticmethod
    def get_binary_path(binary_name):
        if hasattr(sys, '_MEIPASS'):
            bundle_path = os.path.join(sys._MEIPASS, binary_name)
            if platform.system() == "Windows": bundle_path += ".exe"
            if os.path.exists(bundle_path): return bundle_path
        script_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        local_bin = os.path.join(script_dir, "bin", binary_name)
        if platform.system() == "Windows": local_bin += ".exe"
        if os.path.exists(local_bin): return local_bin
        return shutil.which(binary_name)

    _hw_cache = None

    @staticmethod
    def detect_hw_accel():
        if DependencyManager._hw_cache is not None: return DependencyManager._hw_cache
        ffmpeg = DependencyManager.get_ffmpeg_path()
        if not ffmpeg: return None
        try:
            res = subprocess.run([ffmpeg, '-hwaccels'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=EnvUtils.get_clean_env())
            output = res.stdout + res.stderr
            enc_res = subprocess.run([ffmpeg, '-encoders'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=EnvUtils.get_clean_env())
            enc_out = enc_res.stdout
            result = None
            if "cuda" in output and "h264_nvenc" in enc_out: result = "cuda"
            elif "qsv" in output and "h264_qsv" in enc_out: result = "qsv"
            elif "vaapi" in output and "h264_vaapi" in enc_out: result = "vaapi"
            DependencyManager._hw_cache = result
            return result
        except: return None
