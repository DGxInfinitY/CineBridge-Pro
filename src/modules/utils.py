import os
import sys
import shutil
import re
import platform
import subprocess
import hashlib
import json
import xml.etree.ElementTree as ET
from datetime import datetime
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QTextDocument, QPageLayout, QPageSize
from PyQt6.QtPrintSupport import QPrinter
from PyQt6.QtCore import QSettings, QMarginsF

try:
    import xxhash
    HAS_XXHASH = True
except ImportError:
    HAS_XXHASH = False

# Import Config
from .config import AppConfig, AppLogger, debug_log, info_log, error_log

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
        
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # Fallback to looking in src/bin (where cinebridge.py was)
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
    def get_binary_path(binary_name):
        # Similar logic for ffprobe
        settings = QSettings("CineBridgePro", "Config")
        
        if hasattr(sys, '_MEIPASS'):
            bundle_path = os.path.join(sys._MEIPASS, binary_name)
            if platform.system() == "Windows": bundle_path += ".exe"
            if os.path.exists(bundle_path): return bundle_path
        
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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
            if "cuda" in output and "h264_nvenc" in enc_out: 
                debug_log("HW: Detected NVIDIA CUDA/NVENC")
                result = "cuda"
            elif "qsv" in output and "h264_qsv" in enc_out: 
                debug_log("HW: Detected Intel QuickSync")
                result = "qsv"
            elif "vaapi" in output and "h264_vaapi" in enc_out: 
                debug_log("HW: Detected Linux VAAPI")
                result = "vaapi"
            
            DependencyManager._hw_cache = result
            return result
        except Exception as e:
            debug_log(f"HW Detection Error: {e}")
        return None

class TranscodeEngine:
    @staticmethod
    def get_font_path():
        """Returns a system font path for drawtext."""
        paths = []
        if platform.system() == "Windows":
            paths = ["C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/Tahoma.ttf"]
        elif platform.system() == "Darwin":
            paths = ["/Library/Fonts/Arial.ttf", "/System/Library/Fonts/Helvetica.ttc"]
        else: # Linux
            paths = ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/TTF/DejaVuSans.ttf"]
        
        for p in paths:
            if os.path.exists(p): return p.replace('\\', '/')
        return None

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
        
        vf_chain = []
        if settings.get("lut_path"):
            lut_file = settings['lut_path'].replace('\\', '/').replace(':', '\\:').replace("'", "'\\''")
            vf_chain.append(f"lut3d='{lut_file}'")
        
        font = TranscodeEngine.get_font_path()
        if font:
            if settings.get("burn_file"):
                vf_chain.append(f"drawtext=text='%{{filename}}':x=10:y=H-th-10:fontfile='{font}':fontcolor=white:fontsize=24:box=1:boxcolor=black@0.5")
            if settings.get("burn_tc"):
                vf_chain.append(f"drawtext=text='%{{pts\\:hms}}':x=W-tw-10:y=H-th-10:fontfile='{font}':fontcolor=white:fontsize=24:box=1:boxcolor=black@0.5")
            if settings.get("watermark"):
                txt = settings['watermark'].replace("'", "")
                vf_chain.append(f"drawtext=text='{txt}':x=(W-tw)/2:y=10:fontfile='{font}':fontcolor=white@0.3:fontsize=32")

        if vf_chain:
            cmd.extend(['-vf', ','.join(vf_chain)])

        if v_codec in ['dnxhd', 'prores_ks']:
            cmd.extend(['-c:v', v_codec, '-profile:v', v_profile])
            if v_codec == 'dnxhd': cmd.extend(['-pix_fmt', 'yuv422p'])
        elif v_codec in ['libx264', 'libx265']:
            if hw_method == "cuda" and v_codec == 'libx264': cmd.extend(['-c:v', 'h264_nvenc', '-preset', 'fast'])
            elif hw_method == "cuda" and v_codec == 'libx265': cmd.extend(['-c:v', 'hevc_nvenc', '-preset', 'fast'])
            elif hw_method == "qsv" and v_codec == 'libx264': cmd.extend(['-c:v', 'h264_qsv', '-preset', 'fast'])
            elif hw_method == "qsv" and v_codec == 'libx265': cmd.extend(['-c:v', 'hevc_qsv', '-preset', 'fast'])
            elif hw_method == "vaapi" and v_codec == 'libx264': cmd.extend(['-c:v', 'h264_vaapi'])
            elif hw_method == "vaapi" and v_codec == 'libx265': cmd.extend(['-c:v', 'hevc_vaapi'])
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
    def is_edit_friendly(input_path, target_codec_family):
        """Checks if the file is already in the target codec family (dnxhd/prores)."""
        # Normalize target family (e.g. 'prores_ks' -> 'prores')
        if 'prores' in target_codec_family: target_codec_family = 'prores'
        
        # Quick extension check first (optimization)
        ext = os.path.splitext(input_path)[1].lower()
        if target_codec_family == 'prores' and ext != '.mov': return False
        if target_codec_family == 'dnxhd' and ext not in ['.mov', '.mxf']: return False

        info = MediaInfoExtractor.get_info(input_path)
        if "video_streams" in info and info["video_streams"]:
            codec = info["video_streams"][0]['codec'].lower()
            if target_codec_family == 'prores' and 'prores' in codec: return True
            if target_codec_family == 'dnxhd' and 'dnxhd' in codec: return True
        return False

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

class ReportGenerator:
    @staticmethod
    def generate_pdf(dest_path, file_data_list, project_name="Unnamed Project", thumbnails=None):
        """Generates a professional DIT transfer report in PDF format."""
        is_visual = thumbnails is not None
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: 'Segoe UI', sans-serif; margin: 30px; }}
                h1 {{ color: #2980B9; border-bottom: 2px solid #2980B9; padding-bottom: 10px; }}
                .header-info {{ margin-bottom: 20px; font-size: 14px; }}
                table {{ width: 100%; border-collapse: collapse; }}
                th, td {{ border: 1px solid #eee; padding: 8px; text-align: left; font-size: 11px; vertical-align: middle; }}
                th {{ background-color: #f8f9fa; color: #2980B9; font-weight: bold; }}
                tr:nth-child(even) {{ background-color: #fafafa; }}
                .thumb {{ width: 120px; height: 68px; background-color: #000; display: block; }}
                .footer {{ margin-top: 40px; font-size: 10px; color: #aaa; text-align: center; border-top: 1px solid #eee; padding-top: 10px; }}
            </style>
        </head>
        <body>
            <h1>CineBridge Pro | Transfer Report</h1>
            <div class="header-info">
                <p><b>Project:</b> {project_name}</p>
                <p><b>Completion Date:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p><b>Total Files:</b> {len(file_data_list)}</p>
            </div>
            <table>
                <thead>
                    <tr>
                        {"<th>Preview</th>" if is_visual else ""}
                        <th>Filename</th>
                        <th>Size (MB)</th>
                        <th>Checksum (Hash)</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
        """
        total_bytes = 0
        for f in file_data_list:
            size_mb = f.get('size', 0) / (1024*1024); total_bytes += f.get('size', 0)
            thumb_html = ""
            if is_visual:
                b64 = thumbnails.get(f['name'], "")
                if b64: thumb_html = f'<td><img src="data:image/png;base64,{b64}" class="thumb"></td>'
                else: thumb_html = '<td><div class="thumb" style="background:#333;"></div></td>'
            
            html += f"<tr>{thumb_html}<td>{f['name']}</td><td>{size_mb:.2f}</td><td><code>{f.get('hash', 'N/A')}</code></td><td>✅ OK</td></tr>"
        
        html += f"""
                </tbody>
            </table>
            <p><b>Summary:</b> Total Data {total_bytes/(1024**3):.2f} GB transferred and verified.</p>
            <div class="footer">CineBridge Pro v4.16.5 (Dev) - Professional DIT & Post-Production Suite</div>
        </body>
        </html>
        """
        doc = QTextDocument(); doc.setHtml(html)
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(dest_path)
        printer.setPageLayout(QPageLayout(QPageSize(QPageSize.PageSizeId.A4), QPageLayout.Orientation.Portrait, QMarginsF(15, 15, 15, 15)))
        doc.print(printer)
        return dest_path

class MHLGenerator:
    @staticmethod
    def generate(dest_root, transfer_data, project_name="CineBridge_Pro"):
        """Generates an ASC-MHL compliant XML file for media integrity verification."""
        timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        root = ET.Element("hashlist", version="1.1")
        for f in transfer_data:
            if f.get('hash') == "N/A": continue
            hash_node = ET.SubElement(root, "hash")
            ET.SubElement(hash_node, "file").text = f['name']
            ET.SubElement(hash_node, "size").text = str(f['size'])
            hash_tag = "xxhash64" if HAS_XXHASH else "md5"
            ET.SubElement(hash_node, hash_tag).text = f['hash']
            ET.SubElement(hash_node, "hashdate").text = timestamp
        
        tree = ET.ElementTree(root)
        # ElementTree.indent is only available in Python 3.9+
        if hasattr(ET, 'indent'): ET.indent(tree, space="  ", level=0)
        
        mhl_filename = f"{project_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mhl"
        mhl_path = os.path.join(dest_root, mhl_filename)
        tree.write(mhl_path, encoding="utf-8", xml_declaration=True)
        return mhl_path

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

# =============================================================================
# NOTIFICATION SYSTEM
# =============================================================================
class SystemNotifier:
    @staticmethod
    def notify(title, message, icon="dialog-information"):
        """Triggers a cross-platform system notification. 
        Icon types: 'dialog-information', 'dialog-error', 'dialog-warning'
        """
        system = platform.system()
        try:
            if system == "Linux":
                # Use notify-send with specific hints/icons
                cmd = ['notify-send', '-a', 'CineBridge Pro', '-i', icon, title, message]
                if icon == "dialog-error": cmd.extend(['-u', 'critical'])
                subprocess.Popen(cmd)
                
                # Try to play a system sound if canberra-gtk-play is available
                try:
                    sound_id = "message" if icon == "dialog-information" else "dialog-error"
                    subprocess.Popen(['canberra-gtk-play', '-i', sound_id], stderr=subprocess.DEVNULL)
                except: 
                    if icon != "dialog-information": QApplication.beep()
            
            elif system == "Darwin":
# ...
            # Fallback beep for non-Linux if no specific sound played
            if system != "Linux":
                if icon == "dialog-error": QApplication.beep()
                elif icon == "dialog-information": QApplication.beep() # Re-add info beep
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
        "DJI Drone/Osmo": {
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
        
        # 1. Quick Check: Is it empty/inaccessible?
        root_items = DeviceRegistry.safe_list_dir(mount_point)
        if not root_items: 
            debug_log(f"Registry: {mount_point} is inaccessible or empty.")
            return "Generic Storage", mount_point, None

        # 2. Scoring System
        best_match = None
        best_score = 0
        best_root = mount_point
        best_exts = None

        def check_structure(base_path, pattern):
            """Checks if a folder structure exists. Supports regex-like patterns."""
            if not pattern or pattern == ".": return None # Safety Check
            
            curr = base_path
            parts = pattern.split('/')
            for part in parts:
                if not part or part == ".": continue
                
                found_next = None
                try:
                    items = [os.path.basename(p) for p in DeviceRegistry.safe_list_dir(curr)]
                    for item in items:
                        if part == "*": 
                            found_next = os.path.join(curr, item); break
                        
                        if item.lower() == part.lower():
                            found_next = os.path.join(curr, item); break
                        
                        # Special Case: GoPro '100GOPRO', '101GOPRO'
                        if "GOPRO" in part and re.match(r"\d{3}GOPRO", item.upper()):
                            found_next = os.path.join(curr, item); break
                            
                except: pass
                
                if found_next: curr = found_next
                else: return None
            return curr

        for name, profile in DeviceRegistry.PROFILES.items():
            score = 0
            detected_root = None

            # A. Structure Check (High Confidence)
            for root_hint in profile['roots']:
                if not root_hint or root_hint == ".": continue # skip generic roots
                
                if "100GOPRO" in root_hint: # Special handling for GoPro
                     dcim = check_structure(mount_point, "DCIM")
                     if dcim:
                         try:
                             for sub in DeviceRegistry.safe_list_dir(dcim):
                                 if re.match(r"\d{3}GOPRO", os.path.basename(sub).upper()):
                                     detected_root = sub; score += 100; break
                         except: pass
                else:
                    found_path = check_structure(mount_point, root_hint)
                    if found_path:
                        detected_root = found_path
                        score += 100
                        break
            
            # B. Signature Check (Medium Confidence) - ONLY if no structure found yet
            if score < 100:
                for sig in profile['signatures']:
                    for item in root_items:
                        base = os.path.basename(item)
                        if sig.lower() in base.lower():
                            debug_log(f"Registry: '{name}' signature '{sig}' found in file '{base}'")
                            score += 20
            
            # C. USB Hint Check (Low Confidence / Tie-Breaker)
            for sig in profile['signatures']:
                for hint in usb_hints:
                    if sig.lower() in hint.lower():
                        score += 5

            if score > best_score:
                best_score = score
                best_match = name
                best_root = detected_root if detected_root else mount_point
                best_exts = profile['exts']

        # threshold for acceptance
        if best_score >= 20:
             debug_log(f"Registry: Identified {best_match} (Score: {best_score})")
             return best_match, best_root, best_exts

        # 3. Android/Generic Fallback
        search_root = mount_point
        internal = check_structure(mount_point, "Internal shared storage")
        if not internal: internal = check_structure(mount_point, "Internal Storage")
        if internal: 
            debug_log(f"Registry: Found Android storage layer: {internal}")
            search_root = internal

        dcim = check_structure(search_root, "DCIM")
        if dcim:
             cam = check_structure(dcim, "Camera")
             if cam: 
                 debug_log("Registry: Identified Android Phone via DCIM/Camera")
                 return "Android/Phone", cam, {'.MP4', '.JPG', '.JPEG', '.DNG', '.HEIC'}
             
        debug_log(f"Registry: No specific profile match for {mount_point} (Best Score: {best_score}). Falling back to Generic.")
        return "Generic Storage", mount_point, None

class DriveDetector:
    IGNORED_KEYWORDS = ["boot", "recovery", "snap", "loop", "var", "tmp", "sys"]

    @staticmethod
    def is_network_mount(path):
        path_lower = path.lower()
        if "mtp" in path_lower or "gphoto" in path_lower or "usb" in path_lower: return False 
        network_sigs = ["smb", "sftp", "ftp", "dav", "afp", "nfs", "ssh"]
        for sig in network_sigs:
            if sig in path_lower: return True
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
                                    if not DriveDetector.is_network_mount(entry.path): mounts.append(entry.path)
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
