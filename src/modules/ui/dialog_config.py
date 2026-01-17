import os
import subprocess
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QGroupBox, QComboBox, QTextEdit
)
from PyQt6.QtCore import QSettings
from ..utils import EnvUtils, DependencyManager

class FFmpegConfigDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent); self.setWindowTitle("FFmpeg configuration"); self.resize(600, 500)
        self.settings = QSettings("CineBridgePro", "Config"); layout = QVBoxLayout(); layout.setSpacing(15); self.setLayout(layout)
        path_group = QGroupBox("FFmpeg binary location"); path_lay = QVBoxLayout(); row = QHBoxLayout(); self.path_input = QLineEdit(); self.path_input.setReadOnly(True)
        self.btn_browse = QPushButton("Browse..."); self.btn_browse.clicked.connect(self.browse_ffmpeg); self.btn_reset = QPushButton("Reset default"); self.btn_reset.clicked.connect(self.reset_ffmpeg)
        row.addWidget(self.path_input); row.addWidget(self.btn_browse); row.addWidget(self.btn_reset); path_lay.addLayout(row); path_lay.addWidget(QLabel("<small>Select a custom FFmpeg binary.</small>")); path_group.setLayout(path_lay); layout.addWidget(path_group)
        cap_group = QGroupBox("Detected capabilities"); cap_lay = QVBoxLayout(); self.report_area = QTextEdit(); self.report_area.setReadOnly(True); self.report_area.setStyleSheet("font-family: Consolas; font-size: 12px;"); cap_lay.addWidget(self.report_area); cap_group.setLayout(cap_lay); layout.addWidget(cap_group)
        btn_row = QHBoxLayout(); btn_row.addStretch(); close_btn = QPushButton("Close"); close_btn.clicked.connect(self.accept); btn_row.addWidget(close_btn); layout.addLayout(btn_row); self.refresh_status()
    def browse_ffmpeg(self):
        from PyQt6.QtWidgets import QFileDialog
        f, _ = QFileDialog.getOpenFileName(self, "Select FFmpeg executable")
        if f: self.settings.setValue("ffmpeg_custom_path", f); self.refresh_status()
    def reset_ffmpeg(self): self.settings.remove("ffmpeg_custom_path"); self.refresh_status()
    def refresh_status(self):
        path = DependencyManager.get_ffmpeg_path()
        self.path_input.setText(path if path else "Not Found")
        if not path:
            self.report_area.setHtml("<h3 style='color:red'>FFmpeg binary not found!</h3>"); return

        report = f"<b>Active Binary:</b> {path}<br>"
        if DependencyManager.detect_hw_accel(): 
            report += "<span style='color: green'>[Hardware Acceleration Ready]</span><br>"
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

class TranscodeConfigDialog(QDialog):
    def __init__(self, settings_widget, parent=None):
        super().__init__(parent); self.setWindowTitle("Transcode configuration"); self.resize(500, 400); layout = QVBoxLayout(); self.setLayout(layout); self.settings_widget = settings_widget
        if self.settings_widget.parent(): self.settings_widget.parent().layout().removeWidget(self.settings_widget)
        layout.addWidget(self.settings_widget); btn = QPushButton("Done"); btn.clicked.connect(self.accept); layout.addWidget(btn)
    def accept(self): self.layout().removeWidget(self.settings_widget); self.settings_widget.setParent(None); super().accept()
    def reject(self): self.layout().removeWidget(self.settings_widget); self.settings_widget.setParent(None); super().reject()

class StructureConfigDialog(QDialog):
    def __init__(self, current_template, parent=None):
        super().__init__(parent); self.setWindowTitle("Folder Structure Configuration"); self.resize(500, 250)
        layout = QVBoxLayout(); layout.setSpacing(15); self.setLayout(layout)
        
        layout.addWidget(QLabel("<b>Select Output Structure</b>"))
        layout.addWidget(QLabel("Define how files are organized inside the Project folder."))
        
        self.combo_presets = QComboBox()
        self.presets = {
            "Standard DIT (Date/Camera/Type)": "{Date}/{Camera}/{Category}",
            "Simple Date (Date only)": "{Date}",
            "Device Centric (Camera/Date)": "{Camera}/{Date}",
            "Type Centric (Type/Date)": "{Category}/{Date}",
            "Flat (Files in Project root)": ""
        }
        for name, tmpl in self.presets.items():
            self.combo_presets.addItem(name, tmpl)
        
        self.combo_presets.addItem("Custom...", "custom")
        layout.addWidget(self.combo_presets)
        
        self.inp_custom = QLineEdit()
        self.inp_custom.setPlaceholderText("e.g. {Date}/{Camera}")
        self.inp_custom.setText(current_template)
        layout.addWidget(self.inp_custom)
        
        self.lbl_preview = QLabel()
        self.lbl_preview.setStyleSheet("color: #777; font-style: italic;")
        layout.addWidget(self.lbl_preview)
        
        self.combo_presets.currentIndexChanged.connect(self.on_combo_change)
        self.inp_custom.textChanged.connect(self.update_preview)
        
        # Set initial state
        found = False
        for i in range(self.combo_presets.count()):
            if self.combo_presets.itemData(i) == current_template:
                self.combo_presets.setCurrentIndex(i); found = True; break
        if not found:
            self.combo_presets.setCurrentIndex(self.combo_presets.count() - 1) # Custom
            self.inp_custom.setEnabled(True)
        else:
            self.inp_custom.setEnabled(False)
            
        self.update_preview()
        
        btns = QHBoxLayout(); btns.addStretch()
        btn_ok = QPushButton("OK"); btn_ok.clicked.connect(self.accept)
        btn_cancel = QPushButton("Cancel"); btn_cancel.clicked.connect(self.reject)
        btns.addWidget(btn_cancel); btns.addWidget(btn_ok); layout.addLayout(btns)

    def on_combo_change(self):
        data = self.combo_presets.currentData()
        if data == "custom":
            self.inp_custom.setEnabled(True); self.inp_custom.setFocus()
        else:
            self.inp_custom.setEnabled(False); self.inp_custom.setText(data)
        self.update_preview()

    def update_preview(self):
        tmpl = self.inp_custom.text()
        example = tmpl.replace("{Date}", "2023-10-27").replace("{Camera}", "Sony_FX3").replace("{Category}", "videos")
        path = os.path.join("Project_Name", example, "C001.mp4")
        self.lbl_preview.setText(f"Preview: {path}")

    def get_template(self):
        return self.inp_custom.text()
