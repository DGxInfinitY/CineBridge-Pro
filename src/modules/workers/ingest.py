import os
import time
import shutil
import hashlib
from PyQt6.QtCore import QThread, pyqtSignal
from ..utils import DeviceRegistry, HAS_XXHASH
if HAS_XXHASH: import xxhash

class CopyWorker(QThread):
    log_signal = pyqtSignal(str); progress_signal = pyqtSignal(int); status_signal = pyqtSignal(str); speed_signal = pyqtSignal(str); file_ready_signal = pyqtSignal(str, str, str); transcode_count_signal = pyqtSignal(int); finished_signal = pyqtSignal(bool, str)
    storage_check_signal = pyqtSignal(int, int, bool)
    
    def __init__(self, source, dest_list, project_name, sort_by_date, skip_dupes, videos_only, camera_override, verify_copy, file_list=None, transcode_settings=None):
        super().__init__(); self.source = source; self.dest_list = [d.strip() for d in dest_list if d.strip()]; self.project_name = project_name.strip(); self.sort_by_date = sort_by_date; self.skip_dupes = skip_dupes; self.videos_only = videos_only; self.camera_override = camera_override; self.verify_copy = verify_copy; self.file_list = file_list; self.transcode_settings = transcode_settings; self.is_running = True
        self.transfer_data = []
    
    def get_mmt_category(self, filename):
        ext = os.path.splitext(filename.upper())[1]
        if ext in DeviceRegistry.VIDEO_EXTS: return "videos"
        if ext in ['.JPG', '.JPEG', '.PNG', '.INSP']: return "photos"
        if ext in ['.DNG', '.GPR']: return "raw"
        if ext in ['.WAV', '.MP3']: return "audios"
        return "misc"
    
    def get_media_date(self, file_path):
        try: return time.strftime('%Y-%m-%d', time.localtime(os.path.getmtime(file_path)))
        except: return "Unsorted"
        
    def calculate_hash(self, file_path):
        try:
            h = xxhash.xxh64() if HAS_XXHASH else hashlib.md5()
            with open(file_path, 'rb') as f:
                while chunk := f.read(4194304): h.update(chunk)
            return h.hexdigest(), "xxHash64" if HAS_XXHASH else "MD5"
        except: return None, "Error"
    
    def get_free_space(self, path):
        p = path
        while not os.path.exists(p):
            parent = os.path.dirname(p)
            if parent == p: break
            p = parent
        try: return shutil.disk_usage(p).free
        except: return 0

    def run(self):
        active_dests = [os.path.join(d, self.project_name) if self.project_name else d for d in self.dest_list]
        if not active_dests: self.finished_signal.emit(False, "No destinations set."); return
        found_files = self.file_list if self.file_list else []
        if not found_files:
            for root, dirs, files in os.walk(self.source):
                for f in files:
                    if f.upper().endswith(tuple(DeviceRegistry.get_all_valid_exts())): found_files.append(os.path.join(root, f))
        
        v_exts = DeviceRegistry.VIDEO_EXTS
        files_to_process = [f for f in found_files if os.path.splitext(f)[1].upper() in v_exts] if self.videos_only else found_files
        total_files = len(files_to_process)
        self.transcode_count_signal.emit(len([f for f in files_to_process if os.path.splitext(f)[1].upper() in ('.MP4', '.MOV', '.MKV', '.AVI')]))
        
        source_size = sum(os.path.getsize(f) for f in files_to_process)
        
        # Estimate transcode space if enabled
        transcode_extra = 0
        if self.transcode_settings:
            total_duration = 0
            for f in files_to_process:
                if os.path.splitext(f)[1].upper() in ('.MP4', '.MOV', '.MKV', '.AVI'):
                    try: total_duration += TranscodeEngine.get_duration(f)
                    except: pass
            codec = self.transcode_settings.get('v_codec', 'dnxhd')
            est_mbps = 100 if codec in ['dnxhd', 'prores_ks'] else 10
            transcode_extra = int(total_duration * est_mbps * 1024 * 1024)

        # Accurate Storage Check: Group by drive/mount
        drive_usage = {}
        for i, d in enumerate(active_dests):
            # Get the base existing directory to check storage
            p = d
            while not os.path.exists(p) and os.path.dirname(p) != p: p = os.path.dirname(p)
            try:
                if platform.system() == "Windows":
                    drive = os.path.splitdrive(os.path.abspath(p))[0].upper()
                else:
                    drive = os.stat(p).st_dev
                
                usage = source_size
                if i == 0: usage += transcode_extra # Transcodes usually go to first dest
                drive_usage[drive] = drive_usage.get(drive, 0) + usage
            except: pass

        for drive, needed in drive_usage.items():
            # Find a path associated with this drive to check free space
            check_path = self.dest_list[0] # fallback
            for d in active_dests:
                p = d
                while not os.path.exists(p) and os.path.dirname(p) != p: p = os.path.dirname(p)
                try:
                    if platform.system() == "Windows":
                        if os.path.splitdrive(os.path.abspath(p))[0].upper() == drive: check_path = p; break
                    else:
                        if os.stat(p).st_dev == drive: check_path = p; break
                except: continue
            
            free = self.get_free_space(check_path)
            if free < (needed + 104857600): # 100MB buffer
                self.finished_signal.emit(False, f"Insufficient storage on {drive}!"); return

        # Progress calculation: Copy (1.0) + Verify (1.0 per destination if enabled)
        # However, for UX simplicity, let's keep it based on total bytes to be processed
        # Total "work" bytes = source_size (for copy) + (source_size * len(active_dests) if verify_copy)
        total_work_bytes = source_size
        if self.verify_copy:
            total_work_bytes += (source_size * len(active_dests))
        
        bytes_done = 0
        last_time = time.time(); last_bytes = 0
        for idx, src in enumerate(files_to_process):
            if not self.is_running: break
            name = os.path.basename(src); sz = os.path.getsize(src); dest_paths = []
            for base in active_dests:
                td = base
                if self.sort_by_date: td = os.path.join(td, self.get_media_date(src))
                if self.camera_override != "Generic_Device": td = os.path.join(td, self.camera_override)
                td = os.path.join(td, self.get_mmt_category(name)); os.makedirs(td, exist_ok=True); dest_paths.append(os.path.join(td, name))
            
            try:
                h = xxhash.xxh64() if HAS_XXHASH else hashlib.md5()
                with open(src, 'rb') as fsrc:
                    handles = [open(d, 'wb') for d in dest_paths]
                    try:
                        while chunk := fsrc.read(4194304):
                            if not self.is_running: break
                            if self.verify_copy: h.update(chunk)
                            for hand in handles: hand.write(chunk)
                            bytes_done += len(chunk); now = time.time()
                            if now - last_time >= 0.5:
                                self.speed_signal.emit(f"{((bytes_done-last_bytes)/(now-last_time))/1048576:.1f} MB/s")
                                last_time = now; last_bytes = bytes_done
                            self.progress_signal.emit(int((bytes_done/total_work_bytes)*100))
                    finally:
                        for hand in handles: hand.close()
                for d in dest_paths: shutil.copystat(src, d)
                
                self.log_signal.emit(f"✔️ Copied: {name} (to {len(dest_paths)} drives)")

                # VERIFICATION PHASE
                current_hash = "N/A"
                if self.verify_copy and self.is_running:
                    self.status_signal.emit(f"Verifying {idx + 1}/{total_files}: {name}")
                    src_hash = h.hexdigest()
                    
                    all_verified = True
                    for d in dest_paths:
                        if not self.is_running: break
                        # Inline verification with progress
                        try:
                            dh = xxhash.xxh64() if HAS_XXHASH else hashlib.md5()
                            with open(d, 'rb') as f:
                                while chunk := f.read(4194304):
                                    if not self.is_running: break
                                    dh.update(chunk)
                                    bytes_done += len(chunk)
                                    self.progress_signal.emit(int((bytes_done/total_work_bytes)*100))
                            dest_hash = dh.hexdigest()
                        except: dest_hash = None

                        if src_hash != dest_hash:
                            all_verified = False
                            self.log_signal.emit(f"❌ VERIFY FAILED on: {d}")
                    
                    if all_verified:
                        self.log_signal.emit(f"    ↳ ✅ Verified ({'xxHash64' if HAS_XXHASH else 'MD5'})")
                        current_hash = src_hash
                    else:
                        current_hash = "FAILED"
                
                self.transfer_data.append({
                    'name': name,
                    'path': dest_paths[0],
                    'size': sz,
                    'hash': current_hash,
                    'status': "OK" if current_hash != "FAILED" else "VERIFY FAILED"
                })
                if name.upper().endswith(('.MP4', '.MOV', '.MKV', '.AVI')): self.file_ready_signal.emit(src, dest_paths[0], name)
            except Exception as e:
                self.log_signal.emit(f"❌ Error {name}: {e}")
        
        if not self.is_running: self.finished_signal.emit(False, "🚫 Operation Aborted")
        else: self.finished_signal.emit(True, "✅ Ingest Complete!")
    def stop(self): self.is_running = False
