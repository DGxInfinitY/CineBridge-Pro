from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
    QCheckBox, QGroupBox, QComboBox, QRadioButton, 
    QButtonGroup, QLineEdit, QLabel, QFileDialog, QWidget
)
from ..utils import EnvUtils
from ..config import AppLogger
from .dialog_config import FFmpegConfigDialog

class AdvancedFeaturesDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent); self.setWindowTitle("Advanced feature configuration"); self.setMinimumWidth(550); self.parent_app = parent; layout = QVBoxLayout(); self.settings = parent.settings
        feat_group = QGroupBox("Pro / workflow features"); feat_lay = QVBoxLayout(); feat_group.setLayout(feat_lay)
        self.chk_watch = QCheckBox("Enable watch folder service"); self.chk_watch.setChecked(self.settings.value("feature_watch_folder", False, type=bool)); feat_lay.addWidget(self.chk_watch)
        self.chk_burn = QCheckBox("Enable burn-in tools (Dailies)"); self.chk_burn.setChecked(self.settings.value("feature_burn_in", False, type=bool)); feat_lay.addWidget(self.chk_burn)
        self.chk_multi = QCheckBox("Enable multi-destination ingest"); self.chk_multi.setChecked(self.settings.value("feature_multi_dest", False, type=bool)); feat_lay.addWidget(self.chk_multi)
        self.chk_mhl = QCheckBox("Enable MHL generation (Media hash list)"); self.chk_mhl.setChecked(self.settings.value("feature_mhl", False, type=bool)); feat_lay.addWidget(self.chk_mhl)
        self.chk_pdf = QCheckBox("Enable PDF transfer reports"); self.chk_pdf.setChecked(self.settings.value("feature_pdf_report", False, type=bool)); feat_lay.addWidget(self.chk_pdf)
        self.chk_visual = QCheckBox("Use visual PDF reports (Thumbnails)"); self.chk_visual.setChecked(self.settings.value("feature_visual_report", False, type=bool)); feat_lay.addWidget(self.chk_visual); layout.addWidget(feat_group)
        
        btns = QHBoxLayout(); btn_save = QPushButton("APPLY ADVANCED SETTINGS"); btn_save.clicked.connect(self.save_settings); btn_cancel = QPushButton("Cancel"); btn_cancel.clicked.connect(self.reject); btns.addStretch(); btn_cancel.setFixedWidth(100); btn_save.setFixedWidth(200); btns.addWidget(btn_cancel); btns.addWidget(btn_save); layout.addLayout(btns); self.setLayout(layout)
    def save_settings(self):
        self.settings.setValue("feature_watch_folder", self.chk_watch.isChecked()); self.settings.setValue("feature_burn_in", self.chk_burn.isChecked()); self.settings.setValue("feature_multi_dest", self.chk_multi.isChecked()); self.settings.setValue("feature_mhl", self.chk_mhl.isChecked()); self.settings.setValue("feature_pdf_report", self.chk_pdf.isChecked()); self.settings.setValue("feature_visual_report", self.chk_visual.isChecked()); self.settings.sync(); self.parent_app.update_feature_visibility(); self.accept()

class SettingsDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent); self.parent_app = parent; self.setWindowTitle("CineBridge settings"); self.setMinimumWidth(500); layout = QVBoxLayout()
        theme_group = QGroupBox("Appearance"); theme_lay = QVBoxLayout(); self.rb_sys = QRadioButton("System default"); self.rb_dark = QRadioButton("Dark mode"); self.rb_light = QRadioButton("Light mode")
        mode = parent.settings.value("theme_mode", "system"); bg = QButtonGroup(self); bg.addButton(self.rb_sys); bg.addButton(self.rb_dark); bg.addButton(self.rb_light); self.rb_sys.toggled.connect(lambda: parent.set_theme("system")); self.rb_dark.toggled.connect(lambda: parent.set_theme("dark")); self.rb_light.toggled.connect(lambda: parent.set_theme("light"))
        if mode == "dark": self.rb_dark.setChecked(True)
        elif mode == "light": self.rb_light.setChecked(True)
        else: self.rb_sys.setChecked(True)
        theme_lay.addWidget(self.rb_sys); theme_lay.addWidget(self.rb_dark); theme_lay.addWidget(self.rb_light); theme_group.setLayout(theme_lay); layout.addWidget(theme_group)
        view_group = QGroupBox("View options"); view_lay = QVBoxLayout(); self.chk_copy = QCheckBox("Show copy log"); self.chk_trans = QCheckBox("Show transcode log")
        self.chk_copy.setChecked(parent.tab_ingest.copy_log.isVisible()); self.chk_trans.setChecked(parent.tab_ingest.transcode_log.isVisible()); self.chk_copy.toggled.connect(self.apply_view_options); self.chk_trans.toggled.connect(self.apply_view_options); view_lay.addWidget(self.chk_copy); view_lay.addWidget(self.chk_trans); view_group.setLayout(view_lay); layout.addWidget(view_group)
        sys_group = QGroupBox("System settings"); sys_lay = QVBoxLayout(); sys_group.setLayout(sys_lay)
        self.adv_btn = QPushButton("⚙️ CONFIGURE ADVANCED FEATURES"); self.adv_btn.setMinimumHeight(45); self.adv_btn.setStyleSheet("font-weight: bold; color: #3498DB;"); self.adv_btn.clicked.connect(self.open_advanced); sys_lay.addWidget(self.adv_btn)
        self.btn_ffmpeg = QPushButton("🔧 CONFIGURE FFMPEG"); self.btn_ffmpeg.setMinimumHeight(45); self.btn_ffmpeg.setStyleSheet("font-weight: bold; color: #3498DB;"); self.btn_ffmpeg.clicked.connect(self.show_ffmpeg_info); sys_lay.addWidget(self.btn_ffmpeg)
        self.btn_log = QPushButton("View debug log"); self.btn_log.clicked.connect(self.view_log); sys_lay.addWidget(self.btn_log)
        
        self.chk_debug = QCheckBox("Enable debug mode")
        self.chk_debug.setChecked(parent.settings.value("debug_mode", False, type=bool))
        self.chk_debug.toggled.connect(parent.toggle_debug)
        sys_lay.addWidget(self.chk_debug)
        
        self.btn_reset = QPushButton("Reset to default settings"); self.btn_reset.setStyleSheet("color: red;"); self.btn_reset.clicked.connect(parent.reset_to_defaults); sys_lay.addWidget(self.btn_reset); layout.addWidget(sys_group)
        self.btn_about = QPushButton("About CineBridge Pro"); self.btn_about.clicked.connect(parent.show_about); layout.addWidget(self.btn_about); layout.addStretch(); close_btn = QPushButton("Close"); close_btn.clicked.connect(self.accept); layout.addWidget(close_btn); self.setLayout(layout)
    def open_advanced(self): AdvancedFeaturesDialog(self.parent_app).exec()
    def apply_view_options(self): self.parent_app.tab_ingest.toggle_logs(self.chk_copy.isChecked(), self.chk_trans.isChecked()); self.parent_app.settings.setValue("show_copy_log", self.chk_copy.isChecked()); self.parent_app.settings.setValue("show_trans_log", self.chk_trans.isChecked())
    def show_ffmpeg_info(self): FFmpegConfigDialog(self).exec()
    def view_log(self): EnvUtils.open_file(AppLogger._log_path)
