import os
import sys
import subprocess
import platform
from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
    QFileDialog, QCheckBox, QGroupBox, QComboBox, QFrame, QRadioButton, 
    QButtonGroup, QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QSlider, QStyle, QSizePolicy, QToolButton
)
from PyQt6.QtGui import QPixmap, QIcon, QPalette
from PyQt6.QtCore import Qt, QSettings, QUrl, QTimer
from ..config import DEBUG_MODE, AppLogger
from ..utils import EnvUtils, DependencyManager, SystemNotifier, MediaInfoExtractor

try:
    from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
    from PyQt6.QtMultimediaWidgets import QVideoWidget
    HAS_MULTIMEDIA = True
except ImportError:
    HAS_MULTIMEDIA = False

class JobReportDialog(QDialog):
    def __init__(self, title, message, parent=None):
        super().__init__(parent); self.setWindowTitle(title); self.setFixedWidth(450); layout = QVBoxLayout()
        layout.setContentsMargins(30, 30, 30, 30); layout.setSpacing(20)
        header_lay = QHBoxLayout(); icon_label = QLabel(); icon_label.setPixmap(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton).pixmap(32, 32))
        header_lay.addWidget(icon_label); msg_label = QLabel(message); msg_label.setWordWrap(True); msg_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        header_lay.addWidget(msg_label, 1); layout.addLayout(header_lay)
        ok_btn = QPushButton("OK"); ok_btn.setMinimumHeight(40); ok_btn.setFixedWidth(100); ok_btn.clicked.connect(self.accept)
        btn_lay = QHBoxLayout(); btn_lay.addStretch(); btn_lay.addWidget(ok_btn); btn_lay.addStretch(); layout.addLayout(btn_lay); self.setLayout(layout)

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

class MediaInfoDialog(QDialog):
    def __init__(self, media_info, parent=None):
        super().__init__(parent); self.setWindowTitle(f"Media Info: {media_info.get('filename', 'Unknown')}"); self.resize(500, 600); layout = QVBoxLayout(); self.setLayout(layout)
        if "error" in media_info: layout.addWidget(QLabel(f"Error: {media_info['error']}")); return
        layout.addWidget(QLabel("<b>Container Format</b>")); gen_table = QTableWidget(3, 2); gen_table.horizontalHeader().setVisible(False); gen_table.verticalHeader().setVisible(False); gen_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        gen_table.setItem(0, 0, QTableWidgetItem("Container")); gen_table.setItem(0, 1, QTableWidgetItem(media_info['container'])); gen_table.setItem(1, 0, QTableWidgetItem("Duration")); gen_table.setItem(1, 1, QTableWidgetItem(f"{media_info['duration']:.2f} sec")); gen_table.setItem(2, 0, QTableWidgetItem("Size")); gen_table.setItem(2, 1, QTableWidgetItem(f"{media_info['size_mb']:.2f} MB")); layout.addWidget(gen_table)
        if media_info['video_streams']:
            layout.addWidget(QLabel("<b>Video Streams</b>"))
            for v in media_info['video_streams']:
                v_table = QTableWidget(5, 2); v_table.horizontalHeader().setVisible(False); v_table.verticalHeader().setVisible(False); v_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
                v_table.setItem(0, 0, QTableWidgetItem("Codec")); v_table.setItem(0, 1, QTableWidgetItem(f"{v['codec']} ({v['profile']})")); v_table.setItem(1, 0, QTableWidgetItem("Resolution")); v_table.setItem(1, 1, QTableWidgetItem(v['resolution'])); v_table.setItem(2, 0, QTableWidgetItem("Frame rate")); v_table.setItem(2, 1, QTableWidgetItem(str(v['fps']))); v_table.setItem(3, 0, QTableWidgetItem("Pixel format")); v_table.setItem(3, 1, QTableWidgetItem(v['pix_fmt'])); v_table.setItem(4, 0, QTableWidgetItem("Bitrate")); v_table.setItem(4, 1, QTableWidgetItem(f"{v['bitrate']} kbps")); layout.addWidget(v_table)
        layout.addStretch(); close_btn = QPushButton("Close"); close_btn.clicked.connect(self.accept); layout.addWidget(close_btn)

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

class TranscodeConfigDialog(QDialog):
    def __init__(self, settings_widget, parent=None):
        super().__init__(parent); self.setWindowTitle("Transcode configuration"); self.resize(500, 400); layout = QVBoxLayout(); self.setLayout(layout); self.settings_widget = settings_widget
        if self.settings_widget.parent(): self.settings_widget.parent().layout().removeWidget(self.settings_widget)
        layout.addWidget(self.settings_widget); btn = QPushButton("Done"); btn.clicked.connect(self.accept); layout.addWidget(btn)
    def accept(self): self.layout().removeWidget(self.settings_widget); self.settings_widget.setParent(None); super().accept()
    def reject(self): self.layout().removeWidget(self.settings_widget); self.settings_widget.setParent(None); super().reject()

class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent); self.setWindowTitle("About CineBridge Pro"); self.setFixedWidth(400); layout = QVBoxLayout(); layout.setSpacing(15); layout.setContentsMargins(30, 30, 30, 30); logo_label = QLabel(); logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if hasattr(sys, '_MEIPASS'): base_dir = sys._MEIPASS
        else: base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        logo_path = os.path.join(base_dir, "assets", "icon.svg")
        if os.path.exists(logo_path): pixmap = QPixmap(logo_path); logo_label.setPixmap(pixmap.scaled(80, 80, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        layout.addWidget(logo_label); title = QLabel("CineBridge Pro"); title.setStyleSheet("font-size: 22px; font-weight: bold; color: #3498DB;"); title.setAlignment(Qt.AlignmentFlag.AlignCenter); layout.addWidget(title); version = QLabel("v4.16.6 (Dev)"); version.setStyleSheet("font-size: 14px; color: #888;"); version.setAlignment(Qt.AlignmentFlag.AlignCenter); layout.addWidget(version); desc = QLabel("The Linux DIT & Post-Production Suite.\nSolving the 'Resolve on Linux' problem."); desc.setWordWrap(True); desc.setStyleSheet("font-size: 13px;"); desc.setAlignment(Qt.AlignmentFlag.AlignCenter); layout.addWidget(desc); credits = QLabel("<b>Developed by:</b><br>Donovan Goodwin<br>(with Gemini AI)"); credits.setStyleSheet("font-size: 13px;"); credits.setAlignment(Qt.AlignmentFlag.AlignCenter); layout.addWidget(credits); links = QLabel('<a href="mailto:ddg2goodwin@gmail.com" style="color: #3498DB;">ddg2goodwin@gmail.com</a><br><br><a href="https://github.com/DGxInfinitY" style="color: #3498DB;">GitHub: DGxInfinitY</a>'); links.setOpenExternalLinks(True); links.setAlignment(Qt.AlignmentFlag.AlignCenter); layout.addWidget(links); layout.addStretch(); btn_box = QHBoxLayout(); ok_btn = QPushButton("Close"); ok_btn.setFixedWidth(100); ok_btn.clicked.connect(self.accept); btn_box.addStretch(); btn_box.addWidget(ok_btn); btn_box.addStretch(); layout.addLayout(btn_box); self.setLayout(layout)

class VideoPreviewDialog(QDialog):
    def __init__(self, video_path, parent=None):
        super().__init__(parent); self.setWindowTitle(f"Preview: {os.path.basename(video_path)}"); self.resize(900, 600); layout = QVBoxLayout(); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(0); self.setLayout(layout); self.video_path = video_path; self.player = None; self.video_widget = None; self.audio = None
        if not HAS_MULTIMEDIA: layout.addWidget(QLabel("Video preview not available.\nMissing 'PyQt6.QtMultimedia' module.", alignment=Qt.AlignmentFlag.AlignCenter)); return
        self.video_container = QFrame(); self.video_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding); self.video_layout = QVBoxLayout(self.video_container); self.video_layout.setContentsMargins(0,0,0,0); layout.addWidget(self.video_container)
        ctrl_frame = QFrame(); ctrl_frame.setStyleSheet("background-color: #222; border-top: 1px solid #444;"); ctrl_frame.setFixedHeight(50); ctrl_layout = QHBoxLayout(); ctrl_layout.setContentsMargins(10, 5, 10, 5); ctrl_frame.setLayout(ctrl_layout); self.play_btn = QToolButton(); self.play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)); self.play_btn.clicked.connect(self.toggle_play); ctrl_layout.addWidget(self.play_btn); self.lbl_curr = QLabel("00:00"); self.lbl_curr.setStyleSheet("color: #ccc; font-family: monospace;"); ctrl_layout.addWidget(self.lbl_curr); self.slider = QSlider(Qt.Orientation.Horizontal); self.slider.setRange(0, 0); self.slider.sliderMoved.connect(self.set_position); ctrl_layout.addWidget(self.slider); self.lbl_total = QLabel("00:00"); self.lbl_total.setStyleSheet("color: #ccc; font-family: monospace;"); ctrl_layout.addWidget(self.lbl_total); ctrl_layout.addSpacing(10); vol_icon = QLabel(); vol_icon.setPixmap(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaVolume).pixmap(16,16)); ctrl_layout.addWidget(vol_icon); self.vol_slider = QSlider(Qt.Orientation.Horizontal); self.vol_slider.setFixedWidth(80); self.vol_slider.setRange(0, 100); self.vol_slider.setValue(100); self.vol_slider.valueChanged.connect(self.set_volume); ctrl_layout.addWidget(self.vol_slider); self.fs_btn = QToolButton(); self.fs_btn.setText("⛶"); self.fs_btn.setToolTip("Toggle fullscreen"); self.fs_btn.clicked.connect(self.toggle_fullscreen); ctrl_layout.addWidget(self.fs_btn); layout.addWidget(ctrl_frame)
    def showEvent(self, event):
        super().showEvent(event)
        if not HAS_MULTIMEDIA or self.player: return
        self.player = QMediaPlayer(); self.audio = QAudioOutput(); self.player.setAudioOutput(self.audio); self.audio.setVolume(self.vol_slider.value() / 100); self.video_widget = QVideoWidget(); self.video_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding); self.video_layout.addWidget(self.video_widget); self.player.setVideoOutput(self.video_widget); self.player.positionChanged.connect(self.position_changed); self.player.durationChanged.connect(self.duration_changed); self.player.mediaStatusChanged.connect(self.status_changed); self.player.errorOccurred.connect(self.handle_errors); self.play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause)); self.player.setSource(QUrl.fromLocalFile(self.video_path)); self.player.play()

    def load_video(self, video_path):
        if not HAS_MULTIMEDIA: return
        self.video_path = video_path
        self.setWindowTitle(f"Preview: {os.path.basename(video_path)}")
        self.play_btn.setEnabled(True); self.play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))
        if self.player:
            self.player.setVideoOutput(None); self.player.setVideoOutput(self.video_widget)
            self.player.setSource(QUrl.fromLocalFile(video_path)); self.player.play()

    def cleanup(self):
        if self.player: self.player.stop(); self.player.setSource(QUrl()); self.player.setVideoOutput(None); self.player.setAudioOutput(None); self.player.deleteLater(); self.player = None
        if self.audio: self.audio.deleteLater(); self.audio = None
        if self.video_widget: self.video_layout.removeWidget(self.video_widget); self.video_widget.deleteLater(); self.video_widget = None
    def set_volume(self, v):
        if self.audio: self.audio.setVolume(v / 100)
    def toggle_play(self):
        if not self.player: return
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState: self.player.pause(); self.play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        else: self.player.play(); self.play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))
    def toggle_fullscreen(self):
        if self.isFullScreen(): self.showNormal()
        else: self.showFullScreen()
    def set_position(self, position):
        if self.player: self.player.setPosition(position)
    def position_changed(self, position):
        if not self.slider.isSliderDown(): self.slider.setValue(position)
        if self.player: self.update_time_label(position, self.player.duration())
    def duration_changed(self, duration):
        self.slider.setRange(0, duration)
        if self.player: self.update_time_label(self.player.position(), duration)
    def update_time_label(self, current_ms, total_ms):
        def fmt(ms): return f"{(ms//1000)//60:02}:{(ms//1000)%60:02}"
        self.lbl_curr.setText(fmt(current_ms)); self.lbl_total.setText(fmt(total_ms))
    def status_changed(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia: self.play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
    def handle_errors(self):
        self.play_btn.setEnabled(False); self.lbl_curr.setText("Error")
    def closeEvent(self, event): self.cleanup(); event.accept()
