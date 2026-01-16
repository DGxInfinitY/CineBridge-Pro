import os
import platform
import json
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
    QFileDialog, QCheckBox, QGroupBox, QComboBox, QFrame, QFormLayout, 
    QToolButton, QGridLayout, QInputDialog, QMessageBox, QListView
)
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QStandardItemModel, QStandardItem
from PyQt6.QtCore import Qt, pyqtSignal, QEvent
from ..utils import PresetManager, MediaInfoExtractor

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
        self.chk_gpu = QCheckBox("Use Hardware Acceleration (if available)"); self.chk_gpu.setStyleSheet("font-weight: bold; color: #3498DB;")
        self.chk_gpu.setToolTip("Enables hardware acceleration (NVENC/QSV/VAAPI) for significantly faster transcoding.")
        self.layout.addWidget(self.chk_gpu)
        top_row = QHBoxLayout(); top_row.addWidget(QLabel("Preset:")); self.preset_combo = QComboBox(); self.init_presets() 
        self.preset_combo.setToolTip("Choose from optimized industry-standard presets or create your own.")
        self.preset_combo.currentIndexChanged.connect(self.apply_preset); top_row.addWidget(self.preset_combo, 1)
        
        # Preset Management Buttons
        self.btn_save_preset = QToolButton(); self.btn_save_preset.setText("💾"); self.btn_save_preset.setToolTip("Save Current as Preset"); self.btn_save_preset.clicked.connect(self.save_custom_preset)
        self.btn_import_preset = QToolButton(); self.btn_import_preset.setText("📥"); self.btn_import_preset.setToolTip("Import Preset File"); self.btn_import_preset.clicked.connect(self.import_preset_file)
        self.btn_export_preset = QToolButton(); self.btn_export_preset.setText("📤"); self.btn_export_preset.setToolTip("Export Selected Preset"); self.btn_export_preset.clicked.connect(self.export_preset_file)
        self.btn_del_preset = QToolButton(); self.btn_del_preset.setText("🗑️"); self.btn_del_preset.setToolTip("Delete Selected Preset"); self.btn_del_preset.clicked.connect(self.delete_current_preset)
        top_row.addWidget(self.btn_save_preset); top_row.addWidget(self.btn_import_preset); top_row.addWidget(self.btn_export_preset); top_row.addWidget(self.btn_del_preset)
        self.layout.addLayout(top_row)
        
        lut_lay = QHBoxLayout(); self.lut_path = QLineEdit(); self.lut_path.setPlaceholderText("Select 3D LUT (.cube) - Optional")
        self.lut_path.setToolTip("Apply a 3D LUT (.cube) during transcoding to see your creative look on proxies.")
        self.btn_lut = QPushButton("Browse LUT"); self.btn_lut.clicked.connect(self.browse_lut)
        self.btn_clr_lut = QPushButton("X"); self.btn_clr_lut.setFixedWidth(30); self.btn_clr_lut.clicked.connect(self.lut_path.clear)
        lut_lay.addWidget(QLabel("Look:")); lut_lay.addWidget(self.lut_path); lut_lay.addWidget(self.btn_lut); lut_lay.addWidget(self.btn_clr_lut)
        self.layout.addLayout(lut_lay)

        # Overlays Section
        self.overlay_group = QGroupBox("Visual Overlays (Burn-in)"); overlay_lay = QGridLayout(); self.overlay_group.setLayout(overlay_lay)
        self.chk_burn_file = QCheckBox("Burn Filename"); self.chk_burn_file.setToolTip("Overlay the source filename on the bottom left of the video.")
        self.chk_burn_tc = QCheckBox("Burn Timecode"); self.chk_burn_tc.setToolTip("Overlay the timecode or duration on the bottom right of the video.")
        self.inp_watermark = QLineEdit(); self.inp_watermark.setPlaceholderText("Watermark Text (Optional)"); self.inp_watermark.setToolTip("Add a custom text watermark to the center of the frame.")
        overlay_lay.addWidget(self.chk_burn_file, 0, 0); overlay_lay.addWidget(self.chk_burn_tc, 0, 1)
        overlay_lay.addWidget(QLabel("Watermark:"), 1, 0); overlay_lay.addWidget(self.inp_watermark, 1, 1)
        self.layout.addWidget(self.overlay_group)

        self.advanced_frame = QFrame(); adv_layout = QFormLayout(); self.advanced_frame.setLayout(adv_layout)
        self.codec_combo = QComboBox(); self.init_codecs(); self.codec_combo.currentIndexChanged.connect(self.update_profiles)
        self.codec_combo.setToolTip("Select the video encoding engine.")
        self.profile_combo = QComboBox(); self.profile_combo.setToolTip("Select the specific quality profile for the chosen codec.")
        self.audio_combo = QComboBox(); self.audio_combo.addItems(["PCM (Uncompressed)", "AAC (Compressed)"]); self.audio_combo.setToolTip("Select the audio encoding format.")
        
        self.chk_audio_fix = QCheckBox("Fix Audio Drift (48kHz)"); self.chk_audio_fix.setToolTip("Attempts to correct audio drift and normalizes to 48kHz.")
        
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
        self.custom_presets = PresetManager.list_presets()
        if self.custom_presets:
            self.preset_combo.insertSeparator(self.preset_combo.count())
            for name in sorted(self.custom_presets.keys()): self.preset_combo.addItem(f"⭐ {name}", self.custom_presets[name])
        self.preset_combo.insertSeparator(self.preset_combo.count()); self.preset_combo.addItem("Custom")

    def init_codecs(self):
        self.codec_combo.clear()
        if self.mode == "general": self.codec_combo.addItems(["DNxHR (Avid)", "ProRes (Apple)", "H.264", "H.265 (HEVC)"])
        else: self.codec_combo.addItems(["H.264", "H.265 (HEVC)"])

    def update_profiles(self):
        self.profile_combo.clear(); codec = self.codec_combo.currentText()
        if "DNxHR" in codec: self.profile_combo.addItem("LB (Proxy)", "dnxhr_lb"); self.profile_combo.addItem("SQ (Standard)", "dnxhr_sq"); self.profile_combo.addItem("HQ (High Quality)", "dnxhr_hq")
        elif "ProRes" in codec: self.profile_combo.addItem("Proxy", "0"); self.profile_combo.addItem("LT", "1"); self.profile_combo.addItem("422", "2"); self.profile_combo.addItem("HQ", "3")
        elif "H.264" in codec: self.profile_combo.addItem("High", "high"); self.profile_combo.addItem("Main", "main")
        elif "H.265" in codec: self.profile_combo.addItem("Main", "main"); self.profile_combo.addItem("Main 10", "main10")

    def save_custom_preset(self):
        name, ok = QInputDialog.getText(self, "Save Preset", "Enter a name for this preset:")
        if ok and name.strip():
            if PresetManager.save_preset(name.strip(), self.get_settings()): self.init_presets(); idx = self.preset_combo.findText(f"⭐ {name.strip()}"); self.preset_combo.setCurrentIndex(idx)

    def import_preset_file(self):
        f, _ = QFileDialog.getOpenFileName(self, "Import Preset", "", "JSON Files (*.json)")
        if f:
            try:
                with open(f, 'r') as p: data = json.load(p)
                name = os.path.splitext(os.path.basename(f))[0]
                if PresetManager.save_preset(name, data): self.init_presets(); QMessageBox.information(self, "Success", f"Imported '{name}'")
            except Exception as e: QMessageBox.critical(self, "Error", f"Failed to import: {e}")

    def export_preset_file(self):
        text = self.preset_combo.currentText(); data = self.preset_combo.currentData() or self.get_settings()
        clean_name = text.replace("⭐ ", "").replace("Linux ", "").replace(" ", "_")
        f, _ = QFileDialog.getSaveFileName(self, "Export Preset", f"{clean_name}.json", "JSON Files (*.json)")
        if f:
            try:
                with open(f, 'w') as p: json.dump(data, p, indent=4)
                QMessageBox.information(self, "Success", f"Exported to {f}")
            except Exception as e: QMessageBox.critical(self, "Error", f"Failed to export: {e}")

    def delete_current_preset(self):
        text = self.preset_combo.currentText()
        if text.startswith("⭐ "):
            if PresetManager.delete_preset(text.replace("⭐ ", "")): self.init_presets()

    def apply_preset(self):
        text = self.preset_combo.currentText(); is_custom_entry = (text == "Custom"); is_user_preset = text.startswith("⭐ ")
        
        # Keep advanced settings enabled for all modes so users can apply modifiers (like Audio Drift Fix)
        self.advanced_frame.setEnabled(True)
        self.btn_del_preset.setEnabled(is_user_preset); self.btn_export_preset.setEnabled(is_user_preset or is_custom_entry)
        
        data = self.preset_combo.currentData()
        if data and isinstance(data, dict):
            v_map = {"dnxhd": 0, "prores_ks": 1, "libx264": 2, "libx265": 3}
            if self.mode != "general": v_map = {"libx264": 0, "libx265": 1}
            self.codec_combo.setCurrentIndex(v_map.get(data.get('v_codec'), 0)); self.update_profiles()
            p_idx = self.profile_combo.findData(data.get('v_profile'))
            if p_idx >= 0: self.profile_combo.setCurrentIndex(p_idx)
            self.audio_combo.setCurrentIndex(1 if data.get('a_codec') == 'aac' else 0); self.chk_audio_fix.setChecked(data.get('audio_fix', False))
            self.lut_path.setText(data.get('lut_path', "")); self.chk_burn_file.setChecked(data.get('burn_file', False)); self.chk_burn_tc.setChecked(data.get('burn_tc', False)); self.inp_watermark.setText(data.get('watermark', ""))
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
        self.codec_combo.blockSignals(True); self.codec_combo.setCurrentIndex(codec_idx); self.codec_combo.blockSignals(False); self.update_profiles()
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
            "audio_fix": self.chk_audio_fix.isChecked(), "burn_file": self.chk_burn_file.isChecked(),
            "burn_tc": self.chk_burn_tc.isChecked(), "watermark": self.inp_watermark.text().strip()
        }
        if self.lut_path.text().strip(): settings["lut_path"] = self.lut_path.text().strip()
        return settings
    def is_gpu_enabled(self): return self.chk_gpu.isChecked()
    def set_gpu_checked(self, checked): self.chk_gpu.blockSignals(True); self.chk_gpu.setChecked(checked); self.chk_gpu.blockSignals(False)

class CheckableComboBox(QComboBox):
    checked_items_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setEditable(True)
        self.lineEdit().setReadOnly(True)
        self.lineEdit().setPlaceholderText("All Media")
        
        self.p_model = QStandardItemModel(self)
        self.setModel(self.p_model)
        self.view().viewport().installEventFilter(self)
        self.view().pressed.connect(self.handle_item_pressed)

    def eventFilter(self, obj, event):
        if obj == self.view().viewport() and event.type() == QEvent.Type.MouseButtonRelease:
            return True # Prevent popup closing
        return False

    def handle_item_pressed(self, index):
        item = self.p_model.itemFromIndex(index)
        if item.checkState() == Qt.CheckState.Checked: item.setCheckState(Qt.CheckState.Unchecked)
        else: item.setCheckState(Qt.CheckState.Checked)
        self.update_text()
        self.checked_items_changed.emit()

    def add_check_item(self, text, data=None):
        item = QStandardItem(text)
        item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        item.setData(data)
        item.setCheckState(Qt.CheckState.Unchecked)
        self.p_model.appendRow(item)
        self.update_text()

    def update_text(self):
        items = [self.p_model.item(i).text() for i in range(self.p_model.rowCount()) if self.p_model.item(i).checkState() == Qt.CheckState.Checked]
        text = ", ".join(items) if items else "All Media"
        self.lineEdit().setText(text)

    def get_checked_data(self):
        return [self.p_model.item(i).data() for i in range(self.p_model.rowCount()) if self.p_model.item(i).checkState() == Qt.CheckState.Checked]
        
    def set_checked_texts(self, texts_str):
        if not texts_str or texts_str == "All Media": 
            for i in range(self.p_model.rowCount()): self.p_model.item(i).setCheckState(Qt.CheckState.Unchecked)
        else:
            texts = [t.strip() for t in texts_str.split(',')]
            for i in range(self.p_model.rowCount()):
                item = self.p_model.item(i)
                item.setCheckState(Qt.CheckState.Checked if item.text() in texts else Qt.CheckState.Unchecked)
        self.update_text()
