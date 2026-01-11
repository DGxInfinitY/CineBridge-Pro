import sys
import os
import shutil
import re
import time
import platform
import signal
import subprocess
import hashlib
import json
from datetime import datetime
from collections import deque

try:
    import xxhash
    HAS_XXHASH = True
except ImportError:
    HAS_XXHASH = False

# PyQt6 Imports
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                             QFileDialog, QProgressBar, QTextEdit, QMessageBox, 
                             QCheckBox, QGroupBox, QComboBox, QTabWidget, QFrame, 
                             QSizePolicy, QSplitter, QFormLayout, QDialog,
                             QListWidget, QAbstractItemView, QToolButton, QRadioButton, QButtonGroup,
                             QTableWidget, QTableWidgetItem, QHeaderView, QMenu, QTreeWidget, QTreeWidgetItem, QGridLayout, QInputDialog)
from PyQt6.QtGui import QAction, QPalette, QColor, QIcon, QFont, QDragEnterEvent, QDropEvent, QPixmap, QImage
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QSettings, QTimer, QMimeData, QObject, QSize, QStandardPaths

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

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
                f.write(f"{'='*60}\n")
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

        if DEBUG_MODE or level in ["INFO", "ERROR"]:
            gui_msg = f"[{level} {timestamp}] {msg}"
            print(formatted)
            GUI_LOG_QUEUE.append(gui_msg)
            if len(GUI_LOG_QUEUE) > 500: GUI_LOG_QUEUE.pop(0)

def debug_log(msg): AppLogger.log(msg, "DEBUG")
def info_log(msg): AppLogger.log(msg, "INFO")
def error_log(msg): AppLogger.log(msg, "ERROR")

# =============================================================================
# BACKEND UTILS
# =============================================================================

class EnvUtils:
    @staticmethod
    def get_clean_env():
        env = os.environ.copy()
        if hasattr(sys, '_MEIPASS') and platform.system() == 'Linux':
            if 'LD_LIBRARY_PATH_ORIG' in env:
                env['LD_LIBRARY_PATH'] = env['LD_LIBRARY_PATH_ORIG']
            elif 'LD_LIBRARY_PATH' in env:
                del env['LD_LIBRARY_PATH']
        return env

    @staticmethod
    def open_file(path):
        """Opens a file using the system's default application."""
        if not os.path.exists(path): return
        try:
            if platform.system() == "Windows":
                os.startfile(path)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            error_log(f"UI: Failed to open file {path}: {e}")

class DependencyManager:
    @staticmethod
    def get_ffmpeg_path():
        settings = QSettings("CineBridgePro", "Config")
        custom_path = settings.value("ffmpeg_custom_path", "")
        if custom_path and os.path.exists(custom_path):
            debug_log(f"FFmpeg: Using custom path {custom_path}")
            return custom_path

        if hasattr(sys, '_MEIPASS'):
            bundle_path = os.path.join(sys._MEIPASS, "ffmpeg")
            if platform.system() == "Windows": bundle_path += ".exe"
            if os.path.exists(bundle_path):
                debug_log(f"FFmpeg: Found bundled binary at {bundle_path}")
                return bundle_path
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        local_bin = os.path.join(script_dir, "bin", "ffmpeg")
        if platform.system() == "Windows": local_bin += ".exe"
        if os.path.exists(local_bin):
            debug_log(f"FFmpeg: Found local binary at {local_bin}")
            return local_bin
        
        system_bin = shutil.which("ffmpeg")
        if system_bin:
            debug_log(f"FFmpeg: Found system binary at {system_bin}")
            return system_bin
        
        error_log("FFmpeg binary NOT found in any known location.")
        return None

    @staticmethod
    def detect_hw_accel():
        ffmpeg = DependencyManager.get_ffmpeg_path()
        if not ffmpeg: return None
        try:
            res = subprocess.run([ffmpeg, '-hwaccels'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=EnvUtils.get_clean_env())
            output = res.stdout + res.stderr
            enc_res = subprocess.run([ffmpeg, '-encoders'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=EnvUtils.get_clean_env())
            enc_out = enc_res.stdout
            if "cuda" in output and "h264_nvenc" in enc_out: 
                debug_log("HW: Detected NVIDIA CUDA/NVENC")
                return "cuda"
            if "qsv" in output and "h264_qsv" in enc_out: 
                debug_log("HW: Detected Intel QuickSync")
                return "qsv"
            if "vaapi" in output: 
                debug_log("HW: Detected Linux VAAPI")
                return "vaapi"
        except Exception as e:
            debug_log(f"HW Detection Error: {e}")
        return None

class TranscodeEngine:
    @staticmethod
    def build_command(input_path, output_path, settings, use_gpu=False):
        ffmpeg_bin = DependencyManager.get_ffmpeg_path()
        if not ffmpeg_bin: return None
        v_codec = settings.get('v_codec', 'dnxhd')
        v_profile = settings.get('v_profile', 'dnxhr_hq')
        a_codec = settings.get('a_codec', 'pcm_s16le')
        cmd = [ffmpeg_bin, '-y']
        hw_method = DependencyManager.detect_hw_accel() if use_gpu else None
        
        if hw_method == "cuda": cmd.extend(['-hwaccel', 'cuda'])
        elif hw_method == "qsv": cmd.extend(['-hwaccel', 'qsv', '-c:v', 'h264_qsv'])
        elif hw_method == "vaapi": cmd.extend(['-hwaccel', 'vaapi', '-hwaccel_device', '/dev/dri/renderD128', '-hwaccel_output_format', 'yuv420p'])
        
        cmd.extend(['-i', input_path])
        
        if settings.get("lut_path"):
            lut_file = settings['lut_path'].replace('\\', '/').replace(':', '\\:').replace("'", "'\\''")
            cmd.extend(['-vf', f"lut3d='{lut_file}'"])

        if v_codec in ['dnxhd', 'prores_ks']:
            cmd.extend(['-c:v', v_codec, '-profile:v', v_profile])
            if v_codec == 'dnxhd': cmd.extend(['-pix_fmt', 'yuv422p'])
        elif v_codec in ['libx264', 'libx265']:
            if hw_method == "cuda" and v_codec == 'libx264': cmd.extend(['-c:v', 'h264_nvenc', '-preset', 'fast'])
            elif hw_method == "cuda" and v_codec == 'libx265': cmd.extend(['-c:v', 'hevc_nvenc', '-preset', 'fast'])
            elif hw_method == "qsv" and v_codec == 'libx264': cmd.extend(['-c:v', 'h264_qsv', '-preset', 'fast'])
            elif hw_method == "qsv" and v_codec == 'libx265': cmd.extend(['-c:v', 'hevc_qsv', '-preset', 'fast'])
            elif hw_method == "vaapi" and v_codec == 'libx264': cmd.extend(['-c:v', 'h264_vaapi']) 
            else:
                cmd.extend(['-c:v', v_codec, '-preset', 'fast', '-crf', '18'])
                if v_codec == 'libx264': cmd.extend(['-pix_fmt', 'yuv420p'])
        
        if a_codec == 'pcm_s16le': cmd.extend(['-c:a', 'pcm_s16le', '-ar', '48000'])
        elif a_codec == 'aac': cmd.extend(['-c:a', 'aac', '-b:a', '320k', '-ar', '48000'])
        
        if settings.get('audio_fix'):
            cmd.extend(['-af', 'aresample=async=1:min_comp=0.01:first_pts=0'])

        cmd.append(output_path)
        debug_log(f"FFmpeg CMD: {' '.join(cmd)}")
        return cmd

    @staticmethod
    def get_duration(input_path):
        ffprobe = DependencyManager.get_binary_path("ffprobe")
        if not ffprobe: return 0
        try:
            cmd = [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", input_path]
            startupinfo = None
            if platform.system() == 'Windows':
                startupinfo = subprocess.STARTUPINFO(); startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            result = subprocess.run(cmd, capture_output=True, text=True, startupinfo=startupinfo, env=EnvUtils.get_clean_env())
            return float(result.stdout.strip())
        except: return 0

    @staticmethod
    def parse_progress(line, total_duration):
        time_match = re.search(r"time=(\d+):(\d+):(\d+\.\d+)", line)
        speed_match = re.search(r"speed=\s*(\d+\.?\d*)x", line)
        fps_match = re.search(r"fps=\s*(\d+)", line)
        progress = 0
        status_str = ""
        if time_match and total_duration > 0:
            hours, minutes, seconds = map(float, time_match.groups())
            current_seconds = hours * 3600 + minutes * 60 + seconds
            progress = int((current_seconds / total_duration) * 100)
        parts = []
        if fps_match: parts.append(f"{fps_match.group(1)} fps")
        if speed_match: parts.append(f"{speed_match.group(1)}x Speed")
        if parts: status_str = " | ".join(parts)
        return progress, status_str

class MediaInfoExtractor:
    @staticmethod
    def get_info(input_path):
        ffprobe = DependencyManager.get_binary_path("ffprobe")
        if not ffprobe: return {"error": "ffprobe not found"}
        try:
            cmd = [ffprobe, "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", input_path]
            startupinfo = None
            if platform.system() == 'Windows':
                startupinfo = subprocess.STARTUPINFO(); startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            result = subprocess.run(cmd, capture_output=True, text=True, startupinfo=startupinfo, env=EnvUtils.get_clean_env())
            if result.returncode != 0: return {"error": "Failed to read file"}
            data = json.loads(result.stdout)
            info = {
                "filename": os.path.basename(input_path),
                "container": data.get("format", {}).get("format_long_name", "Unknown"),
                "size_mb": float(data.get("format", {}).get("size", 0)) / (1024*1024),
                "duration": float(data.get("format", {}).get("duration", 0)),
                "video_streams": [], "audio_streams": []
            }
            for stream in data.get("streams", []):
                if stream["codec_type"] == "video":
                    v_info = {
                        "codec": stream.get("codec_name", "Unknown"), "profile": stream.get("profile", ""),
                        "resolution": f"{stream.get('width')}x{stream.get('height')}", "fps": stream.get("r_frame_rate", "0/0"),
                        "pix_fmt": stream.get("pix_fmt", ""), "bitrate": int(stream.get("bit_rate", 0)) / 1000 if stream.get("bit_rate") else 0
                    }
                    info["video_streams"].append(v_info)
                elif stream["codec_type"] == "audio":
                    a_info = {
                        "codec": stream.get("codec_name", "Unknown"), "channels": stream.get("channels", 0),
                        "sample_rate": stream.get("sample_rate", 0), "language": stream.get("tags", {}).get("language", "und")
                    }
                    info["audio_streams"].append(a_info)
            return info
        except Exception as e: return {"error": str(e)}

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
                        with open(path, 'r') as p:
                            presets[name] = json.load(p)
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

# =============================================================================
# NOTIFICATION SYSTEM
# =============================================================================
class SystemNotifier:
    @staticmethod
    def notify(title, message):
        """Triggers a cross-platform system notification and sound."""
        QApplication.beep()
        system = platform.system()
        try:
            if system == "Linux":
                subprocess.Popen(['notify-send', '-a', 'CineBridge Pro', title, message])
            elif system == "Darwin":
                script = f'display notification "{message}" with title "{title}"'
                subprocess.run(["osascript", "-e", script])
            elif system == "Windows":
                ps_script = f"""
                [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null;
                $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02);
                $xml = $template.GetXml();
                $text = $template.GetElementsByTagName("text");
                $text[0].AppendChild($template.CreateTextNode("{title}")) > $null;
                $text[1].AppendChild($template.CreateTextNode("{message}")) > $null;
                $toast = [Windows.UI.Notifications.ToastNotification]::new($template);
                [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("CineBridge Pro").Show($toast);
                """
                subprocess.Popen(["powershell", "-Command", ps_script], creationflags=subprocess.CREATE_NO_WINDOW)
        except Exception as e:
            debug_log(f"Notification failed: {e}")

class DeviceRegistry:
    VIDEO_EXTS = {'.MP4', '.MOV', '.MKV', '.INSV', '.360', '.AVI', '.MXF', '.CRM', '.BRAW', '.VR'}
    PHOTO_EXTS = {'.JPG', '.JPEG', '.PNG', '.ARW', '.CR2', '.CR3', '.DNG', '.GPR', '.HEIC'}
    AUDIO_EXTS = {'.WAV', '.MP3', '.AAC'}
    MISC_EXTS = {'.SRT', '.LRV', '.THM', '.XML', '.BIM', '.RSV', '.AAE'}

    @staticmethod
    def get_all_valid_exts():
        return DeviceRegistry.VIDEO_EXTS | DeviceRegistry.PHOTO_EXTS | DeviceRegistry.AUDIO_EXTS | DeviceRegistry.MISC_EXTS

    PROFILES = {
        "Sony Pro (Alpha/FX)": {
            "signatures": ["M4ROOT", "AVCHD"], 
            "roots": ["private/M4ROOT/CLIP", "PRIVATE/M4ROOT/CLIP", "private/M4ROOT", "PRIVATE/AVCHD/BDMV/STREAM"],
            "exts": {'.MXF', '.MP4', '.XML', '.BIM', '.RSV'}
        },
        "Blackmagic Design": {
            "signatures": ["Blackmagic", "BRAW"],
            "roots": ["."], 
            "exts": {'.BRAW', '.MOV', '.VR'}
        },
        "Canon EOS/Cinema": {
            "signatures": ["100CANON", "CONTENTS"],
            "roots": ["DCIM/100CANON", "CONTENTS/CLIPS001"],
            "exts": {'.CRM', '.MXF', '.MP4', '.MOV', '.CR2', '.CR3'}
        },
        "GoPro Hero": {
            "signatures": ["GOPRO", "HERO"],
            "roots": ["DCIM/100GOPRO"],
            "exts": {'.MP4', '.LRV', '.THM', '.JPG', '.GPR'}
        },
        "DJI Drone/Osmo": {
            "signatures": ["DJI", "100MEDIA"],
            "roots": ["DCIM/100MEDIA", "DCIM/101MEDIA"],
            "exts": {'.MP4', '.MOV', '.DNG', '.JPG', '.SRT'}
        },
        "Insta360": {
            "signatures": ["Insta360"],
            "roots": ["DCIM/Camera01", "DCIM/FileGroup01", "."],
            "exts": {'.INSV', '.INSP', '.LOG', '.LRV'}
        },
        "Panasonic Lumix": {
            "signatures": ["LUMIX", "100_PANA"],
            "roots": ["DCIM/100_PANA", "PRIVATE/AVCHD/BDMV/STREAM"],
            "exts": {'.MOV', '.MP4', '.RW2'}
        }
    }

    @staticmethod
    def safe_list_dir(path, timeout=5):
        if platform.system() == "Linux" and ("gvfs" in path or "mtp" in path.lower()):
            try:
                result = subprocess.run(['ls', '-1', path], capture_output=True, text=True, timeout=timeout, env=EnvUtils.get_clean_env())
                if result.returncode == 0: return [os.path.join(path, l.strip()) for l in result.stdout.splitlines() if l.strip()]
            except: return []
            return []
        else:
            try: return [os.path.join(path, f) for f in os.listdir(path)] if os.path.isdir(path) else []
            except: return []

    @staticmethod
    def identify(mount_point, usb_hints=set()):
        debug_log(f"Registry: Identifying {mount_point} | USB Hints: {usb_hints}")
        root_items = DeviceRegistry.safe_list_dir(mount_point)
        if not root_items: 
            debug_log(f"Registry: {mount_point} is inaccessible or empty.")
            return "Generic Storage", mount_point, None

        def find_path(base, sub_path):
            curr = base; parts = sub_path.split('/')
            for part in parts:
                if part == ".": continue
                found = False
                items = DeviceRegistry.safe_list_dir(curr)
                for item_path in items:
                    item_name = os.path.basename(item_path)
                    if item_name.lower() == part.lower():
                        curr = item_path; found = True; break
                if not found: return None
            return curr

        # 1. Structure Match (Reliable)
        for name, profile in DeviceRegistry.PROFILES.items():
            for root_hint in profile['roots']:
                found_root = find_path(mount_point, root_hint)
                if found_root:
                    if root_hint == "." or root_hint == "":
                        has_sig = False
                        try:
                            items = DeviceRegistry.safe_list_dir(found_root)
                            for item_path in items:
                                item_name = os.path.basename(item_path)
                                if any(s.lower() in item_name.lower() for s in profile['signatures']):
                                    has_sig = True; break
                                if any(item_name.upper().endswith(e) for e in profile['exts']):
                                    has_sig = True; break
                        except: pass
                        if not has_sig: continue

                    debug_log(f"Registry: Matched {name} structure at {found_root}")
                    return name, found_root, profile['exts']

        # 2. Signature / Hint Match (Fallback)
        for name, profile in DeviceRegistry.PROFILES.items():
            hit = False
            for sig in profile['signatures']:
                if any(sig.lower() in os.path.basename(item).lower() for item in root_items): 
                    debug_log(f"Registry: Signature '{sig}' matched in filenames.")
                    hit = True
                if any(sig.lower() in h.lower() for h in usb_hints): 
                    debug_log(f"Registry: Signature '{sig}' matched in USB hints.")
                    hit = True
                if hit: return name, mount_point, profile['exts']
        
        # 3. Android/Generic Fallback
        search_root = mount_point
        internal = find_path(mount_point, "Internal shared storage")
        if not internal: internal = find_path(mount_point, "Internal Storage")
        if internal: 
            debug_log(f"Registry: Found Android storage layer: {internal}")
            search_root = internal

        dcim = find_path(search_root, "DCIM")
        if dcim:
             cam = find_path(dcim, "Camera")
             if cam: 
                 debug_log("Registry: Identified Android Phone via DCIM/Camera")
                 return "Android/Phone", cam, {'.MP4', '.JPG', '.JPEG', '.DNG', '.HEIC'}
             
        debug_log(f"Registry: No specific profile match for {mount_point}. Falling back to Generic.")
        return "Generic Storage", mount_point, None

class DriveDetector:
    IGNORED_KEYWORDS = ["boot", "recovery", "snap", "loop", "var", "tmp", "sys"]

    @staticmethod
    def is_network_mount(path):
        path_lower = path.lower()
        if "mtp" in path_lower or "gphoto" in path_lower or "usb" in path_lower:
            return False 
        network_sigs = ["smb", "sftp", "ftp", "dav", "afp", "nfs", "ssh"]
        for sig in network_sigs:
            if sig in path_lower:
                return True
        return False

    @staticmethod
    def safe_list_dir(path, timeout=5):
        if platform.system() == "Linux" and ("gvfs" in path or "mtp" in path.lower()):
            try:
                result = subprocess.run(['ls', '-1', path], capture_output=True, text=True, timeout=timeout, env=EnvUtils.get_clean_env())
                if result.returncode == 0: return [os.path.join(path, l.strip()) for l in result.stdout.splitlines() if l.strip()]
            except: return []
            return []
        else:
            try: return [os.path.join(path, f) for f in os.listdir(path)] if os.path.isdir(path) else []
            except: return []
            
    @staticmethod
    def safe_exists(path): return os.path.exists(path)

    @staticmethod
    def get_potential_mounts():
        mounts = []
        user = os.environ.get('USER') or os.environ.get('USERNAME')
        system = platform.system()
        if system == "Linux":
            search_roots = [f"/media/{user}", f"/run/media/{user}"]
            uid = os.getuid(); gvfs = f"/run/user/{uid}/gvfs"
            if os.path.exists(gvfs): search_roots.append(gvfs)
            for root in search_roots:
                if os.path.exists(root):
                    try:
                        with os.scandir(root) as it:
                            for entry in it:
                                if entry.is_dir() and not any(x in entry.name.lower() for x in DriveDetector.IGNORED_KEYWORDS):
                                    if not DriveDetector.is_network_mount(entry.path):
                                        mounts.append(entry.path)
                    except: pass
        elif system == "Darwin":
            if os.path.exists("/Volumes"):
                try:
                    with os.scandir("/Volumes") as it:
                        for entry in it:
                            if entry.is_dir() and not entry.is_symlink(): mounts.append(entry.path)
                except: pass
        elif system == "Windows":
            import string
            drives = ['%s:\\' % d for d in string.ascii_uppercase if os.path.exists('%s:\\' % d)]
            for d in drives:
                if d.upper() != "C:\\": mounts.append(d)
        return mounts
    
    @staticmethod
    def get_usb_hardware_hints():
        hints = set()
        try:
            if platform.system() == "Linux":
                res = subprocess.run(['lsusb'], capture_output=True, text=True, timeout=2, env=EnvUtils.get_clean_env())
                if res.stdout:
                    for line in res.stdout.splitlines():
                        parts = line.split(":", 2)
                        if len(parts) > 2:
                            desc = parts[2].strip()
                            if "root hub" not in desc.lower() and "linux foundation" not in desc.lower(): hints.add(desc)
        except: pass
        return hints

    @staticmethod
    def fingerprint_device(mount_path, usb_hints):
        friendly_name = "External Storage"
        content_path = mount_path
        
        candidates = ["Internal shared storage", "Internal Storage", "sdcard"]
        root_subs = DriveDetector.safe_list_dir(mount_path)
        internal_storage_path = None
        for sub in root_subs:
             base = os.path.basename(sub).lower()
             if any(x.lower() in base.lower() for x in candidates):
                 internal_storage_path = sub
                 break
        search_root = internal_storage_path if internal_storage_path else mount_path

        dcim_node = None
        for child in DriveDetector.safe_list_dir(search_root):
             if os.path.basename(child).lower() == "dcim":
                 dcim_node = child
                 break
        
        if dcim_node:
            camera_node = None
            for item in DriveDetector.safe_list_dir(dcim_node):
                if os.path.basename(item).lower() == "camera":
                    camera_node = item
                    break
            
            if camera_node:
                content_path = camera_node
                friendly_name = "Android Device"
                for hint in usb_hints:
                    h_low = hint.lower()
                    if any(x in h_low for x in ['pixel', 'google', 'galaxy', 'samsung', 'android']):
                        friendly_name = hint; break
            else:
                for item in DriveDetector.safe_list_dir(dcim_node):
                    base = os.path.basename(item).upper()
                    if "GOPRO" in base:
                        content_path = item; friendly_name = "GoPro Camera"; break
                    if "DJI" in base or "100MEDIA" in base:
                        content_path = item; friendly_name = "DJI Drone"; break
                if friendly_name == "External Storage": friendly_name = "Digital Camera"

        elif DriveDetector.safe_exists(os.path.join(mount_path, "PRIVATE", "AVCHD")):
             friendly_name = "Pro Camera (Sony/Panasonic)"
             content_path = os.path.join(mount_path, "PRIVATE", "AVCHD")
             
        if friendly_name in ["External Storage", "Digital Camera"]:
             for hint in usb_hints:
                 if "gopro" in hint.lower() or "hero" in hint.lower():
                     friendly_name = "GoPro Camera"
                     if dcim_node: content_path = dcim_node
                     break
        return friendly_name, content_path

class ScanWorker(QThread):
    finished_signal = pyqtSignal(list)
    def run(self):
        results = []
        try:
            usb_hints = DriveDetector.get_usb_hardware_hints()
            if DEBUG_MODE: debug_log(f"USB Hints Found: {usb_hints}")
            candidates = sorted(list(set(DriveDetector.get_potential_mounts())))
            for mount in candidates:
                if mount == "/" or mount == "/home": continue 
                has_files = False
                try: 
                    if len(DriveDetector.safe_list_dir(mount)) > 0: has_files = True
                except: pass
                
                name, true_path, exts = DeviceRegistry.identify(mount, usb_hints)
                
                results.append({'path': true_path, 'display_name': name, 'root': mount, 'empty': not has_files, 'exts': exts})
            final = []
            seen = set()
            for r in sorted(results, key=lambda x: len(x['path']), reverse=True):
                if r['path'] not in seen: final.append(r); seen.add(r['path'])
            self.finished_signal.emit(final)
        except Exception as e:
            debug_log(f"Scan Error: {e}")
            self.finished_signal.emit([])

class ThumbnailWorker(QThread):
    thumb_ready = pyqtSignal(str, QImage)
    def __init__(self, file_queue): super().__init__(); self.queue = file_queue; self.is_running = True
    def run(self):
        ffmpeg = DependencyManager.get_ffmpeg_path()
        if not ffmpeg: return
        for path in self.queue:
            if not self.is_running: break
            try:
                # Seek 0.5s to avoid black frame at start
                cmd = [ffmpeg, '-y', '-ss', '00:00:00.5', '-i', path, '-vframes', '1', '-vf', 'scale=160:-1', '-f', 'image2pipe', '-']
                startupinfo = None
                if platform.system() == 'Windows': startupinfo = subprocess.STARTUPINFO(); startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, startupinfo=startupinfo, env=EnvUtils.get_clean_env())
                if res.stdout:
                    img = QImage(); img.loadFromData(res.stdout)
                    if not img.isNull(): self.thumb_ready.emit(path, img)
            except: pass
    def stop(self): self.is_running = False

class IngestScanner(QThread):
    finished_signal = pyqtSignal(dict)
    def __init__(self, source_path, video_only=False, allowed_exts=None):
        super().__init__(); self.source = source_path; self.video_only = video_only; self.allowed_exts = allowed_exts
    def run(self):
        grouped = {}
        if self.allowed_exts:
            exts = set(self.allowed_exts)
        else:
            exts = DeviceRegistry.VIDEO_EXTS
            if not self.video_only: 
                exts = DeviceRegistry.get_all_valid_exts()
        for root, dirs, files in os.walk(self.source):
            for f in files:
                if os.path.splitext(f)[1].upper() in exts:
                    full = os.path.join(root, f)
                    try: date = datetime.fromtimestamp(os.path.getmtime(full)).strftime("%Y-%m-%d")
                    except: date = "Unknown Date"
                    if date not in grouped: grouped[date] = []
                    grouped[date].append(full)
        self.finished_signal.emit(grouped)

class AsyncTranscoder(QThread):
    log_signal = pyqtSignal(str); status_signal = pyqtSignal(str); metrics_signal = pyqtSignal(str); progress_signal = pyqtSignal(int); all_finished_signal = pyqtSignal()
    def __init__(self, settings, use_gpu):
        super().__init__(); self.settings = settings; self.use_gpu = use_gpu; self.queue = deque(); self.is_running = True; self.is_idle = True; self.total_expected_jobs = 0; self.completed_jobs = 0; self.producer_finished = False
    def set_total_jobs(self, count): self.total_expected_jobs = count
    def add_job(self, input_path, output_path, filename): self.queue.append({'in': input_path, 'out': output_path, 'name': filename})
    def set_producer_finished(self): self.producer_finished = True
    def run(self):
        while self.is_running:
            if not self.queue:
                if self.producer_finished: self.all_finished_signal.emit(); break
                else: self.is_idle = True; time.sleep(0.5); continue
            self.is_idle = False; job = self.queue.popleft()
            display_total = self.total_expected_jobs if self.total_expected_jobs > 0 else (self.completed_jobs + len(self.queue) + 1)
            base_status = f"Transcoding {self.completed_jobs + 1}/{display_total}: {job['name']}"
            self.status_signal.emit(base_status); self.log_signal.emit(f"🎬 Transcoding Started: {job['name']}")
            cmd = TranscodeEngine.build_command(job['in'], job['out'], self.settings, self.use_gpu); duration = TranscodeEngine.get_duration(job['in'])
            try:
                startupinfo = None; 
                if platform.system() == 'Windows': startupinfo = subprocess.STARTUPINFO(); startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, universal_newlines=True, startupinfo=startupinfo, env=EnvUtils.get_clean_env())
                
                error_lines = []
                while True:
                    if not self.is_running: process.kill(); break
                    line = process.stderr.readline()
                    if not line and process.poll() is not None: break
                    if line:
                        stripped = line.strip()
                        error_lines.append(stripped)
                        if len(error_lines) > 15: error_lines.pop(0)
                        self.log_signal.emit(f"   [FFmpeg] {stripped}")
                        if duration > 0:
                            pct, speed_str = TranscodeEngine.parse_progress(line, duration)
                            if pct > 0: self.progress_signal.emit(pct)
                            if speed_str: self.metrics_signal.emit(f"{base_status} | {speed_str}")
                
                if process.returncode == 0: 
                    self.log_signal.emit(f"✅ Transcode Finished: {job['name']}")
                else: 
                    msg = f"❌ Transcode Failed: {job['name']} (Exit Code: {process.returncode})"
                    self.log_signal.emit(msg)
                    error_log(f"{msg}\nRecent Output:\n" + "\n".join(error_lines))
            except Exception as e: 
                self.log_signal.emit(f"❌ Exception: {e}")
                error_log(f"Transcode Critical Error: {e}")
            self.completed_jobs += 1
    def stop(self): self.is_running = False

class CopyWorker(QThread):
    log_signal = pyqtSignal(str); progress_signal = pyqtSignal(int); status_signal = pyqtSignal(str); speed_signal = pyqtSignal(str); file_ready_signal = pyqtSignal(str, str, str); transcode_count_signal = pyqtSignal(int); finished_signal = pyqtSignal(bool, str)
    # New Signal for Storage Check
    storage_check_signal = pyqtSignal(int, int, bool) # needed, free, is_enough
    
    def __init__(self, source, dest, project_name, sort_by_date, skip_dupes, videos_only, camera_override, verify_copy, file_list=None):
        super().__init__(); self.source = source; self.dest = dest; self.project_name = project_name.strip(); self.sort_by_date = sort_by_date; self.skip_dupes = skip_dupes; self.videos_only = videos_only; self.camera_override = camera_override; self.verify_copy = verify_copy; self.file_list = file_list; self.is_running = True
        self.main_video_exts = {'.MP4', '.MOV', '.MKV', '.INSV', '.360'}
    
    def get_mmt_category(self, filename):
        ext = os.path.splitext(filename.upper())[1]
        if ext in self.main_video_exts: return "videos"
        if ext in ['.JPG', '.JPEG', '.PNG', '.INSP']: return "photos"
        if ext in ['.DNG', '.GPR']: return "raw"
        if ext in ['.WAV', '.MP3']: return "audios"
        return "misc"
    
    def get_media_date(self, file_path):
        try: return datetime.fromtimestamp(os.path.getmtime(file_path)).strftime("%Y-%m-%d")
        except: return "Unsorted"
        
    def calculate_hash(self, file_path):
        chunk_size = 1024 * 1024 * 4 
        try:
            if HAS_XXHASH: hash_algo = xxhash.xxh64(); algo_name = "xxHash64"
            else: hash_algo = hashlib.md5(); algo_name = "MD5"
            with open(file_path, 'rb') as f:
                while chunk := f.read(chunk_size): hash_algo.update(chunk)
            return hash_algo.hexdigest(), algo_name
        except Exception as e: return None, str(e)
    
    def get_free_space(self, path):
        # Handle case where project folder doesn't exist yet by checking parent
        check_path = path
        while not os.path.exists(check_path):
            parent = os.path.dirname(check_path)
            if parent == check_path: break # hit root
            check_path = parent
        try: return shutil.disk_usage(check_path).free
        except: return 0

    def run(self):
        detected_cam = self.camera_override; 
        if detected_cam == "auto": detected_cam = "Generic_Device"
        self.log_signal.emit(f"System: Analyzing source...")
        final_dest = self.dest
        if self.project_name: final_dest = os.path.join(self.dest, self.project_name)
        valid_exts = tuple(DeviceRegistry.get_all_valid_exts())
        found_files = []
        
        if self.file_list:
            found_files = self.file_list
        else:
            count_scanned = 0
            for root, dirs, files in os.walk(self.source):
                if not self.is_running: break
                for file in files:
                    if file.upper().endswith(valid_exts): 
                        found_files.append(os.path.join(root, file))
                        count_scanned += 1
                        if count_scanned % 50 == 0:
                            self.status_signal.emit(f"Analyzing Source... Found {count_scanned} files")

        priority_videos = [f for f in found_files if os.path.splitext(f)[1].upper() in self.main_video_exts]
        secondary_files = [f for f in found_files if os.path.splitext(f)[1].upper() not in self.main_video_exts]
        files_to_process = priority_videos if self.videos_only else priority_videos + secondary_files
        
        transcode_candidates = [f for f in files_to_process if os.path.splitext(f)[1].upper() in ('.MP4', '.MOV', '.MKV', '.AVI')]
        self.transcode_count_signal.emit(len(transcode_candidates))
        
        total_files = len(files_to_process)
        total_bytes = sum(os.path.getsize(f) for f in files_to_process)
        bytes_processed = 0
        
        # --- PRE-FLIGHT STORAGE CHECK ---
        free_bytes = self.get_free_space(final_dest)
        
        # Check if we have enough space (adding 50MB buffer)
        is_enough = free_bytes > (total_bytes + 50*1024*1024)
        self.storage_check_signal.emit(total_bytes, free_bytes, is_enough)
        
        if not is_enough:
             needed_gb = total_bytes / (1024**3)
             free_gb = free_bytes / (1024**3)
             err_msg = f"❌ Insufficient Storage! Needed: {needed_gb:.2f} GB, Available: {free_gb:.2f} GB"
             self.log_signal.emit(err_msg)
             self.finished_signal.emit(False, err_msg)
             return
        # ------------------------------------
        
        if total_files == 0:
            self.finished_signal.emit(False, "No media found.")
            return

        last_time = time.time()
        bytes_since_last_time = 0

        for idx, src_path in enumerate(files_to_process):
            if not self.is_running: break
            filename = os.path.basename(src_path)
            file_size = os.path.getsize(src_path)
            target_dir = final_dest
            if self.sort_by_date: target_dir = os.path.join(target_dir, self.get_media_date(src_path))
            if detected_cam != "Generic_Device": target_dir = os.path.join(target_dir, detected_cam)
            target_dir = os.path.join(target_dir, self.get_mmt_category(filename))
            os.makedirs(target_dir, exist_ok=True)
            dest_path = os.path.join(target_dir, filename)

            if self.skip_dupes and os.path.exists(dest_path):
                if os.path.getsize(dest_path) == file_size:
                    self.log_signal.emit(f"Skipping (Dupe): {filename}")
                    bytes_processed += file_size
                    self.progress_signal.emit(int((bytes_processed / total_bytes) * 100))
                    continue
            
            self.status_signal.emit(f"Copying {idx + 1}/{total_files}: {filename}")
            try:
                # COPY PHASE
                with open(src_path, 'rb') as fsrc:
                    with open(dest_path, 'wb') as fdst:
                        copied_this_file = 0; chunk_size = 1024 * 1024 * 4
                        while True:
                            if not self.is_running: break
                            buf = fsrc.read(chunk_size)
                            if not buf: break
                            fdst.write(buf)
                            len_buf = len(buf); copied_this_file += len_buf; bytes_since_last_time += len_buf
                            current_time = time.time()
                            if current_time - last_time >= 0.5:
                                speed_mbps = (bytes_since_last_time / (current_time - last_time)) / (1024 * 1024)
                                self.speed_signal.emit(f"{speed_mbps:.1f} MB/s")
                                last_time = current_time; bytes_since_last_time = 0
                            if total_bytes > 0: self.progress_signal.emit(int(((bytes_processed + copied_this_file) / total_bytes) * 100))
                shutil.copystat(src_path, dest_path)
                
                # VERIFICATION PHASE
                if self.verify_copy and self.is_running:
                    self.status_signal.emit(f"Verifying {idx + 1}/{total_files}: {filename}")
                    src_hash, algo = self.calculate_hash(src_path)
                    dest_hash, _ = self.calculate_hash(dest_path)
                    
                    if src_hash and dest_hash and src_hash == dest_hash:
                        self.log_signal.emit(f"✅ Verified ({algo}): {filename}")
                    else:
                        self.log_signal.emit(f"❌ VERIFICATION FAILED: {filename}")
                else:
                    self.log_signal.emit(f"✔️ Copied: {filename}")

                if filename.upper().endswith(('.MP4', '.MOV', '.MKV', '.AVI')):
                    self.file_ready_signal.emit(src_path, dest_path, filename)
            except Exception as e: self.log_signal.emit(f"❌ Error {filename}: {e}")
            bytes_processed += file_size

        if not self.is_running: self.finished_signal.emit(False, "🚫 Operation Aborted")
        else: self.finished_signal.emit(True, "✅ Ingest Complete!")
    def stop(self): self.is_running = False

class BatchTranscodeWorker(QThread):
    progress_signal = pyqtSignal(int); log_signal = pyqtSignal(str); status_signal = pyqtSignal(str); finished_signal = pyqtSignal(bool)
    def __init__(self, file_list, dest_folder, settings, mode="convert", use_gpu=False):
        super().__init__(); self.files = file_list; self.dest = dest_folder; self.settings = settings; self.mode = mode; self.use_gpu = use_gpu; self.is_running = True
    def run(self):
        total = len(self.files)
        for i, input_path in enumerate(self.files):
            if not self.is_running: break
            filename = os.path.basename(input_path); name_only = os.path.splitext(filename)[0]; target_dir = ""
            if self.mode == "convert":
                if self.dest and os.path.isdir(self.dest): target_dir = self.dest
                else: target_dir = os.path.join(os.path.dirname(input_path), "Converted")
                out_name = f"{name_only}_CNV.mov"
            else: 
                if self.dest and os.path.isdir(self.dest): target_dir = self.dest
                else: target_dir = os.path.join(os.path.dirname(input_path), "Final_Render")
                ext = ".mp4" if "libx26" in self.settings['v_codec'] else ".mov"; out_name = f"{name_only}_DELIVERY{ext}"
            os.makedirs(target_dir, exist_ok=True); output_path = os.path.join(target_dir, out_name)
            cmd = TranscodeEngine.build_command(input_path, output_path, self.settings, self.use_gpu); duration = TranscodeEngine.get_duration(input_path)
            self.log_signal.emit(f"Starting: {filename}")
            try:
                startupinfo = None; 
                if platform.system() == 'Windows': startupinfo = subprocess.STARTUPINFO(); startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, universal_newlines=True, startupinfo=startupinfo, env=EnvUtils.get_clean_env())
                
                error_lines = []
                while True:
                    if not self.is_running: process.kill(); break
                    line = process.stderr.readline()
                    if not line and process.poll() is not None: break
                    if line:
                        stripped = line.strip()
                        error_lines.append(stripped)
                        if len(error_lines) > 15: error_lines.pop(0)
                        if duration > 0:
                            pct, speed = TranscodeEngine.parse_progress(line, duration)
                            if pct > 0: self.pbar.setValue(pct) if hasattr(self, 'pbar') else self.progress_signal.emit(pct)
                            if speed: self.status_signal.emit(f"Processing {i+1}/{total}: {speed}")
                
                if process.returncode == 0: 
                    self.log_signal.emit(f"✅ Finished: {out_name}")
                else: 
                    msg = f"❌ Error on {filename} (Exit Code: {process.returncode})"
                    self.log_signal.emit(msg)
                    error_log(f"{msg}\nRecent Output:\n" + "\n".join(error_lines))
            except Exception as e: 
                self.log_signal.emit(f"❌ Exception: {e}")
                error_log(f"Batch Transcode Error: {e}")
        self.finished_signal.emit(True)
    def stop(self): self.is_running = False

class SystemMonitor(QThread):
    cpu_signal = pyqtSignal(int)
    def run(self):
        while True:
            if PSUTIL_AVAILABLE:
                try: self.cpu_signal.emit(int(psutil.cpu_percent(interval=1)))
                except: self.cpu_signal.emit(0)
            else: self.cpu_signal.emit(0); time.sleep(1)

# =============================================================================
# GUI COMPONENTS
# =============================================================================

class FileDropLineEdit(QLineEdit):
    def __init__(self, parent=None): super().__init__(parent); self.setAcceptDrops(True)
    def dragEnterEvent(self, e: QDragEnterEvent): 
        if e.mimeData().hasUrls(): e.accept()
        else: super().dragEnterEvent(e)
    def dropEvent(self, e: QDropEvent):
        if e.mimeData().hasUrls(): files = [u.toLocalFile() for u in e.mimeData().urls()]; self.setText(files[0]); e.accept()
        else: super().dropEvent(e)

class TranscodeSettingsWidget(QGroupBox):
    def __init__(self, title="Transcode Settings", mode="general"):
        super().__init__(title); self.layout = QVBoxLayout(); self.setLayout(self.layout); self.mode = mode
        self.chk_gpu = QCheckBox("Use Hardware Acceleration (if available)"); self.chk_gpu.setStyleSheet("font-weight: bold; color: #3498DB;"); self.layout.addWidget(self.chk_gpu)
        top_row = QHBoxLayout(); top_row.addWidget(QLabel("Preset:")); self.preset_combo = QComboBox(); self.init_presets() 
        self.preset_combo.currentIndexChanged.connect(self.apply_preset); top_row.addWidget(self.preset_combo, 1)
        
        # Preset Management Buttons
        self.btn_save_preset = QToolButton(); self.btn_save_preset.setText("💾"); self.btn_save_preset.setToolTip("Save Current as Preset"); self.btn_save_preset.clicked.connect(self.save_custom_preset)
        self.btn_import_preset = QToolButton(); self.btn_import_preset.setText("📥"); self.btn_import_preset.setToolTip("Import Preset File"); self.btn_import_preset.clicked.connect(self.import_preset_file)
        self.btn_export_preset = QToolButton(); self.btn_export_preset.setText("📤"); self.btn_export_preset.setToolTip("Export Selected Preset"); self.btn_export_preset.clicked.connect(self.export_preset_file)
        self.btn_del_preset = QToolButton(); self.btn_del_preset.setText("🗑️"); self.btn_del_preset.setToolTip("Delete Selected Preset"); self.btn_del_preset.clicked.connect(self.delete_current_preset)
        top_row.addWidget(self.btn_save_preset); top_row.addWidget(self.btn_import_preset); top_row.addWidget(self.btn_export_preset); top_row.addWidget(self.btn_del_preset)
        
        self.layout.addLayout(top_row)
        
        lut_lay = QHBoxLayout(); self.lut_path = QLineEdit(); self.lut_path.setPlaceholderText("Select 3D LUT (.cube) - Optional")
        self.btn_lut = QPushButton("Browse LUT"); self.btn_lut.clicked.connect(self.browse_lut)
        self.btn_clr_lut = QPushButton("X"); self.btn_clr_lut.setFixedWidth(30); self.btn_clr_lut.clicked.connect(self.lut_path.clear)
        lut_lay.addWidget(QLabel("Look:")); lut_lay.addWidget(self.lut_path); lut_lay.addWidget(self.btn_lut); lut_lay.addWidget(self.btn_clr_lut)
        self.layout.addLayout(lut_lay)

        self.advanced_frame = QFrame(); adv_layout = QFormLayout(); self.advanced_frame.setLayout(adv_layout)
        self.codec_combo = QComboBox(); self.init_codecs(); self.codec_combo.currentIndexChanged.connect(self.update_profiles)
        self.profile_combo = QComboBox(); self.audio_combo = QComboBox(); self.audio_combo.addItems(["PCM (Uncompressed)", "AAC (Compressed)"])
        self.chk_audio_fix = QCheckBox("Fix Audio Drift (48kHz)")
        adv_layout.addRow("Video Codec:", self.codec_combo); adv_layout.addRow("Profile:", self.profile_combo)
        adv_layout.addRow("Audio Codec:", self.audio_combo); adv_layout.addRow("Processing:", self.chk_audio_fix)
        self.layout.addWidget(self.advanced_frame); self.update_profiles(); self.apply_preset() 
    def init_presets(self):
        self.preset_combo.clear()
        if self.mode == "general":
            p = "Linux " if platform.system() == "Linux" else ""
            self.preset_combo.addItems([f"{p}Edit-Ready (DNxHR HQ)", f"{p}Proxy (DNxHR LB)", "ProRes 422 HQ", "ProRes Proxy", "H.264 (Standard)", "H.265 (High Compress)"])
        else:
            self.preset_combo.addItems(["YouTube 4K (H.265 / HEVC)", "YouTube 1080p (H.264 / AVC)", "Social / Mobile (H.264)", "Master Archive (H.265 10-bit)"])
        
        # Load Custom Presets
        self.custom_presets = PresetManager.list_presets()
        if self.custom_presets:
            self.preset_combo.insertSeparator(self.preset_combo.count())
            for name in sorted(self.custom_presets.keys()):
                self.preset_combo.addItem(f"⭐ {name}", self.custom_presets[name])
        
        self.preset_combo.insertSeparator(self.preset_combo.count())
        self.preset_combo.addItem("Custom")

    def init_codecs(self):
        self.codec_combo.clear()
        if self.mode == "general": self.codec_combo.addItems(["DNxHR (Avid)", "ProRes (Apple)", "H.264", "H.265 (HEVC)"])
        else: self.codec_combo.addItems(["H.264", "H.265 (HEVC)"])

    def update_profiles(self):
        self.profile_combo.clear(); codec = self.codec_combo.currentText()
        if "DNxHR" in codec: 
            self.profile_combo.addItem("LB (Proxy)", "dnxhr_lb"); self.profile_combo.addItem("SQ (Standard)", "dnxhr_sq"); self.profile_combo.addItem("HQ (High Quality)", "dnxhr_hq")
        elif "ProRes" in codec: 
            self.profile_combo.addItem("Proxy", "0"); self.profile_combo.addItem("LT", "1"); self.profile_combo.addItem("422", "2"); self.profile_combo.addItem("HQ", "3")
        elif "H.264" in codec: 
            self.profile_combo.addItem("High", "high"); self.profile_combo.addItem("Main", "main")
        elif "H.265" in codec: 
            self.profile_combo.addItem("Main", "main"); self.profile_combo.addItem("Main 10", "main10")

    def save_custom_preset(self):
        name, ok = QInputDialog.getText(self, "Save Preset", "Enter a name for this preset:")
        if ok and name.strip():
            if PresetManager.save_preset(name.strip(), self.get_settings()):
                self.init_presets()
                idx = self.preset_combo.findText(f"⭐ {name.strip()}")
                if idx >= 0: self.preset_combo.setCurrentIndex(idx)

    def import_preset_file(self):
        f, _ = QFileDialog.getOpenFileName(self, "Import Preset", "", "JSON Files (*.json)")
        if f:
            try:
                with open(f, 'r') as p: data = json.load(p)
                name = os.path.splitext(os.path.basename(f))[0]
                if PresetManager.save_preset(name, data):
                    self.init_presets(); QMessageBox.information(self, "Success", f"Imported '{name}'")
            except Exception as e: QMessageBox.critical(self, "Error", f"Failed to import: {e}")

    def export_preset_file(self):
        text = self.preset_combo.currentText()
        data = self.preset_combo.currentData()
        if not data or not isinstance(data, dict):
            data = self.get_settings()
        
        clean_name = text.replace("⭐ ", "").replace("Linux ", "").replace(" ", "_")
        f, _ = QFileDialog.getSaveFileName(self, "Export Preset", f"{clean_name}.json", "JSON Files (*.json)")
        if f:
            try:
                with open(f, 'w') as p: json.dump(data, p, indent=4)
                QMessageBox.information(self, "Success", f"Exported to {f}")
            except Exception as e: QMessageBox.critical(self, "Error", f"Failed to export: {e}")

    def delete_current_preset(self):
        text = self.preset_combo.currentText()
        if not text.startswith("⭐ "): return
        name = text.replace("⭐ ", "")
        if PresetManager.delete_preset(name): self.init_presets()

    def apply_preset(self):
        text = self.preset_combo.currentText(); is_custom_entry = (text == "Custom")
        self.advanced_frame.setEnabled(is_custom_entry or text.startswith("⭐ "))
        
        data = self.preset_combo.currentData()
        if data and isinstance(data, dict):
            v_map = {"dnxhd": 0, "prores_ks": 1, "libx264": 2, "libx265": 3}
            if self.mode != "general": v_map = {"libx264": 0, "libx265": 1}
            self.codec_combo.setCurrentIndex(v_map.get(data.get('v_codec'), 0))
            self.update_profiles()
            p_idx = self.profile_combo.findData(data.get('v_profile'))
            if p_idx >= 0: self.profile_combo.setCurrentIndex(p_idx)
            self.audio_combo.setCurrentIndex(1 if data.get('a_codec') == 'aac' else 0)
            self.chk_audio_fix.setChecked(data.get('audio_fix', False))
            self.lut_path.setText(data.get('lut_path', ""))
            return

        if is_custom_entry: return
        idx = self.preset_combo.currentIndex()
        if self.mode == "general":
            if idx == 0: self.set_combo(0, "dnxhr_hq", 0)
            elif idx == 1: self.set_combo(0, "dnxhr_lb", 0)
            elif idx == 2: self.set_combo(1, "3", 0)
            elif idx == 3: self.set_combo(1, "0", 0)
            elif idx == 4: self.set_combo(2, None, 1)
            elif idx == 5: self.set_combo(3, None, 1)
        else:
            if idx == 0: self.set_combo(1, "main10", 1)
            elif idx == 1: self.set_combo(0, "high", 1)
            elif idx == 2: self.set_combo(0, "main", 1)
            elif idx == 3: self.set_combo(1, "main10", 1)

    def set_combo(self, codec_idx, profile_data, audio_idx):
        self.codec_combo.blockSignals(True)
        self.codec_combo.setCurrentIndex(codec_idx)
        self.codec_combo.blockSignals(False)
        self.update_profiles()
        if profile_data: self.profile_combo.setCurrentIndex(self.profile_combo.findData(profile_data))
        else: self.profile_combo.setCurrentIndex(0)
        self.audio_combo.setCurrentIndex(audio_idx)
    def browse_lut(self):
        f, _ = QFileDialog.getOpenFileName(self, "Select 3D LUT", "", "Cube Files (*.cube)")
        if f: self.lut_path.setText(f)
    def get_settings(self):
        v_codec_map = { "DNxHR (Avid)": "dnxhd", "ProRes (Apple)": "prores_ks", "H.264": "libx264", "H.265 (HEVC)": "libx265" }
        a_codec_map = { "PCM (Uncompressed)": "pcm_s16le", "AAC (Compressed)": "aac" }
        settings = { 
            "v_codec": v_codec_map.get(self.codec_combo.currentText(), "dnxhd"), 
            "v_profile": self.profile_combo.currentData(), 
            "a_codec": a_codec_map.get(self.audio_combo.currentText(), "pcm_s16le"),
            "audio_fix": self.chk_audio_fix.isChecked()
        }
        if self.lut_path.text().strip(): settings["lut_path"] = self.lut_path.text().strip()
        return settings
    def is_gpu_enabled(self): return self.chk_gpu.isChecked()
    def set_gpu_checked(self, checked): self.chk_gpu.blockSignals(True); self.chk_gpu.setChecked(checked); self.chk_gpu.blockSignals(False)

class JobReportDialog(QDialog):
    def __init__(self, title, report_text, parent=None):
        super().__init__(parent); self.setWindowTitle(title); self.setMinimumWidth(500); self.resize(600, 400); layout = QVBoxLayout()
        # Theme-aware styling for report
        self.text_edit = QTextEdit(); self.text_edit.setReadOnly(True)
        # Using a div with specific class or inline style that adapts is tricky in simple HTML.
        # Instead, we set the widget stylesheet to handle background/text color, and use minimal HTML.
        # We assume the parent app has already set a global stylesheet (QTextEdit will inherit).
        # We add some padding/margins via HTML container.
        self.text_edit.setHtml(f"<div style='font-family: Consolas, monospace; font-size: 13px; padding: 10px;'>{report_text}</div>")
        layout.addWidget(self.text_edit); ok_btn = QPushButton("OK"); ok_btn.clicked.connect(self.accept); layout.addWidget(ok_btn); self.setLayout(layout)

class FFmpegConfigDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent); self.setWindowTitle("FFmpeg Configuration"); self.resize(600, 500)
        self.settings = QSettings("CineBridgePro", "Config")
        layout = QVBoxLayout(); layout.setSpacing(15); self.setLayout(layout)
        
        path_group = QGroupBox("FFmpeg Binary Location"); path_lay = QVBoxLayout()
        row = QHBoxLayout()
        self.path_input = QLineEdit(); self.path_input.setReadOnly(True)
        self.btn_browse = QPushButton("Browse..."); self.btn_browse.clicked.connect(self.browse_ffmpeg)
        self.btn_reset = QPushButton("Reset Default"); self.btn_reset.clicked.connect(self.reset_ffmpeg)
        row.addWidget(self.path_input); row.addWidget(self.btn_browse); row.addWidget(self.btn_reset)
        path_lay.addLayout(row)
        path_lay.addWidget(QLabel("<small>Select a custom FFmpeg binary (e.g. custom build with NVENC enabled).</small>"))
        path_group.setLayout(path_lay); layout.addWidget(path_group)
        
        cap_group = QGroupBox("Detected Capabilities"); cap_lay = QVBoxLayout()
        self.report_area = QTextEdit(); self.report_area.setReadOnly(True)
        self.report_area.setStyleSheet("font-family: Consolas; font-size: 12px;")
        cap_lay.addWidget(self.report_area); cap_group.setLayout(cap_lay)
        layout.addWidget(cap_group)
        
        btn_row = QHBoxLayout(); btn_row.addStretch()
        close_btn = QPushButton("Close"); close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn); layout.addLayout(btn_row)
        self.refresh_status()

    def browse_ffmpeg(self):
        f, _ = QFileDialog.getOpenFileName(self, "Select FFmpeg Executable")
        if f and os.path.exists(f):
            self.settings.setValue("ffmpeg_custom_path", f); self.refresh_status()

    def reset_ffmpeg(self):
        self.settings.remove("ffmpeg_custom_path"); self.refresh_status()

    def refresh_status(self):
        path = DependencyManager.get_ffmpeg_path()
        self.path_input.setText(path if path else "Not Found")
        if not path or not os.path.exists(path):
            self.report_area.setHtml("<h3 style='color:red'>FFmpeg binary not found!</h3>"); return

        report = f"<b>Active Binary:</b> {path}<br>"
        if "ffmpeg_custom_path" in self.settings.allKeys(): report += "<b style='color: #3498DB'>[CUSTOM OVERRIDE ACTIVE]</b><br>"
        else: report += "<span style='color: green'>[Using System/Default]</span><br>"
        report += "<hr>"
        
        try:
            res = subprocess.run([path, '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=EnvUtils.get_clean_env())
            ver = res.stdout.splitlines()[0] if res.stdout else "Unknown"; report += f"<b>Version:</b> {ver}<br>"
        except: report += "<b>Version:</b> Error checking version<br>"

        report += "<br><b>Hardware Acceleration:</b><br>"
        try:
            res = subprocess.run([path, '-hwaccels'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=EnvUtils.get_clean_env())
            accels = [x.strip() for x in res.stdout.splitlines()[1:] if x.strip()] if res.stdout else []
            if accels: report += f"APIs: {', '.join(accels)}<br>"
        except: pass
        
        target_encoders = ["h264_nvenc", "hevc_nvenc", "h264_qsv", "h264_vaapi", "h264_videotoolbox"]
        found_encs = []
        try:
            res = subprocess.run([path, '-encoders'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=EnvUtils.get_clean_env())
            for enc in target_encoders:
                if enc in res.stdout: found_encs.append(enc)
        except: pass
        
        if found_encs: report += f"Encoders: <span style='color:green'>{' '.join(found_encs)}</span>"
        else: report += "Encoders: <span style='color:orange'>No Hardware Encoders Found</span>"
        
        report += "<hr><b>CineBridge Active Strategy:</b><br>"
        active_prof = DependencyManager.detect_hw_accel()
        if active_prof: 
            msg = f"CineBridge is currently configured to use: <b style='color:#E67E22; font-size:14px'>{active_prof.upper()}</b>"
        else: 
            msg = "CineBridge will use: <b>Software Encoding (CPU)</b>"
        report += f"<p>{msg}</p>"
        
        self.report_area.setHtml(report)

class MediaInfoDialog(QDialog):
    def __init__(self, media_info, parent=None):
        super().__init__(parent); self.setWindowTitle(f"Media Info: {media_info.get('filename', 'Unknown')}"); self.resize(500, 600); layout = QVBoxLayout(); self.setLayout(layout)
        if "error" in media_info: layout.addWidget(QLabel(f"Error: {media_info['error']}")); return
        
        layout.addWidget(QLabel("<b>Container Format</b>"))
        gen_table = QTableWidget(3, 2); gen_table.horizontalHeader().setVisible(False); gen_table.verticalHeader().setVisible(False); gen_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        gen_table.setItem(0, 0, QTableWidgetItem("Container")); gen_table.setItem(0, 1, QTableWidgetItem(media_info['container']))
        gen_table.setItem(1, 0, QTableWidgetItem("Duration")); gen_table.setItem(1, 1, QTableWidgetItem(f"{media_info['duration']:.2f} sec"))
        gen_table.setItem(2, 0, QTableWidgetItem("Size")); gen_table.setItem(2, 1, QTableWidgetItem(f"{media_info['size_mb']:.2f} MB"))
        layout.addWidget(gen_table)

        if media_info['video_streams']:
            layout.addWidget(QLabel("<b>Video Streams</b>"))
            for v in media_info['video_streams']:
                v_table = QTableWidget(5, 2); v_table.horizontalHeader().setVisible(False); v_table.verticalHeader().setVisible(False); v_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
                v_table.setItem(0, 0, QTableWidgetItem("Codec")); v_table.setItem(0, 1, QTableWidgetItem(f"{v['codec']} ({v['profile']})"))
                v_table.setItem(1, 0, QTableWidgetItem("Resolution")); v_table.setItem(1, 1, QTableWidgetItem(v['resolution']))
                v_table.setItem(2, 0, QTableWidgetItem("Frame Rate")); v_table.setItem(2, 1, QTableWidgetItem(str(v['fps'])))
                v_table.setItem(3, 0, QTableWidgetItem("Pixel Format")); v_table.setItem(3, 1, QTableWidgetItem(v['pix_fmt']))
                v_table.setItem(4, 0, QTableWidgetItem("Bitrate")); v_table.setItem(4, 1, QTableWidgetItem(f"{v['bitrate']} kbps"))
                layout.addWidget(v_table)
        
        if media_info['audio_streams']:
             layout.addWidget(QLabel("<b>Audio Streams</b>"))
             for a in media_info['audio_streams']:
                a_table = QTableWidget(4, 2); a_table.horizontalHeader().setVisible(False); a_table.verticalHeader().setVisible(False); a_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
                a_table.setItem(0, 0, QTableWidgetItem("Codec")); a_table.setItem(0, 1, QTableWidgetItem(a['codec']))
                a_table.setItem(1, 0, QTableWidgetItem("Channels")); a_table.setItem(1, 1, QTableWidgetItem(str(a['channels'])))
                a_table.setItem(2, 0, QTableWidgetItem("Sample Rate")); a_table.setItem(2, 1, QTableWidgetItem(str(a['sample_rate'])))
                a_table.setItem(3, 0, QTableWidgetItem("Language")); a_table.setItem(3, 1, QTableWidgetItem(a['language']))
                layout.addWidget(a_table)
        
        layout.addStretch()
        close_btn = QPushButton("Close"); close_btn.clicked.connect(self.accept); layout.addWidget(close_btn)

class SettingsDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent); self.parent_app = parent; self.setWindowTitle("CineBridge Settings"); self.setMinimumWidth(500); layout = QVBoxLayout()
        theme_group = QGroupBox("Appearance"); theme_lay = QVBoxLayout(); self.rb_sys = QRadioButton("System Default"); self.rb_dark = QRadioButton("Dark Mode"); self.rb_light = QRadioButton("Light Mode")
        mode = parent.settings.value("theme_mode", "system")
        if mode == "dark": self.rb_dark.setChecked(True)
        elif mode == "light": self.rb_light.setChecked(True)
        else: self.rb_sys.setChecked(True)
        bg = QButtonGroup(self); bg.addButton(self.rb_sys); bg.addButton(self.rb_dark); bg.addButton(self.rb_light)
        self.rb_sys.toggled.connect(lambda: parent.set_theme("system")); self.rb_dark.toggled.connect(lambda: parent.set_theme("dark")); self.rb_light.toggled.connect(lambda: parent.set_theme("light"))
        theme_lay.addWidget(self.rb_sys); theme_lay.addWidget(self.rb_dark); theme_lay.addWidget(self.rb_light); theme_group.setLayout(theme_lay); layout.addWidget(theme_group)
        view_group = QGroupBox("View Options"); view_lay = QVBoxLayout(); self.chk_copy = QCheckBox("Show Copy Log"); self.chk_trans = QCheckBox("Show Transcode Log")
        self.chk_copy.setChecked(parent.tab_ingest.copy_log.isVisible()); self.chk_trans.setChecked(parent.tab_ingest.transcode_log.isVisible())
        self.chk_copy.toggled.connect(self.apply_view_options); self.chk_trans.toggled.connect(self.apply_view_options)
        view_lay.addWidget(self.chk_copy); view_lay.addWidget(self.chk_trans); view_group.setLayout(view_lay); layout.addWidget(view_group)
        sys_group = QGroupBox("System"); sys_lay = QVBoxLayout()
        self.btn_ffmpeg = QPushButton("FFmpeg Settings"); self.btn_ffmpeg.clicked.connect(self.show_ffmpeg_info); sys_lay.addWidget(self.btn_ffmpeg)
        self.btn_log = QPushButton("View Debug Log"); self.btn_log.clicked.connect(self.view_log); sys_lay.addWidget(self.btn_log)
        self.chk_debug = QCheckBox("Enable Debug Mode"); self.chk_debug.setChecked(DEBUG_MODE); self.chk_debug.toggled.connect(parent.toggle_debug); sys_lay.addWidget(self.chk_debug)
        self.btn_reset = QPushButton("Reset to Default Settings"); self.btn_reset.setStyleSheet("color: red;"); self.btn_reset.clicked.connect(parent.reset_to_defaults); sys_lay.addWidget(self.btn_reset)
        sys_group.setLayout(sys_lay); layout.addWidget(sys_group)
        self.btn_about = QPushButton("About CineBridge Pro"); self.btn_about.clicked.connect(parent.show_about); layout.addWidget(self.btn_about)
        layout.addStretch(); close_btn = QPushButton("Close"); close_btn.clicked.connect(self.accept); layout.addWidget(close_btn); self.setLayout(layout)
    def apply_view_options(self): 
        self.parent_app.tab_ingest.toggle_logs(self.chk_copy.isChecked(), self.chk_trans.isChecked())
        self.parent_app.settings.setValue("show_copy_log", self.chk_copy.isChecked())
        self.parent_app.settings.setValue("show_trans_log", self.chk_trans.isChecked())
    def show_ffmpeg_info(self): dlg = FFmpegConfigDialog(self); dlg.exec()
    def view_log(self): EnvUtils.open_file(AppLogger._log_path)

class TranscodeConfigDialog(QDialog):
    def __init__(self, settings_widget, parent=None):
        super().__init__(parent); self.setWindowTitle("Transcode Configuration"); self.resize(500, 400); layout = QVBoxLayout(); self.setLayout(layout)
        self.settings_widget = settings_widget
        # Detach from previous parent if any
        if self.settings_widget.parent():
            self.settings_widget.parent().layout().removeWidget(self.settings_widget)
        layout.addWidget(self.settings_widget)
        btn = QPushButton("Done"); btn.clicked.connect(self.accept); layout.addWidget(btn)
    
    def accept(self):
        # Explicitly remove widget from dialog before closing to keep it alive
        self.layout().removeWidget(self.settings_widget)
        self.settings_widget.setParent(None)
        super().accept()

    def reject(self):
        self.layout().removeWidget(self.settings_widget)
        self.settings_widget.setParent(None)
        super().reject()

class IngestTab(QWidget):
    def __init__(self, parent_app):
        super().__init__(); self.app = parent_app; self.layout = QVBoxLayout(); self.layout.setSpacing(10); self.layout.setContentsMargins(20, 20, 20, 20); self.setLayout(self.layout)
        self.copy_worker = None; self.transcode_worker = None; self.scan_worker = None; self.found_devices = []; self.current_detected_path = None
        self.ingest_mode = "scan"; self.last_scan_results = None
        self.setup_ui(); self.load_tab_settings()
        self.scan_watchdog = QTimer(); self.scan_watchdog.setSingleShot(True); self.scan_watchdog.timeout.connect(self.on_scan_timeout); QTimer.singleShot(500, self.run_auto_scan)
    def setup_ui(self):
        # 1. Source Group
        source_group = QGroupBox("1. Source Media"); source_inner = QVBoxLayout(); self.source_tabs = QTabWidget(); self.tab_auto = QWidget(); auto_lay = QVBoxLayout()
        self.scan_btn = QPushButton(" REFRESH DEVICES "); self.scan_btn.setMinimumHeight(50); self.scan_btn.clicked.connect(self.run_auto_scan)
        self.auto_info_label = QLabel("Scanning..."); self.auto_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.result_card = QFrame(); self.result_card.setVisible(False); self.result_card.setObjectName("ResultCard"); res_lay = QVBoxLayout()
        self.result_label = QLabel(); self.result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.select_device_box = QComboBox(); self.select_device_box.setVisible(False); self.select_device_box.currentIndexChanged.connect(self.on_device_selection_change)
        res_lay.addWidget(self.result_label); res_lay.addWidget(self.select_device_box); self.result_card.setLayout(res_lay)
        auto_lay.addWidget(self.scan_btn); auto_lay.addWidget(self.auto_info_label); auto_lay.addWidget(self.result_card); auto_lay.addStretch()
        self.tab_auto.setLayout(auto_lay); self.tab_manual = QWidget(); man_lay = QVBoxLayout()
        self.source_input = QLineEdit(); self.browse_src = QPushButton("Browse"); self.browse_src.clicked.connect(self.browse_source)
        man_lay.addWidget(QLabel("Path:")); man_lay.addWidget(self.source_input); man_lay.addWidget(self.browse_src); man_lay.addStretch()
        self.tab_manual.setLayout(man_lay); self.source_tabs.addTab(self.tab_auto, "Auto"); self.source_tabs.addTab(self.tab_manual, "Manual")
        source_inner.addWidget(self.source_tabs); source_group.setLayout(source_inner)

        # 2. Dest Group
        dest_group = QGroupBox("2. Destination"); dest_inner = QVBoxLayout()
        self.project_name_input = QLineEdit(); self.project_name_input.setPlaceholderText("Project Name")
        self.dest_input = QLineEdit(); self.browse_dest_btn = QPushButton("Browse"); self.browse_dest_btn.clicked.connect(self.browse_dest)
        dest_inner.addWidget(QLabel("Project Name:")); dest_inner.addWidget(self.project_name_input); dest_inner.addWidget(QLabel("Location:")); dest_inner.addWidget(self.dest_input); dest_inner.addWidget(self.browse_dest_btn); dest_inner.addStretch()
        dest_group.setLayout(dest_inner)

        # 3. Settings Group
        settings_group = QGroupBox("3. Processing Settings"); settings_layout = QVBoxLayout()
        logic_row = QHBoxLayout(); logic_row.addWidget(QLabel("Logic:")); 
        self.device_combo = QComboBox(); self.device_combo.addItems(["auto", "GoPro", "DJI", "Insta360", "Generic Storage"]); logic_row.addWidget(self.device_combo)
        settings_layout.addLayout(logic_row)

        rules_grid = QGridLayout()
        self.check_date = QCheckBox("Sort Date"); rules_grid.addWidget(self.check_date, 0, 0)
        self.check_dupe = QCheckBox("Skip Dupes"); rules_grid.addWidget(self.check_dupe, 0, 1)
        self.check_videos_only = QCheckBox("Video Only"); self.check_videos_only.toggled.connect(self.refresh_tree_view); rules_grid.addWidget(self.check_videos_only, 0, 2)
        self.check_verify = QCheckBox("Verify Copy"); self.check_verify.setStyleSheet("color: #27AE60; font-weight: bold;"); rules_grid.addWidget(self.check_verify, 1, 0)
        self.check_verify.setToolTip("Performs hash verification (xxHash/MD5) after copy.")
        self.check_transcode = QCheckBox("Enable Transcode"); self.check_transcode.setStyleSheet("color: #E67E22; font-weight: bold;"); self.check_transcode.toggled.connect(self.toggle_transcode_ui)
        # Fix: Align left to prevent background stretching
        rules_grid.addWidget(self.check_transcode, 1, 1, 1, 2, Qt.AlignmentFlag.AlignLeft)
        settings_layout.addLayout(rules_grid)
        
        self.btn_config_trans = QPushButton("Configure Transcode..."); self.btn_config_trans.setVisible(False); self.btn_config_trans.clicked.connect(self.open_transcode_config); settings_layout.addWidget(self.btn_config_trans)
        self.transcode_widget = TranscodeSettingsWidget(mode="general")
        settings_group.setLayout(settings_layout)
        
        # 4. Review Group
        self.review_group = QGroupBox("4. Select Media"); review_lay = QVBoxLayout()
        self.tree = QTreeWidget(); self.tree.setHeaderLabel("Media Review")
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.tree.itemChanged.connect(self.update_transfer_button_text)
        # Add Placeholder
        placeholder = QTreeWidgetItem(self.tree); placeholder.setText(0, "Scan source to review media selection."); placeholder.setFlags(placeholder.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
        review_lay.addWidget(self.tree); self.review_group.setLayout(review_lay)
        self.review_group.setVisible(True) # Persistent

        # GRID LAYOUT
        grid = QGridLayout()
        grid.addWidget(source_group, 0, 0)
        grid.addWidget(dest_group, 0, 1)
        grid.addWidget(settings_group, 1, 0)
        grid.addWidget(self.review_group, 1, 1)
        grid.setRowStretch(1, 1); grid.setColumnStretch(0, 1); grid.setColumnStretch(1, 1)
        self.layout.addLayout(grid)

        dash_frame = QFrame(); dash_frame.setObjectName("DashFrame"); dash_layout = QVBoxLayout(); dash_frame.setLayout(dash_layout)
        top_row = QHBoxLayout(); self.status_label = QLabel("READY TO INGEST"); self.status_label.setObjectName("StatusLabel"); self.speed_label = QLabel(""); self.speed_label.setObjectName("SpeedLabel")
        top_row.addWidget(self.status_label, 1); top_row.addWidget(self.speed_label); dash_layout.addLayout(top_row)
        self.storage_bar = QProgressBar(); self.storage_bar.setFormat("Destination Storage: %v%"); self.storage_bar.setStyleSheet("QProgressBar::chunk { background-color: #3498DB; }"); self.storage_bar.setVisible(False); dash_layout.addWidget(self.storage_bar)
        self.progress_bar = QProgressBar(); self.progress_bar.setTextVisible(True); dash_layout.addWidget(self.progress_bar)
        self.transcode_status_label = QLabel(""); self.transcode_status_label.setStyleSheet("color: #E67E22; font-weight: bold;"); self.transcode_status_label.setVisible(False); dash_layout.addWidget(self.transcode_status_label)
        self.load_label = QLabel("🔥 CPU Load: 0%"); self.load_label.setAlignment(Qt.AlignmentFlag.AlignCenter); self.load_label.setStyleSheet("color: #E74C3C; font-weight: bold; font-size: 11px;"); self.load_label.setVisible(False); dash_layout.addWidget(self.load_label); self.layout.addWidget(dash_frame)
        btn_layout = QHBoxLayout()
        self.import_btn = QPushButton("SCAN SOURCE"); self.import_btn.setObjectName("StartBtn"); self.import_btn.clicked.connect(self.on_import_click)
        self.cancel_btn = QPushButton("STOP"); self.cancel_btn.setObjectName("StopBtn"); self.cancel_btn.clicked.connect(self.cancel_import); self.cancel_btn.setEnabled(False)
        btn_layout.addWidget(self.import_btn); btn_layout.addWidget(self.cancel_btn); self.layout.addLayout(btn_layout)
        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.copy_log = QTextEdit(); self.copy_log.setReadOnly(True); self.copy_log.setMinimumHeight(40); self.copy_log.setStyleSheet("background-color: #1e1e1e; color: #2ECC71; font-family: Consolas; font-size: 11px;"); self.copy_log.setPlaceholderText("Copy Log...")
        self.transcode_log = QTextEdit(); self.transcode_log.setReadOnly(True); self.transcode_log.setMinimumHeight(40); self.transcode_log.setStyleSheet("background-color: #2c2c2c; color: #3498DB; font-family: Consolas; font-size: 11px;"); self.transcode_log.setPlaceholderText("Transcode Log..."); self.splitter.addWidget(self.copy_log); self.splitter.addWidget(self.transcode_log); self.layout.addWidget(self.splitter, 1)
        self.transcode_log.setVisible(False)
    def toggle_logs(self, show_copy, show_transcode): self.copy_log.setVisible(show_copy); self.transcode_log.setVisible(show_transcode); self.splitter.setVisible(show_copy or show_transcode)
    def toggle_transcode_ui(self, checked): 
        self.btn_config_trans.setVisible(checked); self.transcode_status_label.setVisible(checked)
        self.update_transfer_button_text()
    def open_transcode_config(self):
        dlg = TranscodeConfigDialog(self.transcode_widget, self); dlg.exec()
    def update_load_display(self, value): self.load_label.setText(f"🔥 CPU Load: {value}%")
    def set_transcode_active(self, active): self.load_label.setVisible(active); self.transcode_status_label.setVisible(active)
    def browse_source(self): 
        d = QFileDialog.getExistingDirectory(self, "Source", self.source_input.text()); 
        if d: self.source_input.setText(d)
    def browse_dest(self): 
        d = QFileDialog.getExistingDirectory(self, "Pick a Destination", self.dest_input.text()); 
        if d: self.dest_input.setText(d)
    def append_copy_log(self, text): self.copy_log.append(text); sb = self.copy_log.verticalScrollBar(); sb.setValue(sb.maximum())
    def append_transcode_log(self, text): self.transcode_log.append(text); sb = self.transcode_log.verticalScrollBar(); sb.setValue(sb.maximum())
    def run_auto_scan(self): self.auto_info_label.setText("Scanning..."); self.result_card.setVisible(False); self.select_device_box.setVisible(False); self.scan_btn.setEnabled(False); self.scan_watchdog.start(30000); self.scan_worker = ScanWorker(); self.scan_worker.finished_signal.connect(self.on_scan_finished); self.scan_worker.start()
    def on_scan_timeout(self): 
        if self.scan_worker.isRunning(): self.scan_worker.terminate(); self.auto_info_label.setText("Scan Timed Out")
    def on_scan_finished(self, results):
        self.scan_watchdog.stop(); self.found_devices = results; self.scan_btn.setEnabled(True)
        if results: self.auto_info_label.setText("✅ Scan Complete"); self.update_result_ui(results[0], len(results)>1)
        else: self.result_card.setVisible(False); self.auto_info_label.setText("No devices")
    def on_device_selection_change(self, idx): 
        if idx >= 0: self.update_result_ui(self.found_devices[idx], True)
    def update_result_ui(self, dev, multi):
        self.current_detected_path = dev['path']; self.source_input.setText(dev['path']); name = dev.get('display_name', dev.get('type', 'Unknown')); path_short = dev['path']; msg = f"✅ {name}" if not dev['empty'] else f"⚠️ {name} (Empty)"
        if len(path_short) > 35: path_short = path_short[:15] + "..." + path_short[-15:]
        self.result_label.setText(f"<h3 style='color:{'#27AE60' if not dev['empty'] else '#F39C12'}'>{msg}</h3><span style='color:white;'>{path_short}</span>")
        self.result_card.setStyleSheet(f"background-color: {'#2e3b33' if not dev['empty'] else '#4d3d2a'}; border: 2px solid {'#27AE60' if not dev['empty'] else '#F39C12'};"); self.result_card.setVisible(True)
        if multi:
            self.select_device_box.setVisible(True); self.select_device_box.blockSignals(True); self.select_device_box.clear()
            for d in self.found_devices: self.select_device_box.addItem(f"{d.get('display_name', d.get('type', 'Unknown'))} ({'Empty' if d['empty'] else 'Data'})")
            self.select_device_box.setCurrentIndex(self.found_devices.index(dev)); self.select_device_box.blockSignals(False); self.select_device_box.setStyleSheet(f"background-color: #1e1e1e; color: white; border: 1px solid {'#27AE60' if not dev['empty'] else '#F39C12'};")
    def on_import_click(self):
        debug_log(f"UI: Ingest Click | Mode: {self.ingest_mode}")
        if self.ingest_mode == "scan": self.start_scan()
        else: self.start_transfer()
    def start_scan(self):
        src = self.current_detected_path if self.source_tabs.currentIndex() == 0 else self.source_input.text()
        debug_log(f"UI: Scan Started | Source: {src}")
        if not src or not os.path.exists(src): 
            debug_log("UI: Scan Aborted - Invalid source path.")
            return QMessageBox.warning(self, "Error", "Invalid Source")
        self.import_btn.setEnabled(False); self.status_label.setText("SCANNING SOURCE..."); self.tree.clear(); self.review_group.setVisible(False)
        
        allowed_exts = None
        if self.source_tabs.currentIndex() == 0 and self.found_devices:
             idx = self.select_device_box.currentIndex()
             if idx >= 0 and idx < len(self.found_devices):
                 allowed_exts = self.found_devices[idx].get('exts')
                 debug_log(f"UI: Using device specific extensions: {allowed_exts}")

        self.scanner = IngestScanner(src, self.check_videos_only.isChecked(), allowed_exts)
        self.scanner.finished_signal.connect(self.on_scan_complete); self.scanner.start()
    def on_scan_complete(self, grouped_files):
        self.last_scan_results = grouped_files
        self.refresh_tree_view()

    def refresh_tree_view(self):
        self.tree.clear(); total_files = 0
        if not self.last_scan_results:
            p = QTreeWidgetItem(self.tree); p.setText(0, "Scan source to review media selection."); p.setFlags(p.flags() & ~Qt.ItemFlag.ItemIsUserCheckable); return
        
        sorted_dates = sorted(self.last_scan_results.keys(), reverse=True); video_exts = DeviceRegistry.VIDEO_EXTS
        for date in sorted_dates:
            all_files = self.last_scan_results[date]
            files = [f for f in all_files if os.path.splitext(f)[1].upper() in video_exts] if self.check_videos_only.isChecked() else all_files
            if not files: continue
            total_files += len(files)
            date_item = QTreeWidgetItem(self.tree); date_item.setText(0, f"{date} ({len(files)} files)"); date_item.setFlags(date_item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsAutoTristate); date_item.setCheckState(0, Qt.CheckState.Checked)
            for f in files:
                f_item = QTreeWidgetItem(date_item); f_item.setText(0, os.path.basename(f)); f_item.setData(0, Qt.ItemDataRole.UserRole, f); f_item.setFlags(f_item.flags() | Qt.ItemFlag.ItemIsUserCheckable); f_item.setCheckState(0, Qt.CheckState.Checked)
        
        if total_files == 0:
            p = QTreeWidgetItem(self.tree); p.setText(0, "No matching media found for current filters."); p.setFlags(p.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
        self.tree.expandAll(); self.review_group.setVisible(True); self.import_btn.setEnabled(True); self.ingest_mode = "transfer"
        self.status_label.setText(f"FOUND {total_files} FILES. SELECT MEDIA TO TRANSFER.")
        self.update_transfer_button_text()

    def update_transfer_button_text(self):
        if not hasattr(self, 'import_btn'): return
        if self.ingest_mode == "scan":
            self.import_btn.setText("SCAN SOURCE"); return
        
        count = 0; root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            date_item = root.child(i)
            for j in range(date_item.childCount()):
                if date_item.child(j).checkState(0) == Qt.CheckState.Checked: count += 1
        
        action = "TRANSFER/TRANSCODE" if self.check_transcode.isChecked() else "TRANSFER"
        self.import_btn.setText(f"START {action} ({count} FILES)")

    def start_transfer(self):
        selected_files = []
        if self.ingest_mode == "transfer":
             root = self.tree.invisibleRootItem()
             for i in range(root.childCount()):
                 date_item = root.child(i)
                 for j in range(date_item.childCount()):
                     f_item = date_item.child(j)
                     if f_item.checkState(0) == Qt.CheckState.Checked:
                         selected_files.append(f_item.data(0, Qt.ItemDataRole.UserRole))
             if not selected_files: return QMessageBox.warning(self, "Error", "No files selected.")

        src = self.current_detected_path if self.source_tabs.currentIndex() == 0 else self.source_input.text(); dest = self.dest_input.text()
        if not src or not dest: return QMessageBox.warning(self, "Error", "Set Source/Dest")
        self.save_tab_settings(); self.import_btn.setEnabled(False); self.cancel_btn.setEnabled(True); self.status_label.setText("INITIALIZING..."); self.copy_log.clear(); self.transcode_log.clear()
        if DEBUG_MODE and GUI_LOG_QUEUE:
            for msg in GUI_LOG_QUEUE: self.append_copy_log(msg)
            GUI_LOG_QUEUE.clear()
        self.storage_bar.setVisible(False) # Reset storage bar visibility
        tc_enabled = self.check_transcode.isChecked(); tc_settings = self.transcode_widget.get_settings(); use_gpu = self.transcode_widget.is_gpu_enabled()
        if tc_enabled:
            self.transcode_worker = AsyncTranscoder(tc_settings, use_gpu); self.transcode_worker.log_signal.connect(self.append_transcode_log); self.transcode_worker.status_signal.connect(self.transcode_status_label.setText); self.transcode_worker.metrics_signal.connect(self.transcode_status_label.setText); self.transcode_worker.all_finished_signal.connect(self.on_all_transcodes_finished); self.transcode_worker.start(); self.set_transcode_active(True)
        else: self.transcode_status_label.setVisible(False)
        self.copy_worker = CopyWorker(src, dest, self.project_name_input.text(), self.check_date.isChecked(), self.check_dupe.isChecked(), self.check_videos_only.isChecked(), self.device_combo.currentText(), self.check_verify.isChecked(), file_list=selected_files)
        self.copy_worker.log_signal.connect(self.append_copy_log); self.copy_worker.progress_signal.connect(self.progress_bar.setValue); self.copy_worker.status_signal.connect(self.status_label.setText); self.copy_worker.speed_signal.connect(self.speed_label.setText); self.copy_worker.finished_signal.connect(self.on_copy_finished)
        self.copy_worker.storage_check_signal.connect(self.update_storage_display_bar)
        if tc_enabled: self.copy_worker.transcode_count_signal.connect(self.transcode_worker.set_total_jobs); self.copy_worker.file_ready_signal.connect(self.queue_for_transcode)
        self.copy_worker.start()
    def update_storage_display_bar(self, needed, free, is_enough):
        self.storage_bar.setVisible(True); needed_gb = needed / (1024**3); free_gb = free / (1024**3)
        if is_enough:
            percent_usage = int((needed / free) * 100) if free > 0 else 100
            self.storage_bar.setValue(percent_usage); self.storage_bar.setFormat(f"Storage: Will use {needed_gb:.2f} GB of {free_gb:.2f} GB Free"); self.storage_bar.setStyleSheet("QProgressBar::chunk { background-color: #27AE60; }")
        else:
            self.storage_bar.setValue(100); self.storage_bar.setFormat(f"⚠️ INSUFFICIENT SPACE! Need {needed_gb:.2f} GB, Have {free_gb:.2f} GB"); self.storage_bar.setStyleSheet("QProgressBar::chunk { background-color: #C0392B; }")
        if not is_enough: SystemNotifier.notify("Ingest Failed", "Insufficient storage space on destination drive.")
    def queue_for_transcode(self, src_path, dest_path, filename):
        if self.transcode_worker:
            base_dir = os.path.dirname(dest_path); tc_dir = os.path.join(base_dir, "Edit_Ready"); os.makedirs(tc_dir, exist_ok=True); name_only = os.path.splitext(filename)[0]; transcode_dest = os.path.join(tc_dir, f"{name_only}_EDIT.mov"); self.transcode_worker.add_job(dest_path, transcode_dest, filename)
    def cancel_import(self):
        if self.copy_worker: self.copy_worker.stop(); self.copy_worker.wait()
        if self.transcode_worker: self.transcode_worker.stop(); self.transcode_worker.wait()
        self.status_label.setText("CANCELLED"); self.import_btn.setEnabled(True); self.cancel_btn.setEnabled(False); self.set_transcode_active(False)
    def on_copy_finished(self, success, msg):
        self.speed_label.setText(""); 
        if success: SystemNotifier.notify("Ingest Complete", "All files copied successfully.")
        else: SystemNotifier.notify("Ingest Failed", "Operation failed or cancelled.")
        if not self.check_transcode.isChecked():
            self.import_btn.setEnabled(True); self.cancel_btn.setEnabled(False); self.status_label.setText(msg); 
            if success: dlg = JobReportDialog("Ingest Complete", f"<h3>Ingest Successful</h3><p>{msg}</p>", self); dlg.exec()
            elif "Insufficient Storage" in msg: QMessageBox.critical(self, "Error", msg)
        else:
            self.status_label.setText("Copy Complete. Waiting for Transcodes..."); 
            if self.transcode_worker: 
                self.transcode_worker.set_producer_finished()
                if not self.transcode_worker.queue and self.transcode_worker.is_idle: self.transcode_worker.all_finished_signal.emit()
    def on_all_transcodes_finished(self):
        SystemNotifier.notify("Job Complete", "Ingest and Transcoding finished."); self.import_btn.setEnabled(True); self.cancel_btn.setEnabled(False); self.set_transcode_active(False); self.transcode_status_label.setText("All Transcodes Complete!"); dlg = JobReportDialog("Job Complete", "<h3>Job Complete</h3><p>All ingest and transcode operations finished successfully.</p>", self); dlg.exec()
    def save_tab_settings(self):
        s = self.app.settings; s.setValue("last_source", self.source_input.text()); s.setValue("last_dest", self.dest_input.text()); s.setValue("sort_date", self.check_date.isChecked()); s.setValue("skip_dupe", self.check_dupe.isChecked()); s.setValue("videos_only", self.check_videos_only.isChecked()); s.setValue("transcode_dnx", self.check_transcode.isChecked()); s.setValue("verify_copy", self.check_verify.isChecked())
        s.setValue("show_copy_log", self.copy_log.isVisible()); s.setValue("show_trans_log", self.transcode_log.isVisible())
    def load_tab_settings(self):
        s = self.app.settings; self.source_input.setText(s.value("last_source", "")); self.dest_input.setText(s.value("last_dest", "")); self.check_date.setChecked(s.value("sort_date", True, type=bool)); self.check_dupe.setChecked(s.value("skip_dupe", True, type=bool)); self.check_videos_only.setChecked(s.value("videos_only", False, type=bool)); self.check_transcode.setChecked(s.value("transcode_dnx", False, type=bool)); self.check_verify.setChecked(s.value("verify_copy", False, type=bool))
        show_copy = s.value("show_copy_log", True, type=bool); show_trans = s.value("show_trans_log", False, type=bool); self.toggle_logs(show_copy, show_trans); self.toggle_transcode_ui(self.check_transcode.isChecked())

class ConvertTab(QWidget):
    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.is_processing = False
        self.thumb_workers = []
        
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        self.setLayout(layout)
        
        self.settings = TranscodeSettingsWidget("Batch Conversion Settings", mode="general")
        layout.addWidget(self.settings)
        
        # Output Location
        out_group = QGroupBox("Output Location (Optional)")
        out_lay = QHBoxLayout()
        self.out_input = QLineEdit()
        self.out_input.setPlaceholderText("Default: Creates 'Converted' folder next to source files")
        self.btn_browse_out = QPushButton("Browse...")
        self.btn_browse_out.clicked.connect(self.browse_dest)
        self.btn_clear_out = QPushButton("Reset")
        self.btn_clear_out.clicked.connect(self.out_input.clear)
        out_lay.addWidget(self.out_input)
        out_lay.addWidget(self.btn_browse_out)
        out_lay.addWidget(self.btn_clear_out)
        out_group.setLayout(out_lay)
        layout.addWidget(out_group)
        
        # Input Files
        input_group = QGroupBox("Input Files")
        input_lay = QVBoxLayout()
        self.btn_browse = QPushButton("Select Video Files...")
        self.btn_browse.clicked.connect(self.browse_files)
        input_lay.addWidget(self.btn_browse)
        self.drop_area = QLabel("\n⬇️\n\nDRAG & DROP VIDEO FILES HERE\n\n")
        self.drop_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_area.setStyleSheet("""
            QLabel { border: 3px dashed #666; border-radius: 10px; background-color: #2b2b2b; color: #aaa; font-weight: bold; }
            QLabel:hover { border-color: #3498DB; background-color: #333; color: white; }
        """)
        input_lay.addWidget(self.drop_area, 1)
        input_group.setLayout(input_lay)
        layout.addWidget(input_group, 1)
        
        # Job Queue
        queue_group = QGroupBox("Job Queue")
        queue_lay = QVBoxLayout()
        self.list = QListWidget()
        self.list.setMaximumHeight(150) # Increased height for thumbnails
        self.list.setDragDropMode(QAbstractItemView.DragDropMode.DropOnly)
        self.list.setIconSize(QSize(96, 54))
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self.show_context_menu)
        queue_lay.addWidget(self.list)
        
        dash_row = QHBoxLayout()
        self.status_label = QLabel("Waiting...")
        self.status_label.setStyleSheet("color: #888;")
        self.load_label = QLabel("")
        self.load_label.setStyleSheet("color: #E74C3C; font-weight: bold;")
        self.load_label.setVisible(False)
        dash_row.addWidget(self.status_label)
        dash_row.addStretch()
        dash_row.addWidget(self.load_label)
        queue_lay.addLayout(dash_row)
        
        self.pbar = QProgressBar()
        self.pbar.setTextVisible(True)
        queue_lay.addWidget(self.pbar)
        
        h = QHBoxLayout()
        b_clr = QPushButton("Clear Queue")
        b_clr.clicked.connect(self.list.clear)
        self.btn_go = QPushButton("START BATCH")
        self.btn_go.setObjectName("StartBtn")
        self.btn_go.clicked.connect(self.on_btn_click)
        h.addWidget(b_clr)
        h.addWidget(self.btn_go)
        queue_lay.addLayout(h)
        queue_group.setLayout(queue_lay)
        layout.addWidget(queue_group)
        
    def update_load_display(self, value):
        self.load_label.setText(f"🔥 CPU: {value}%")

    def browse_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Videos", "", "Video Files (*.mp4 *.mov *.mkv *.avi)")
        if files:
            [self.list.addItem(f) for f in files]; self.start_thumb_process(files)
    def browse_dest(self): 
        d = QFileDialog.getExistingDirectory(self, "Pick a Destination")
        if d: self.out_input.setText(d)
    def dragEnterEvent(self, e): 
        if e.mimeData().hasUrls(): e.accept()
    def dropEvent(self, e):
        new_files = []
        for u in e.mimeData().urls():
            f = u.toLocalFile()
            if f.lower().endswith(('.mp4','.mov','.mkv','.avi')): self.list.addItem(f); new_files.append(f)
        if new_files: self.start_thumb_process(new_files)
    def on_btn_click(self):
        if self.is_processing: self.stop()
        else: self.start()
    def toggle_ui_state(self, running):
        self.is_processing = running
        self.load_label.setVisible(running)
        if running: self.btn_go.setText("STOP BATCH"); self.btn_go.setObjectName("StopBtn")
        else: self.btn_go.setText("START BATCH"); self.btn_go.setObjectName("StartBtn")
        self.btn_go.style().unpolish(self.btn_go); self.btn_go.style().polish(self.btn_go)
    def start(self):
        files = [self.list.item(i).text() for i in range(self.list.count())]
        if not files: return QMessageBox.warning(self, "Empty", "Queue is empty.")
        self.toggle_ui_state(True); dest_folder = self.out_input.text().strip(); use_gpu = self.settings.is_gpu_enabled()
        self.worker = BatchTranscodeWorker(files, dest_folder, self.settings.get_settings(), mode="convert", use_gpu=use_gpu)
        self.worker.progress_signal.connect(self.pbar.setValue); self.worker.status_signal.connect(self.status_label.setText); self.worker.log_signal.connect(lambda s: self.status_label.setText(s)); self.worker.finished_signal.connect(self.on_finished); self.worker.start()
    def start_thumb_process(self, files):
        worker = ThumbnailWorker(files); worker.thumb_ready.connect(self.update_thumbnail)
        worker.finished.connect(lambda: self.thumb_workers.remove(worker) if worker in self.thumb_workers else None)
        worker.start(); self.thumb_workers.append(worker)
    def update_thumbnail(self, path, image):
        pixmap = QPixmap.fromImage(image)
        items = self.list.findItems(path, Qt.MatchFlag.MatchExactly)
        for item in items: item.setIcon(QIcon(pixmap))
    def stop(self):
        if self.worker: self.worker.stop(); self.status.setText("Stopping...")
    def on_finished(self):
        SystemNotifier.notify("Batch Complete", "Transcoding batch finished.")
        self.toggle_ui_state(False); self.status.setText("Batch Complete!"); dest = self.out_input.text(); msg = f"Files saved to:\n{dest}" if dest else "Files saved to 'Converted' folder next to the source file(s)."; dlg = JobReportDialog("Batch Complete", f"<h3>Batch Successful</h3><p>{msg}</p>", self); dlg.exec()
    def show_context_menu(self, pos):
        item = self.list.itemAt(pos)
        if item:
            menu = QMenu(self); action = QAction("Inspect Media Info", self); action.triggered.connect(lambda: self.inspect_file(item)); menu.addAction(action); menu.exec(self.list.mapToGlobal(pos))
    def inspect_file(self, item):
        path = item.text()
        if os.path.exists(path):
            info = MediaInfoExtractor.get_info(path); dlg = MediaInfoDialog(info, self); dlg.exec()

class DeliveryTab(QWidget):
    def __init__(self):
        super().__init__(); self.setAcceptDrops(True); layout = QVBoxLayout(); layout.setSpacing(15); layout.setContentsMargins(20, 20, 20, 20); self.setLayout(layout); self.is_processing = False
        self.settings = TranscodeSettingsWidget("Delivery Settings", mode="delivery"); self.settings.preset_combo.setCurrentText("H.264 / AVC (Standard)"); layout.addWidget(self.settings)
        form_group = QGroupBox("Input/Output"); fl = QFormLayout()
        self.inp_file = FileDropLineEdit(); self.inp_file.setPlaceholderText("Drag Master File Here or Browse")
        b1 = QPushButton("Select Master"); b1.clicked.connect(lambda: self.inp_file.setText(QFileDialog.getOpenFileName(self, "Select Master File")[0]))
        self.inp_dest = QLineEdit(); self.inp_dest.setPlaceholderText("Default: Creates 'Final_Render' folder next to master file")
        b2 = QPushButton("Select Output Folder"); b2.clicked.connect(lambda: self.inp_dest.setText(QFileDialog.getExistingDirectory(self, "Pick a Destination")))
        r1 = QHBoxLayout(); r1.addWidget(self.inp_file); r1.addWidget(b1); r2 = QHBoxLayout(); r2.addWidget(self.inp_dest); r2.addWidget(b2)
        fl.addRow("Master File:", r1); fl.addRow("Output Location:", r2); form_group.setLayout(fl); layout.addWidget(form_group)
        self.drop_area = QLabel("\n⬇️\n\nDRAG MASTER FILE HERE\n\n"); self.drop_area.setAlignment(Qt.AlignmentFlag.AlignCenter); self.drop_area.setStyleSheet("""QLabel { border: 3px dashed #666; border-radius: 10px; background-color: #2b2b2b; color: #aaa; font-weight: bold; } QLabel:hover { border-color: #3498DB; background-color: #333; color: white; }"""); layout.addWidget(self.drop_area, 1); layout.addStretch()
        dash_frame = QFrame(); dash_frame.setObjectName("DashFrame"); dl = QVBoxLayout(dash_frame)
        self.status = QLabel("Ready to Render"); dl.addWidget(self.status); self.pbar = QProgressBar(); self.pbar.setTextVisible(True); dl.addWidget(self.pbar); layout.addWidget(dash_frame)
        self.btn_go = QPushButton("RENDER"); self.btn_go.setObjectName("StartBtn"); self.btn_go.setMinimumHeight(50); self.btn_go.clicked.connect(self.on_btn_click); layout.addWidget(self.btn_go)
    def dragEnterEvent(self, e): 
        if e.mimeData().hasUrls(): e.accept()
    def dropEvent(self, e):
        urls = e.mimeData().urls() 
        if urls:
            fpath = urls[0].toLocalFile()
            if fpath.lower().endswith(('.mp4','.mov','.mkv','.avi')): self.inp_file.setText(fpath)
    def on_btn_click(self):
        if self.is_processing: self.stop()
        else: self.start()
    def toggle_ui_state(self, running):
        self.is_processing = running
        if running: self.btn_go.setText("STOP RENDER"); self.btn_go.setObjectName("StopBtn")
        else: self.btn_go.setText("RENDER"); self.btn_go.setObjectName("StartBtn")
        self.btn_go.style().unpolish(self.btn_go); self.btn_go.style().polish(self.btn_go)
    def start(self):
        if not self.inp_file.text(): return QMessageBox.warning(self, "Missing Info", "Please select a master file.")
        self.toggle_ui_state(True); use_gpu = self.settings.is_gpu_enabled(); dest_folder = self.inp_dest.text().strip()
        self.worker = BatchTranscodeWorker([self.inp_file.text()], dest_folder, self.settings.get_settings(), mode="delivery", use_gpu=use_gpu)
        self.worker.progress_signal.connect(self.pbar.setValue); self.worker.status_signal.connect(self.status.setText); self.worker.finished_signal.connect(self.on_finished); self.worker.start()
    def stop(self):
        if self.worker: self.worker.stop(); self.status.setText("Stopping...")
    def on_finished(self):
        SystemNotifier.notify("Render Complete", "Delivery render finished.")
        self.toggle_ui_state(False); self.status.setText("Delivery Render Complete!"); dest = self.inp_dest.text(); msg = f"File saved to:\n{dest}" if dest else "File saved to 'Final_Render' folder next to the master file."; dlg = JobReportDialog("Render Complete", f"<h3>Render Successful</h3><p>{msg}</p>", self); dlg.exec()

class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent); self.setWindowTitle("About CineBridge Pro"); self.setFixedWidth(400); layout = QVBoxLayout()
        layout.setSpacing(15); layout.setContentsMargins(30, 30, 30, 30)
        logo_label = QLabel(); logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if hasattr(sys, '_MEIPASS'): base_dir = sys._MEIPASS
        else: base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        logo_path = os.path.join(base_dir, "assets", "icon.svg")
        
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path); logo_label.setPixmap(pixmap.scaled(80, 80, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        layout.addWidget(logo_label)
        title = QLabel("CineBridge Pro"); title.setStyleSheet("font-size: 22px; font-weight: bold; color: #3498DB;"); title.setAlignment(Qt.AlignmentFlag.AlignCenter); layout.addWidget(title)
        version = QLabel("v4.15.0 (Dev)"); version.setStyleSheet("font-size: 14px; color: #888;"); version.setAlignment(Qt.AlignmentFlag.AlignCenter); layout.addWidget(version)
        desc = QLabel("The Linux DIT & Post-Production Suite.\nSolving the 'Resolve on Linux' problem."); desc.setWordWrap(True); desc.setStyleSheet("font-size: 13px;"); desc.setAlignment(Qt.AlignmentFlag.AlignCenter); layout.addWidget(desc)
        credits = QLabel("<b>Developed by:</b><br>Donovan Goodwin<br>(with Gemini AI)"); credits.setStyleSheet("font-size: 13px;"); credits.setAlignment(Qt.AlignmentFlag.AlignCenter); layout.addWidget(credits)
        links = QLabel('<a href="mailto:ddg2goodwin@gmail.com" style="color: #3498DB;">ddg2goodwin@gmail.com</a><br><br><a href="https://github.com/DGxInfinitY" style="color: #3498DB;">GitHub: DGxInfinitY</a>'); links.setOpenExternalLinks(True); links.setAlignment(Qt.AlignmentFlag.AlignCenter); layout.addWidget(links)
        layout.addStretch(); btn_box = QHBoxLayout(); ok_btn = QPushButton("Close"); ok_btn.setFixedWidth(100); ok_btn.clicked.connect(self.accept); btn_box.addStretch(); btn_box.addWidget(ok_btn); btn_box.addStretch(); layout.addLayout(btn_box); self.setLayout(layout)

class CineBridgeApp(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle("CineBridge Pro: Open Source DIT Suite"); self.setGeometry(100, 100, 1100, 850); self.settings = QSettings("CineBridgePro", "Config")
        if hasattr(sys, '_MEIPASS'): base_dir = sys._MEIPASS
        else: base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        icon_svg = os.path.join(base_dir, "assets", "icon.svg"); icon_png = os.path.join(base_dir, "assets", "icon.png")
        if os.path.exists(icon_svg): self.setWindowIcon(QIcon(icon_svg))
        elif os.path.exists(icon_png): self.setWindowIcon(QIcon(icon_png))
        self.tabs = QTabWidget(); self.tabs.setTabPosition(QTabWidget.TabPosition.North); self.tabs.setStyleSheet("QTabBar::tab { height: 40px; width: 150px; font-weight: bold; }")
        self.settings_btn = QToolButton(); self.settings_btn.setText("⚙"); self.settings_btn.setStyleSheet("QToolButton { font-size: 20px; border: none; background: transparent; padding: 5px; } QToolButton:hover { color: #3498DB; }"); self.settings_btn.clicked.connect(self.open_settings); self.tabs.setCornerWidget(self.settings_btn, Qt.Corner.TopRightCorner)
        self.tab_ingest = IngestTab(self); self.tab_convert = ConvertTab(); self.tab_delivery = DeliveryTab(); self.tabs.addTab(self.tab_ingest, "📥 INGEST"); self.tabs.addTab(self.tab_convert, "🛠️ CONVERT"); self.tabs.addTab(self.tab_delivery, "🚀 DELIVERY"); self.setCentralWidget(self.tabs)
        self.tab_ingest.transcode_widget.chk_gpu.toggled.connect(self.sync_gpu_toggle); self.tab_convert.settings.chk_gpu.toggled.connect(self.sync_gpu_toggle); self.tab_delivery.settings.chk_gpu.toggled.connect(self.sync_gpu_toggle)
        
        # Global System Monitor
        self.sys_monitor = SystemMonitor()
        self.sys_monitor.cpu_signal.connect(self.tab_ingest.update_load_display)
        self.sys_monitor.cpu_signal.connect(self.tab_convert.update_load_display)
        self.sys_monitor.start()

        saved_gpu = self.settings.value("use_gpu_accel", False, type=bool); self.sync_gpu_toggle(saved_gpu); self.theme_mode = self.settings.value("theme_mode", "light"); self.set_theme(self.theme_mode)
        self.theme_timer = QTimer(self); self.theme_timer.timeout.connect(self.check_system_theme); self.theme_timer.start(2000)
    
    # --- NEW CLOSE EVENT HANDLER ---
    def closeEvent(self, event):
        """Forces a save of all critical settings and ensures safe worker shutdown."""
        try:
            if hasattr(self, 'tab_convert'):
                for worker in self.tab_convert.thumb_workers:
                    worker.stop()
                    # Wait up to 500ms for clean exit, then terminate if stuck
                    if not worker.wait(500):
                        worker.terminate()
        except: pass
        
        self.tab_ingest.save_tab_settings()
        self.settings.setValue("show_copy_log", self.tab_ingest.copy_log.isVisible())
        self.settings.setValue("show_trans_log", self.tab_ingest.transcode_log.isVisible())
        self.settings.sync() 
        event.accept()
    # --------------------------------

    def check_system_theme(self):
        if self.theme_mode != "system": return
        system_is_dark = self.is_system_dark(); current_app_is_dark = getattr(self, 'current_applied_is_dark', None)
        if current_app_is_dark is None or system_is_dark != current_app_is_dark: self.set_theme("system")
    def is_system_dark(self):
        if platform.system() == "Linux":
            try:
                res = subprocess.run(["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"], capture_output=True, text=True, timeout=0.5, env=EnvUtils.get_clean_env())
                if "prefer-dark" in res.stdout: return True
                res2 = subprocess.run(["gsettings", "get", "org.gnome.desktop.interface", "gtk-theme"], capture_output=True, text=True, timeout=0.5, env=EnvUtils.get_clean_env())
                if "dark" in res2.stdout.lower(): return True
            except: pass
        try: return QApplication.palette().color(QPalette.ColorRole.Window).lightness() < 128
        except: return False
    def open_settings(self): dlg = SettingsDialog(self); dlg.exec()
    def update_log_visibility(self): pass
    def reset_to_defaults(self):
        reply = QMessageBox.question(self, "Confirm Reset", "Are you sure you want to reset all settings to default? This cannot be undone.", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.settings.clear(); self.settings.sync(); self.set_theme("light"); self.tab_ingest.chk_date.setChecked(True); self.tab_ingest.chk_dupe.setChecked(True); self.tab_ingest.chk_videos_only.setChecked(False); self.tab_ingest.chk_transcode.setChecked(False); self.tab_ingest.toggle_logs(True, False); self.sync_gpu_toggle(False); QMessageBox.information(self, "Reset", "Settings have been reset to defaults.")
    def sync_gpu_toggle(self, checked):
        for widget in [self.tab_ingest.transcode_widget, self.tab_convert.settings, self.tab_delivery.settings]: widget.set_gpu_checked(checked)
        self.settings.setValue("use_gpu_accel", checked)
    def toggle_debug(self): global DEBUG_MODE; DEBUG_MODE = not DEBUG_MODE; debug_log("Debug logging active.")
    def show_about(self): dlg = AboutDialog(self); dlg.exec()
    def set_theme(self, mode):
        self.theme_mode = mode; self.settings.setValue("theme_mode", mode); is_dark = False
        if mode == "dark": is_dark = True
        elif mode == "system": is_dark = self.is_system_dark()
        self.current_applied_is_dark = is_dark
        style = """QMainWindow, QWidget { background-color: #F0F2F5; color: #333; font-family: 'Segoe UI'; font-size: 14px; } QGroupBox { background: #FFF; border: 1px solid #CCC; border-radius: 5px; margin-top: 20px; font-weight: bold; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; color: #2980B9; } QLineEdit, QComboBox, QTextEdit, QListWidget { background: #FFF; border: 1px solid #CCC; color: #333; } QPushButton { background: #E0E0E0; border: 1px solid #CCC; color: #333; padding: 8px; } QPushButton:hover { background: #D0D0D0; } QPushButton#StartBtn { background: #3498DB; color: white; font-weight: bold; } QPushButton#StopBtn { background: #E74C3C; color: white; font-weight: bold; } QTabWidget::pane { border: 1px solid #CCC; } QTabBar::tab { background: #E0E0E0; color: #555; border: 1px solid #CCC; } QTabBar::tab:selected { background: #FFF; color: #2980B9; border-top: 2px solid #2980B9; } QFrame#ResultCard, QFrame#DashFrame { background-color: #FFF; border-radius: 8px; }"""
        if is_dark: style = """QMainWindow, QWidget { background-color: #2b2b2b; color: #e0e0e0; font-family: 'Segoe UI'; font-size: 14px; } QGroupBox { background: #333; border: 1px solid #444; border-radius: 5px; margin-top: 20px; font-weight: bold; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; color: #3498DB; } QLineEdit, QComboBox, QTextEdit, QListWidget { background: #1e1e1e; border: 1px solid #555; color: white; } QPushButton { background: #444; border: 1px solid #555; color: white; padding: 8px; } QPushButton:hover { background: #555; } QPushButton#StartBtn { background: #2980B9; font-weight: bold; } QPushButton#StopBtn { background: #C0392B; font-weight: bold; } QTabWidget::pane { border: 1px solid #444; } QTabBar::tab { background: #222; color: #888; border: 1px solid #444; } QTabBar::tab:selected { background: #333; color: #3498DB; border-top: 2px solid #3498DB; } QFrame#ResultCard, QFrame#DashFrame { background-color: #1e1e1e; border-radius: 8px; }"""
        self.setStyleSheet(style)
        if hasattr(self, 'tab_ingest') and self.tab_ingest.result_card.isVisible():
             if self.tab_ingest.current_detected_path:
                 info = {'path': self.tab_ingest.current_detected_path, 'type': self.tab_ingest.device_combo.currentText(), 'empty': False}
                 self.tab_ingest.update_result_ui(info, multi=self.tab_ingest.select_device_box.isVisible())

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    AppLogger.init_log()
    app = QApplication(sys.argv); app.setDesktopFileName("CineBridgePro")
    timer = QTimer(); timer.start(500); timer.timeout.connect(lambda: None) 
    app.setStyle("Fusion"); window = CineBridgeApp(); window.show(); sys.exit(app.exec())
