import os
import platform
import subprocess
import re
import json
from .common import DependencyManager, EnvUtils, debug_log, error_log

class TranscodeEngine:
    @staticmethod
    def get_font_path():
        paths = []
        if platform.system() == "Windows": paths = ["C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/Tahoma.ttf"]
        elif platform.system() == "Darwin": paths = ["/Library/Fonts/Arial.ttf", "/System/Library/Fonts/Helvetica.ttc"]
        else: paths = ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/TTF/DejaVuSans.ttf"]
        for p in paths:
            if os.path.exists(p): return p.replace('\\', '/')
        return None

    @staticmethod
    def build_command(input_path, output_path, settings, use_gpu=False):
        ffmpeg_bin = DependencyManager.get_ffmpeg_path()
        if not ffmpeg_bin: return None
        v_codec = settings.get('v_codec', 'dnxhd'); v_profile = settings.get('v_profile', 'dnxhr_hq'); a_codec = settings.get('a_codec', 'pcm_s16le')
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
            if settings.get("burn_file"): vf_chain.append(f"drawtext=text='%{{filename}}':x=10:y=H-th-10:fontfile='{font}':fontcolor=white:fontsize=24:box=1:boxcolor=black@0.5")
            if settings.get("burn_tc"): vf_chain.append(f"drawtext=text='%{{pts\\:hms}}':x=W-tw-10:y=H-th-10:fontfile='{font}':fontcolor=white:fontsize=24:box=1:boxcolor=black@0.5")
            if settings.get("watermark"):
                txt = settings['watermark'].replace("'", "")
                vf_chain.append(f"drawtext=text='{txt}':x=(W-tw)/2:y=10:fontfile='{font}':fontcolor=white@0.3:fontsize=32")
        if vf_chain: cmd.extend(['-vf', ','.join(vf_chain)])
        if v_codec in ['dnxhd', 'prores_ks']:
            cmd.extend(['-c:v', v_codec, '-profile:v', v_profile])
            if v_codec == 'dnxhd': cmd.extend(['-pix_fmt', 'yuv422p'])
        elif v_codec in ['libx264', 'libx265']:
            if hw_method == "cuda" and v_codec == 'libx264': cmd.extend(['-c:v', 'h264_nvenc', '-preset', 'fast'])
            elif hw_method == "cuda" and v_codec == 'libx265': cmd.extend(['-c:v', hevc_nvenc, '-preset', 'fast'])
            elif hw_method == "qsv" and v_codec == 'libx264': cmd.extend(['-c:v', 'h264_qsv', '-preset', 'fast'])
            elif hw_method == "qsv" and v_codec == 'libx265': cmd.extend(['-c:v', 'hevc_qsv', '-preset', 'fast'])
            elif hw_method == "vaapi" and v_codec == 'libx264': cmd.extend(['-c:v', 'h264_vaapi'])
            elif hw_method == "vaapi" and v_codec == 'libx265': cmd.extend(['-c:v', 'hevc_vaapi'])
            else:
                cmd.extend(['-c:v', v_codec, '-preset', 'fast', '-crf', '18'])
                if v_codec == 'libx264': cmd.extend(['-pix_fmt', 'yuv420p'])
        if a_codec == 'pcm_s16le': cmd.extend(['-c:a', 'pcm_s16le', '-ar', '48000'])
        elif a_codec == 'aac': cmd.extend(['-c:a', 'aac', '-b:a', '320k', '-ar', '48000'])
        if settings.get('audio_fix'): cmd.extend(['-af', 'aresample=async=1:min_comp=0.01:first_pts=0'])
        cmd.append(output_path); return cmd

    @staticmethod
    def get_duration(input_path):
        ffprobe = DependencyManager.get_binary_path("ffprobe")
        if not ffprobe: return 0
        try:
            cmd = [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", input_path]
            res = subprocess.run(cmd, capture_output=True, text=True, env=EnvUtils.get_clean_env())
            return float(res.stdout.strip())
        except: return 0

    @staticmethod
    def is_edit_friendly(input_path, target_codec_family):
        if 'prores' in target_codec_family: target_codec_family = 'prores'
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
        progress = 0; status_str = ""
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
            res = subprocess.run(cmd, capture_output=True, text=True, env=EnvUtils.get_clean_env())
            if res.returncode != 0: return {"error": "Failed to read file"}
            data = json.loads(res.stdout)
            info = {"filename": os.path.basename(input_path), "container": data.get("format", {}).get("format_long_name", "Unknown"), "size_mb": float(data.get("format", {}).get("size", 0)) / (1024*1024), "duration": float(data.get("format", {}).get("duration", 0)), "video_streams": [], "audio_streams": []}
            for stream in data.get("streams", []):
                if stream["codec_type"] == "video":
                    v_info = {"codec": stream.get("codec_name", "Unknown"), "profile": stream.get("profile", ""), "resolution": f"{stream.get('width')}x{stream.get('height')}", "fps": stream.get("r_frame_rate", "0/0"), "pix_fmt": stream.get("pix_fmt", ""), "bitrate": int(stream.get("bit_rate", 0)) / 1000 if stream.get("bit_rate") else 0}
                    info["video_streams"].append(v_info)
                elif stream["codec_type"] == "audio":
                    a_info = {"codec": stream.get("codec_name", "Unknown"), "channels": stream.get("channels", 0), "sample_rate": stream.get("sample_rate", 0), "language": stream.get("tags", {}).get("language", "und")}
                    info["audio_streams"].append(a_info)
            return info
        except Exception as e: return {"error": str(e)}