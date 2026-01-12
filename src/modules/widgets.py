import os
import sys
import json
import platform
import subprocess
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
    QFileDialog, QTextEdit, QMessageBox, QCheckBox, QGroupBox, QComboBox, 
    QFrame, QFormLayout, QDialog, QToolButton, QRadioButton, QButtonGroup, 
    QGridLayout, QInputDialog, QTableWidget, QTableWidgetItem, QHeaderView,
    QSlider, QStyle, QSizePolicy
)
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QIcon, QPixmap, QPalette
from PyQt6.QtCore import Qt, QSize, QSettings, QUrl

try:
    from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
    from PyQt6.QtMultimediaWidgets import QVideoWidget
    HAS_MULTIMEDIA = True
except ImportError:
    HAS_MULTIMEDIA = False

# Internal Module Imports
from .config import DEBUG_MODE, AppConfig, AppLogger, debug_log, info_log, error_log
from .utils import (
    EnvUtils, DependencyManager, PresetManager, MediaInfoExtractor
)

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

        # Overlays Section
        self.overlay_group = QGroupBox("Visual Overlays (Burn-in)"); overlay_lay = QGridLayout(); self.overlay_group.setLayout(overlay_lay)
        self.chk_burn_file = QCheckBox("Burn Filename"); self.chk_burn_tc = QCheckBox("Burn Timecode")
        self.inp_watermark = QLineEdit(); self.inp_watermark.setPlaceholderText("Watermark Text (Optional)")
        overlay_lay.addWidget(self.chk_burn_file, 0, 0); overlay_lay.addWidget(self.chk_burn_tc, 0, 1)
        overlay_lay.addWidget(QLabel("Watermark:"), 1, 0); overlay_lay.addWidget(self.inp_watermark, 1, 1)
        self.layout.addWidget(self.overlay_group)

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
            self.chk_burn_file.setChecked(data.get('burn_file', False))
            self.chk_burn_tc.setChecked(data.get('burn_tc', False))
            self.inp_watermark.setText(data.get('watermark', ""))
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
            "audio_fix": self.chk_audio_fix.isChecked(),
            "burn_file": self.chk_burn_file.isChecked(),
            "burn_tc": self.chk_burn_tc.isChecked(),
            "watermark": self.inp_watermark.text().strip()
        }
        if self.lut_path.text().strip(): settings["lut_path"] = self.lut_path.text().strip()
        return settings
    def is_gpu_enabled(self): return self.chk_gpu.isChecked()
    def set_gpu_checked(self, checked): self.chk_gpu.blockSignals(True); self.chk_gpu.setChecked(checked); self.chk_gpu.blockSignals(False)

class JobReportDialog(QDialog):
    def __init__(self, title, report_text, parent=None):
        super().__init__(parent); self.setWindowTitle(title); self.setMinimumWidth(500); self.resize(600, 400); layout = QVBoxLayout()
        
        # Theme Polish
        is_dark = self.palette().color(QPalette.ColorRole.Window).lightness() < 128
        bg_color = "#2b2b2b" if is_dark else "#ffffff"
        text_color = "#e0e0e0" if is_dark else "#333333"
        
        self.text_edit = QTextEdit(); self.text_edit.setReadOnly(True)
        self.text_edit.setStyleSheet(f"background-color: {bg_color}; color: {text_color}; border: 1px solid #555;")
        
        self.text_edit.setHtml(f"<div style='font-family: Consolas, monospace; font-size: 13px; padding: 10px; color: {text_color};'>{report_text}</div>")
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
        if "ffmpeg_custom_path" in self.settings.allKeys(): report += "<b style='color: #3498DB;'>[CUSTOM OVERRIDE ACTIVE]</b><br>"
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
        
        target_encoders = ["h264_nvenc", "hevc_nvenc", "h264_qsv", "hevc_qsv", "h264_vaapi", "hevc_vaapi", "h264_videotoolbox", "hevc_videotoolbox"]
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

        feat_group = QGroupBox("Experimental / Pro Features"); feat_lay = QVBoxLayout(); feat_group.setLayout(feat_lay)
        
        # Watch Folder Toggle
        self.chk_watch_feat = QCheckBox("Enable Watch Folder Service")
        self.chk_watch_feat.setChecked(parent.settings.value("feature_watch_folder", False, type=bool))
        self.chk_watch_feat.toggled.connect(parent.update_feature_visibility)
        feat_lay.addWidget(self.chk_watch_feat)
        feat_lay.addWidget(QLabel("<small><i>Automates proxy generation for any files dropped into a specific folder.</i></small>"))
        
        # Burn-in Toggle
        self.chk_burn_feat = QCheckBox("Enable Burn-in Tools")
        self.chk_burn_feat.setChecked(parent.settings.value("feature_burn_in", False, type=bool))
        self.chk_burn_feat.toggled.connect(parent.update_feature_visibility)
        feat_lay.addWidget(self.chk_burn_feat)
        feat_lay.addWidget(QLabel("<small><i>Adds filename, timecode, and watermark overlays to transcoded media.</i></small>"))
        
        layout.addWidget(feat_group)

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
        version = QLabel("v4.16.4 (Dev)"); version.setStyleSheet("font-size: 14px; color: #888;"); version.setAlignment(Qt.AlignmentFlag.AlignCenter); layout.addWidget(version)
        desc = QLabel("The Linux DIT & Post-Production Suite.\nSolving the 'Resolve on Linux' problem."); desc.setWordWrap(True); desc.setStyleSheet("font-size: 13px;"); desc.setAlignment(Qt.AlignmentFlag.AlignCenter); layout.addWidget(desc)
        credits = QLabel("<b>Developed by:</b><br>Donovan Goodwin<br>(with Gemini AI)"); credits.setStyleSheet("font-size: 13px;"); credits.setAlignment(Qt.AlignmentFlag.AlignCenter); layout.addWidget(credits)
        links = QLabel('<a href="mailto:ddg2goodwin@gmail.com" style="color: #3498DB;">ddg2goodwin@gmail.com</a><br><br><a href="https://github.com/DGxInfinitY" style="color: #3498DB;">GitHub: DGxInfinitY</a>'); links.setOpenExternalLinks(True); links.setAlignment(Qt.AlignmentFlag.AlignCenter); layout.addWidget(links)
        layout.addStretch(); btn_box = QHBoxLayout(); ok_btn = QPushButton("Close"); ok_btn.setFixedWidth(100); ok_btn.clicked.connect(self.accept); btn_box.addStretch(); btn_box.addWidget(ok_btn); btn_box.addStretch(); layout.addLayout(btn_box); self.setLayout(layout)

class VideoPreviewDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Preview")
        self.resize(900, 600)
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        self.setLayout(self.layout)
        
        if not HAS_MULTIMEDIA:
            self.layout.addWidget(QLabel("Video Preview not available.\nMissing 'PyQt6.QtMultimedia' module.", alignment=Qt.AlignmentFlag.AlignCenter))
            return

        # Player Setup
        self.player = QMediaPlayer()
        self.audio = QAudioOutput()
        self.player.setAudioOutput(self.audio)
        self.audio.setVolume(1.0)
        
        self.video_widget = QVideoWidget()
        self.video_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.player.setVideoOutput(self.video_widget)
        self.layout.addWidget(self.video_widget)
        
        # Controls Container
        ctrl_frame = QFrame()
        ctrl_frame.setStyleSheet("background-color: #222; border-top: 1px solid #444;")
        ctrl_frame.setFixedHeight(50)
        ctrl_layout = QHBoxLayout()
        ctrl_layout.setContentsMargins(10, 5, 10, 5)
        ctrl_frame.setLayout(ctrl_layout)
        
        # Play/Pause
        self.play_btn = QToolButton()
        self.play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.play_btn.clicked.connect(self.toggle_play)
        ctrl_layout.addWidget(self.play_btn)
        
        # Time
        self.lbl_curr = QLabel("00:00")
        self.lbl_curr.setStyleSheet("color: #ccc; font-family: monospace;")
        ctrl_layout.addWidget(self.lbl_curr)
        
        # Seek Slider
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.sliderMoved.connect(self.set_position)
        ctrl_layout.addWidget(self.slider)
        
        # Total Time
        self.lbl_total = QLabel("00:00")
        self.lbl_total.setStyleSheet("color: #ccc; font-family: monospace;")
        ctrl_layout.addWidget(self.lbl_total)
        
        # Spacer
        ctrl_layout.addSpacing(10)
        
        # Volume
        vol_icon = QLabel(); vol_icon.setPixmap(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaVolume).pixmap(16,16))
        ctrl_layout.addWidget(vol_icon)
        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setFixedWidth(80)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(100)
        self.vol_slider.valueChanged.connect(lambda v: self.audio.setVolume(v / 100))
        ctrl_layout.addWidget(self.vol_slider)
        
        # Fullscreen
        self.fs_btn = QToolButton()
        self.fs_btn.setText("⛶") 
        self.fs_btn.setToolTip("Toggle Fullscreen")
        self.fs_btn.clicked.connect(self.toggle_fullscreen)
        ctrl_layout.addWidget(self.fs_btn)
        
        self.layout.addWidget(ctrl_frame)
        
        # Connections
        self.player.positionChanged.connect(self.position_changed)
        self.player.durationChanged.connect(self.duration_changed)
        self.player.mediaStatusChanged.connect(self.status_changed)
        self.player.errorOccurred.connect(self.handle_errors)

    def load_video(self, video_path):
        if not HAS_MULTIMEDIA: return
        self.setWindowTitle(f"Preview: {os.path.basename(video_path)}")
        self.play_btn.setEnabled(True)
        self.play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))
        self.player.setSource(QUrl.fromLocalFile(video_path))
        self.player.play()

    def toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
            self.play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        else:
            self.player.play()
            self.play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))

    def toggle_fullscreen(self):
        if self.isFullScreen(): self.showNormal()
        else: self.showFullScreen()

    def set_position(self, position): self.player.setPosition(position)

    def position_changed(self, position):
        if not self.slider.isSliderDown(): self.slider.setValue(position)
        self.update_time_label(position, self.player.duration())

    def duration_changed(self, duration):
        self.slider.setRange(0, duration)
        self.update_time_label(self.player.position(), duration)

    def update_time_label(self, current_ms, total_ms):
        def fmt(ms): return f"{(ms//1000)//60:02}:{(ms//1000)%60:02}"
        self.lbl_curr.setText(fmt(current_ms))
        self.lbl_total.setText(fmt(total_ms))
        
    def status_changed(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))

    def handle_errors(self):
        self.play_btn.setEnabled(False)
        self.lbl_curr.setText("Error")

    def closeEvent(self, event):
        if HAS_MULTIMEDIA:
            self.player.pause() # Just pause, keep pipeline alive for reuse
        event.accept()
