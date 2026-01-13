import os
import platform
import subprocess
from datetime import datetime
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QImage
from ..config import DEBUG_MODE, debug_log, error_log
from ..utils import DriveDetector, DeviceRegistry, EnvUtils, DependencyManager

class ScanWorker(QThread):
    finished_signal = pyqtSignal(list)
    def run(self):
        results = []
        try:
            usb_hints = DriveDetector.get_usb_hardware_hints()
            candidates = sorted(list(set(DriveDetector.get_potential_mounts())))
            for mount in candidates:
                if mount == "/" or mount == "/home": continue 
                has_files = False
                try: 
                    if len(DriveDetector.safe_list_dir(mount)) > 0: has_files = True
                except: pass
                name, true_path, exts = DeviceRegistry.identify(mount, usb_hints)
                results.append({'path': true_path, 'display_name': name, 'root': mount, 'empty': not has_files, 'exts': exts})
            final = []; seen = set()
            for r in sorted(results, key=lambda x: len(x['path']), reverse=True):
                if r['path'] not in seen: final.append(r); seen.add(r['path'])
            self.finished_signal.emit(final)
        except Exception as e:
            debug_log(f"Scan Error: {e}"); self.finished_signal.emit([])

class ThumbnailWorker(QThread):
    thumb_ready = pyqtSignal(str, QImage); status_signal = pyqtSignal(str)
    def __init__(self, file_queue): super().__init__(); self.queue = file_queue; self.is_running = True
    def run(self):
        ffmpeg = DependencyManager.get_ffmpeg_path()
        if not ffmpeg: 
            error_log("ThumbnailWorker: FFmpeg binary not found. Thumbnails disabled."); return
        total = len(self.queue)
        for idx, path in enumerate(self.queue):
            if not self.is_running: break
            if not os.path.exists(path): continue
            self.status_signal.emit(f"Extracting Thumbnails ({idx+1}/{total})")
            try:
                cmd = [ffmpeg, '-y', '-ss', '00:00:00.5', '-i', path, '-vframes', '1', '-vf', 'scale=320:-1', '-f', 'image2pipe', '-']
                startupinfo = None
                if platform.system() == 'Windows': startupinfo = subprocess.STARTUPINFO(); startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, startupinfo=startupinfo, env=EnvUtils.get_clean_env(), timeout=10)
                if res.returncode == 0 and res.stdout:
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
        if self.allowed_exts: exts = set(self.allowed_exts)
        else:
            exts = DeviceRegistry.VIDEO_EXTS
            if not self.video_only: exts = DeviceRegistry.get_all_valid_exts()
        for root, dirs, files in os.walk(self.source):
            for f in files:
                if os.path.splitext(f)[1].upper() in exts:
                    full = os.path.join(root, f)
                    try: date = datetime.fromtimestamp(os.path.getmtime(full)).strftime("%Y-%m-%d")
                    except: date = "Unknown Date"
                    if date not in grouped: grouped[date] = []
                    grouped[date].append(full)
        self.finished_signal.emit(grouped)
