import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, 
    QTableWidgetItem, QHeaderView, QPushButton, QFrame, 
    QToolButton, QSlider, QSizePolicy, QStyle
)
from PyQt6.QtCore import Qt, QUrl
try:
    from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
    from PyQt6.QtMultimediaWidgets import QVideoWidget
    HAS_MULTIMEDIA = True
except ImportError:
    HAS_MULTIMEDIA = False

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

class VideoPreviewDialog(QDialog):
    def __init__(self, video_path, parent=None):
        super().__init__(parent); self.setWindowTitle(f"Preview: {os.path.basename(video_path)}"); self.resize(900, 600); layout = QVBoxLayout(); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(0); self.setLayout(layout); self.video_path = video_path; self.player = None; self.video_widget = None; self.audio = None
        if not HAS_MULTIMEDIA: layout.addWidget(QLabel("Video preview not available.\nMissing 'PyQt6.QtMultimedia' module.", alignment=Qt.AlignmentFlag.AlignCenter)); return
        self.video_container = QFrame(); self.video_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding); self.video_layout = QVBoxLayout(self.video_container); self.video_layout.setContentsMargins(0,0,0,0); layout.addWidget(self.video_container)
        ctrl_frame = QFrame(); ctrl_frame.setStyleSheet("background-color: #222; border-top: 1px solid #444;"); ctrl_frame.setFixedHeight(50); ctrl_layout = QHBoxLayout(); ctrl_layout.setContentsMargins(10, 5, 10, 5); ctrl_frame.setLayout(ctrl_layout); self.play_btn = QToolButton(); self.play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)); self.play_btn.clicked.connect(self.toggle_play); ctrl_layout.addWidget(self.play_btn); self.lbl_curr = QLabel("00:00"); self.lbl_curr.setStyleSheet("color: #ccc; font-family: monospace;"); ctrl_layout.addWidget(self.lbl_curr); self.slider = QSlider(Qt.Orientation.Horizontal); self.slider.setRange(0, 0); self.slider.sliderMoved.connect(self.set_position); ctrl_layout.addWidget(self.slider); self.lbl_total = QLabel("00:00"); self.lbl_total.setStyleSheet("color: #ccc; font-family: monospace;"); ctrl_layout.addWidget(self.lbl_total); ctrl_layout.addSpacing(10); vol_icon = QLabel(); vol_icon.setPixmap(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaVolume).pixmap(16,16)); ctrl_layout.addWidget(vol_icon); self.vol_slider = QSlider(Qt.Orientation.Horizontal); self.vol_slider.setFixedWidth(80); self.vol_slider.setRange(0, 100); self.vol_slider.setValue(100); self.vol_slider.valueChanged.connect(self.set_volume); ctrl_layout.addWidget(self.vol_slider); self.fs_btn = QToolButton(); self.fs_btn.setText("⛶"); self.fs_btn.setToolTip("Toggle fullscreen"); self.fs_btn.clicked.connect(self.toggle_fullscreen); ctrl_layout.addWidget(self.fs_btn); layout.addWidget(ctrl_frame)
    def init_player(self):
        if self.player: return
        self.player = QMediaPlayer()
        self.audio = QAudioOutput()
        self.player.setAudioOutput(self.audio)
        self.audio.setVolume(self.vol_slider.value() / 100)
        
        self.video_widget = QVideoWidget()
        self.video_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.video_layout.addWidget(self.video_widget)
        self.player.setVideoOutput(self.video_widget)
        
        self.player.positionChanged.connect(self.position_changed)
        self.player.durationChanged.connect(self.duration_changed)
        self.player.mediaStatusChanged.connect(self.status_changed)
        self.player.errorOccurred.connect(self.handle_errors)

    def showEvent(self, event):
        super().showEvent(event)
        if not HAS_MULTIMEDIA: return
        self.init_player()
        if self.video_path and self.player.playbackState() == QMediaPlayer.PlaybackState.StoppedState:
            self.player.setSource(QUrl.fromLocalFile(self.video_path))
            self.player.play()
            self.play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))

    def load_video(self, video_path):
        if not HAS_MULTIMEDIA: return
        self.cleanup() # Full reset to prevent GStreamer pipeline hangs
        self.video_path = video_path
        self.setWindowTitle(f"Preview: {os.path.basename(video_path)}")
        self.play_btn.setEnabled(True)
        
        self.init_player()
        self.player.setSource(QUrl.fromLocalFile(video_path))
        self.player.play()
        self.play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))

    def cleanup(self):
        if self.player:
            self.player.stop()
            self.player.setSource(QUrl())
            self.player.setVideoOutput(None)
            self.player.deleteLater()
            self.player = None
        if self.audio:
            self.audio.deleteLater()
            self.audio = None
        if self.video_widget:
            self.video_layout.removeWidget(self.video_widget)
            self.video_widget.deleteLater()
            self.video_widget = None

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
    def handle_errors(self, error, error_string):
        self.play_btn.setEnabled(False); self.lbl_curr.setText("Error")
        print(f"Video Error: {error} - {error_string}")
    def closeEvent(self, event): self.cleanup(); event.accept()
