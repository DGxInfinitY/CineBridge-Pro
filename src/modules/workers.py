import os
import time
import shutil
import platform
import subprocess
import hashlib
from collections import deque
from datetime import datetime
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QImage

try:
    import xxhash
    HAS_XXHASH = True
except ImportError:
    HAS_XXHASH = False

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

from .config import DEBUG_MODE, debug_log, info_log, error_log
from .utils import DriveDetector, DeviceRegistry, EnvUtils, TranscodeEngine, DependencyManager

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
        self.main_video_exts = DeviceRegistry.VIDEO_EXTS
        self.transfer_data = [] # List of dicts for report
    
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
                current_hash = "N/A"
                if self.verify_copy and self.is_running:
                    self.status_signal.emit(f"Verifying {idx + 1}/{total_files}: {filename}")
                    src_hash, algo = self.calculate_hash(src_path)
                    dest_hash, _ = self.calculate_hash(dest_path)
                    
                    if src_hash and dest_hash and src_hash == dest_hash:
                        self.log_signal.emit(f"✅ Verified ({algo}): {filename}")
                        current_hash = src_hash
                    else:
                        self.log_signal.emit(f"❌ VERIFICATION FAILED: {filename}")
                        current_hash = "FAILED"
                else:
                    self.log_signal.emit(f"✔️ Copied: {filename}")

                # Store for report
                self.transfer_data.append({
                    'name': filename,
                    'size': file_size,
                    'hash': current_hash,
                    'status': "OK" if current_hash != "FAILED" else "VERIFY FAILED"
                })

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
                            if pct > 0: self.progress_signal.emit(pct)
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
