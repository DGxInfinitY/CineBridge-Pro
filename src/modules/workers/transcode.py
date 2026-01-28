import os
import platform
import subprocess
import time
import shutil
from collections import deque
from PyQt6.QtCore import QThread, pyqtSignal
from ..config import debug_log, error_log
from ..utils import EnvUtils, TranscodeEngine, DependencyManager, DeviceRegistry

class AsyncTranscoder(QThread):
    log_signal = pyqtSignal(str); status_signal = pyqtSignal(str); metrics_signal = pyqtSignal(str); progress_signal = pyqtSignal(int); all_finished_signal = pyqtSignal()
    def __init__(self, settings, use_gpu):
        super().__init__(); self.settings = settings; self.use_gpu = use_gpu; self.queue = deque(); self.is_running = True; self.is_idle = True; self.total_expected_jobs = 0; self.completed_jobs = 0; self.producer_finished = False
    def set_total_jobs(self, count): self.total_expected_jobs = count
    def add_job(self, input_path, output_path, filename):
        ext = os.path.splitext(filename)[1].upper()
        if ext not in DeviceRegistry.VIDEO_EXTS:
            self.log_signal.emit(f"⚠️ Skipped non-video file: {filename}")
            return
        self.queue.append({'in': input_path, 'out': output_path, 'name': filename})
    def report_skipped(self, filename):
        self.completed_jobs += 1
        display_total = self.total_expected_jobs if self.total_expected_jobs > 0 else (self.completed_jobs + len(self.queue))
        self.status_signal.emit(f"Skipped {self.completed_jobs}/{display_total}: {filename}"); self.progress_signal.emit(100)
    def set_producer_finished(self): self.producer_finished = True
    def run(self):
        ffmpeg_bin = DependencyManager.get_ffmpeg_path()
        if not ffmpeg_bin: self.log_signal.emit("❌ Error: FFmpeg binary not found."); return
        while self.is_running:
            if not self.queue:
                if self.producer_finished: self.all_finished_signal.emit(); break
                else: self.is_idle = True; time.sleep(0.5); continue
            self.is_idle = False; job = self.queue.popleft(); display_total = self.total_expected_jobs if self.total_expected_jobs > 0 else (self.completed_jobs + len(self.queue) + 1)
            base_status = f"Transcoding {self.completed_jobs + 1}/{display_total}: {job['name']}"
            self.status_signal.emit(base_status); 
            
            # Detailed Start Log
            v_codec = self.settings.get('v_codec', 'auto'); res = self.settings.get('resolution', 'Source')
            self.log_signal.emit(f"🎬 Transcoding Started: {job['name']} [{v_codec.upper()} | {res}]")
            
            cmd = TranscodeEngine.build_command(job['in'], job['out'], self.settings, self.use_gpu)
            if not cmd: self.completed_jobs += 1; continue
            
            duration = TranscodeEngine.get_duration(job['in']); start_time = time.time()
            try:
                startupinfo = None
                if platform.system() == 'Windows': startupinfo = subprocess.STARTUPINFO(); startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, universal_newlines=True, startupinfo=startupinfo, env=EnvUtils.get_clean_env())
                
                last_errors = deque(maxlen=10)
                while True:
                    if not self.is_running: process.kill(); process.wait(); break
                    line = process.stderr.readline()
                    if not line and process.poll() is not None: break
                    if line:
                        last_errors.append(line.strip())
                        if duration > 0:
                            pct, speed_str = TranscodeEngine.parse_progress(line, duration)
                            if pct > 0: self.progress_signal.emit(pct)
                            if speed_str: self.metrics_signal.emit(f"🎬 {speed_str}")
                
                elapsed = time.time() - start_time
                if process.returncode == 0: 
                    self.log_signal.emit(f"✅ Transcode Finished: {job['name']} (took {elapsed:.1f}s)")
                else: 
                    err_msg = " | ".join(list(last_errors))
                    self.log_signal.emit(f"❌ Transcode Failed: {job['name']} (Exit: {process.returncode}) Log: {err_msg}")
            except Exception as e: error_log(f"Transcode Critical Error: {e}")
            self.completed_jobs += 1
    def stop(self): self.is_running = False

class BatchTranscodeWorker(QThread):
    progress_signal = pyqtSignal(int); log_signal = pyqtSignal(str); status_signal = pyqtSignal(str); metrics_signal = pyqtSignal(str); finished_signal = pyqtSignal(bool, str)
    def __init__(self, file_list, dest_folder, settings, mode="convert", use_gpu=False):
        super().__init__(); self.files = file_list; self.dest = dest_folder; self.settings = settings; self.mode = mode; self.use_gpu = use_gpu; self.is_running = True
    def run(self):
        total = len(self.files); total_duration = 0
        for f in self.files:
            try: d = TranscodeEngine.get_duration(f); total_duration += d
            except: pass
        
        # Estimate storage (100MB/s for high-quality, 10MB/s for H.264)
        codec = self.settings.get('v_codec', 'dnxhd')
        est_mbps = 100 if codec in ['dnxhd', 'prores_ks'] else 10
        needed = int(total_duration * est_mbps * 1024 * 1024)
        
        target_base = self.dest if (self.dest and os.path.isdir(self.dest)) else os.path.dirname(self.files[0])
        try:
            free = shutil.disk_usage(target_base).free
            if free < (needed + 524288000): # 500MB buffer
                self.finished_signal.emit(False, f"Insufficient storage! Need ~{needed/1073741824:.1f} GB"); return
        except: pass

        for i, input_path in enumerate(self.files):
            if not self.is_running: break
            filename = os.path.basename(input_path); name_only = os.path.splitext(filename)[0]
            if self.mode == "convert":
                target_dir = self.dest if (self.dest and os.path.isdir(self.dest)) else os.path.join(os.path.dirname(input_path), "Converted")
                output_path = os.path.join(target_dir, f"{name_only}_CNV.mov")
            else:
                target_dir = self.dest if (self.dest and os.path.isdir(self.dest)) else os.path.join(os.path.dirname(input_path), "Final_Render")
                ext = ".mp4" if "libx26" in self.settings.get('v_codec', '') else ".mov"
                output_path = os.path.join(target_dir, f"{name_only}_DELIVERY{ext}")
            os.makedirs(target_dir, exist_ok=True)
            self.status_signal.emit(f"Processing {i+1}/{total}: {filename}")
            cmd = TranscodeEngine.build_command(input_path, output_path, self.settings, self.use_gpu); duration = TranscodeEngine.get_duration(input_path)
            
            if not cmd:
                self.log_signal.emit(f"⚠️ Skipped invalid source/settings: {filename}")
                continue

            try:
                startupinfo = None
                if platform.system() == 'Windows': startupinfo = subprocess.STARTUPINFO(); startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, universal_newlines=True, startupinfo=startupinfo, env=EnvUtils.get_clean_env())
                
                last_errors = deque(maxlen=10)
                while True:
                    if not self.is_running: process.kill(); process.wait(); break
                    line = process.stderr.readline()
                    if not line and process.poll() is not None: break
                    if line:
                        last_errors.append(line.strip())
                        if duration > 0:
                            pct, speed = TranscodeEngine.parse_progress(line, duration)
                            if pct > 0: self.progress_signal.emit(pct)
                            if speed: self.metrics_signal.emit(f"🎬 {speed}")
                
                if not self.is_running: break

                if process.returncode != 0: 
                    err_msg = " | ".join(list(last_errors))
                    self.log_signal.emit(f"❌ Error transcoding {filename} (Exit: {process.returncode}). Log: {err_msg}")
            except Exception as e: error_log(f"Batch Transcode Error: {e}")
        
        if self.is_running:
            self.finished_signal.emit(True, "Complete")
    def stop(self): self.is_running = False
