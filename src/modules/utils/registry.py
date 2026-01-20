import os
import platform
import subprocess
import re
from PyQt6.QtCore import QSettings
from .common import EnvUtils, debug_log
from .engine import MediaInfoExtractor

class DeviceRegistry:
    VIDEO_EXTS = {'.MP4', '.MOV', '.MKV', '.INSV', '.360', '.AVI', '.MXF', '.CRM', '.BRAW', '.VR'}
    PHOTO_EXTS = {'.JPG', '.JPEG', '.PNG', '.ARW', '.CR2', '.CR3', '.DNG', '.GPR', '.HEIC', '.INSP', '.RW2'}
    AUDIO_EXTS = {'.WAV', '.MP3', '.AAC'}
    MISC_EXTS = {'.SRT', '.LRV', '.THM', '.XML', '.BIM', '.RSV', '.AAE', '.LOG'}

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
            "roots": [], 
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
        "DJI Device": { # Renamed from DJI Drone/Osmo for generic catch
            "signatures": ["DJI", "100MEDIA", "DJI_001"],
            "roots": ["DCIM/100MEDIA", "DCIM/101MEDIA", "DCIM/DJI_001"],
            "exts": {'.MP4', '.MOV', '.DNG', '.JPG', '.SRT'}
        },
        "Insta360": {
            "signatures": ["Insta360"],
            "roots": ["DCIM/Camera01", "DCIM/FileGroup01"],
            "exts": {'.INSV', '.INSP', '.LOG', '.LRV'}
        },
        "Panasonic Lumix": {
            "signatures": ["LUMIX", "100_PANA"],
            "roots": ["DCIM/100_PANA", "PRIVATE/AVCHD/BDMV/STREAM"],
            "exts": {'.MOV', '.MP4', '.RW2'}
        }
    }

    DJI_MODELS = {
        "FC8436": "DJI Neo 2", # Hypothetical ID
        "FC8284": "DJI Avata 2",
        "FC3582": "DJI Mini 3 Pro",
        "FC848": "DJI Air 3",
        "OT-210": "DJI Action 2",
        "AC003": "DJI Osmo Action 3",
        "AC004": "DJI Osmo Action 4",
        "AC005": "DJI Action 5 Pro", # Hypothetical
        "AC005PRO": "DJI Action 5 Pro"
    }
    
    _OVERRIDES = None

    @staticmethod
    def load_overrides():
        if DeviceRegistry._OVERRIDES is None:
            s = QSettings("CineBridge", "CineBridgePro")
            DeviceRegistry._OVERRIDES = s.value("device_overrides", {}, type=dict)
        return DeviceRegistry._OVERRIDES

    @staticmethod
    def save_override(key, name):
        if not key: return
        DeviceRegistry.load_overrides()
        DeviceRegistry._OVERRIDES[key] = name
        s = QSettings("CineBridge", "CineBridgePro")
        s.setValue("device_overrides", DeviceRegistry._OVERRIDES)
        debug_log(f"DeviceRegistry: Saved override '{key}' -> '{name}'")

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
        DeviceRegistry.load_overrides()
        
        # Check direct path override first
        if mount_point in DeviceRegistry._OVERRIDES:
            debug_log(f"DeviceRegistry: Found override for path {mount_point}")
            return DeviceRegistry._OVERRIDES[mount_point], mount_point, None, mount_point

        root_items = DeviceRegistry.safe_list_dir(mount_point)
        if not root_items: return "Generic Storage", mount_point, None, None
        best_match = None; best_score = 0; best_root = mount_point; best_exts = None; detected_id = None

        def check_structure(base_path, pattern):
            if not pattern or pattern == ".": return None
            curr = base_path; parts = pattern.split('/')
            for part in parts:
                if not part or part == ".": continue
                found_next = None
                try:
                    items = [os.path.basename(p) for p in DeviceRegistry.safe_list_dir(curr)]
                    for item in items:
                        if part == "*" or item.lower() == part.lower(): found_next = os.path.join(curr, item); break
                        if "GOPRO" in part and re.match(r"\d{3}GOPRO", item.upper()): found_next = os.path.join(curr, item); break
                except: pass
                if found_next: curr = found_next
                else: return None
            return curr

        for name, profile in DeviceRegistry.PROFILES.items():
            score = 0; detected_root = None
            for root_hint in profile['roots']:
                if not root_hint or root_hint == ".": continue
                
                # Check for GoPro specific folders (DCIM/100GOPRO, etc)
                dcim = check_structure(mount_point, "DCIM")
                if "GOPRO" in name.upper() and dcim:
                    try:
                        for sub in DeviceRegistry.safe_list_dir(dcim):
                            base_sub = os.path.basename(sub).upper()
                            if "GOPRO" in base_sub or re.match(r"\d{3}GOPRO", base_sub):
                                detected_root = sub; score += 100; break
                    except: pass
                
                if score < 100:
                    found_path = check_structure(mount_point, root_hint)
                    if found_path: detected_root = found_path; score += 100; break
            if score < 100:
                for sig in profile['signatures']:
                    for item in root_items:
                        if sig.lower() in os.path.basename(item).lower(): score += 20
            for sig in profile['signatures']:
                for hint in usb_hints:
                    if sig.lower() in hint.lower(): score += 5
            if score > best_score: best_score = score; best_match = name; best_root = detected_root if detected_root else mount_point; best_exts = profile['exts']

        # Metadata Refinement for DJI
        if best_match == "DJI Device":
            try:
                # Find a sample video file
                sample_file = None
                items = DeviceRegistry.safe_list_dir(best_root)
                for item in items:
                    if os.path.splitext(item)[1].upper() in {'.MP4', '.MOV'}:
                        sample_file = item; break
                
                if sample_file:
                    meta = MediaInfoExtractor.get_device_metadata(sample_file)
                    model = meta.get('model')
                    if model:
                        detected_id = model
                        # 1. Check Model Override
                        if model in DeviceRegistry._OVERRIDES:
                            best_match = DeviceRegistry._OVERRIDES[model]
                        # 2. Check Known Models
                        elif model in DeviceRegistry.DJI_MODELS:
                            best_match = DeviceRegistry.DJI_MODELS[model]
                        # 3. Smart Fallback
                        else:
                            clean_model = model.strip()
                            if "DJI" in clean_model.upper(): best_match = clean_model
                            else: best_match = f"DJI {clean_model}"
            except Exception as e: debug_log(f"DJI Metadata check failed: {e}")

        if best_score >= 20: return best_match, best_root, best_exts, detected_id
        internal = check_structure(mount_point, "Internal shared storage") or check_structure(mount_point, "Internal Storage")
        if internal:
            dcim = check_structure(internal, "DCIM")
            if dcim:
                cam = check_structure(dcim, "Camera")
                if cam: return "Android/Phone", cam, {'.MP4', '.JPG', '.JPEG', '.DNG', '.HEIC'}, None
        return "Generic Storage", mount_point, None, None

class DriveDetector:
    IGNORED_KEYWORDS = ["boot", "recovery", "snap", "loop", "var", "tmp", "sys"]
    @staticmethod
    def is_network_mount(path):
        p = path.lower()
        if "mtp" in p or "gphoto" in p or "usb" in p: return False 
        for sig in ["smb", "sftp", "ftp", "dav", "afp", "nfs", "ssh"]:
            if sig in p: return True
        return False
    @staticmethod
    def safe_list_dir(path, timeout=5): return DeviceRegistry.safe_list_dir(path, timeout)
    @staticmethod
    def safe_exists(path): return os.path.exists(path)
    @staticmethod
    def get_potential_mounts():
        mounts = []
        user = os.environ.get('USER') or os.environ.get('USERNAME')
        system = platform.system()
        if system == "Linux":
            search_roots = [f"/media/{user}", f"/run/media/{user}"]
            gvfs = f"/run/user/{os.getuid()}/gvfs"
            if os.path.exists(gvfs): search_roots.append(gvfs)
            for root in search_roots:
                if os.path.exists(root):
                    try:
                        with os.scandir(root) as it:
                            for entry in it:
                                if entry.is_dir() and not any(x in entry.name.lower() for x in DriveDetector.IGNORED_KEYWORDS):
                                    if not DriveDetector.is_network_mount(entry.path): mounts.append(entry.path)
                    except: pass
        elif system == "Darwin" and os.path.exists("/Volumes"):
            with os.scandir("/Volumes") as it:
                for entry in it:
                    if entry.is_dir() and not entry.is_symlink(): mounts.append(entry.path)
        elif system == "Windows":
            import string
            for d in string.ascii_uppercase:
                p = f"{d}:\\"
                if os.path.exists(p) and d != "C": mounts.append(p)
        return mounts
    @staticmethod
    def get_usb_hardware_hints():
        hints = set()
        if platform.system() == "Linux":
            try:
                res = subprocess.run(['lsusb'], capture_output=True, text=True, timeout=2, env=EnvUtils.get_clean_env())
                for line in res.stdout.splitlines():
                    parts = line.split(":", 2)
                    if len(parts) > 2:
                        desc = parts[2].strip()
                        if "root hub" not in desc.lower() and "linux foundation" not in desc.lower(): hints.add(desc)
            except: pass
        return hints
