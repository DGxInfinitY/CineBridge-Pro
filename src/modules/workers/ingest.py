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
    
    def __init__(self, source, dest_list, project_name, sort_by_date, skip_dupes, videos_only, camera_override, verify_copy, file_list=None):
        super().__init__(); self.source = source; self.dest_list = [d.strip() for d in dest_list if d.strip()]; self.project_name = project_name.strip(); self.sort_by_date = sort_by_date; self.skip_dupes = skip_dupes; self.videos_only = videos_only; self.camera_override = camera_override; self.verify_copy = verify_copy; self.file_list = file_list; self.is_running = True
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
        self.transcode_count_signal.emit(len([f for f in files_to_process if os.path.splitext(f)[1].upper() in ('.MP4', '.MOV', '.MKV', '.AVI')]))
        total_bytes = sum(os.path.getsize(f) for f in files_to_process); bytes_done = 0
        min_free = min(self.get_free_space(d) for d in active_dests)
        if min_free < (total_bytes + 104857600):
            self.finished_signal.emit(False, "Insufficient storage!"); return

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
                            self.progress_signal.emit(int((bytes_done/total_bytes)*100))
                    finally:
                        for hand in handles: hand.close()
                for d in dest_paths: shutil.copystat(src, d)
                res_h = h.hexdigest() if self.verify_copy else "N/A"
                self.transfer_data.append({'name': name, 'path': dest_paths[0], 'size': sz, 'hash': res_h, 'status': "OK"})
                if name.upper().endswith(('.MP4', '.MOV', '.MKV', '.AVI')): self.file_ready_signal.emit(src, dest_paths[0], name)
            except: pass
        self.finished_signal.emit(True, "✅ Ingest Complete!")
    def stop(self): self.is_running = False
