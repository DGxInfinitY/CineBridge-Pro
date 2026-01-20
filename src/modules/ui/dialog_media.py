import os
import subprocess
import signal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, 
    QTableWidgetItem, QHeaderView, QPushButton, QFrame, 
    QToolButton, QSlider, QSizePolicy, QStyle, QWidget
)
from PyQt6.QtCore import Qt, QUrl, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
from ..utils import DependencyManager, EnvUtils

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
        super().__init__(parent); self.setWindowTitle(f"Preview: {os.path.basename(video_path)}"); self.resize(800, 500)
        self.video_path = video_path; self.process = None
        self.monitor_timer = QTimer(self); self.monitor_timer.setInterval(500); self.monitor_timer.timeout.connect(self.monitor_process)
        
        layout = QVBoxLayout(); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(0); self.setLayout(layout)
        
        # Container for FFplay embedding
        self.video_container = QFrame()
        self.video_container.setAttribute(Qt.WidgetAttribute.WA_NativeWindow) # Crucial for embedding
        self.video_container.setStyleSheet("background-color: black;")
        self.video_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.video_container)
        
        # Status Bar
        status_bar = QFrame(); status_bar.setFixedHeight(40); status_bar.setStyleSheet("background-color: #222; color: #ccc; border-top: 1px solid #444;")
        sb_lay = QHBoxLayout(status_bar); sb_lay.setContentsMargins(10, 0, 10, 0)
        self.lbl_status = QLabel("Loading player..."); sb_lay.addWidget(self.lbl_status)
        sb_lay.addStretch()
        sb_lay.addWidget(QLabel("<b>Controls:</b> Space=Pause | Arrows=Seek | F=Fullscreen"))
        sb_lay.addSpacing(20)
        btn_close = QPushButton("Close Preview"); btn_close.setFixedSize(100, 24); btn_close.clicked.connect(self.close)
        btn_close.setStyleSheet("background-color: #C0392B; color: white; border: none; border-radius: 3px;")
        sb_lay.addWidget(btn_close)
        layout.addWidget(status_bar)

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(200, self.start_ffplay)

    def monitor_process(self):
        if self.process and self.process.poll() is not None:
            self.monitor_timer.stop()
            self.close()

    def start_ffplay(self):
        self.cleanup()
        
        ffplay = DependencyManager.get_binary_path("ffplay")
        if not ffplay:
            self.lbl_status.setText("Error: ffplay not found.")
            return

        self.lbl_status.setText(f"Playing: {os.path.basename(self.video_path)}")
        
        # Forced dimensions to prevent auto-fullscreen
        w = self.video_container.width()
        h = self.video_container.height()
        
        # Build Command
        cmd = [
            ffplay, self.video_path, 
            '-noborder', 
            '-loglevel', 'quiet', 
            '-threads', '0', 
            '-x', str(w), '-y', str(h),
            '-window_title', 'CineBridge_Embed'
        ]
        
        # Environment setup for robust embedding
        env = os.environ.copy()
        env['SDL_VIDEODRIVER'] = 'x11' # Force X11 for SDL embedding compatibility
        
        win_id = int(self.video_container.winId())
        if win_id:
            env['SDL_WINDOWID'] = str(win_id)
        
        try:
            self.process = subprocess.Popen(cmd, env=env)
            self.monitor_timer.start()
        except Exception as e:
            self.lbl_status.setText(f"Error launching player: {e}")

    def load_video(self, video_path):
        self.video_path = video_path
        self.setWindowTitle(f"Preview: {os.path.basename(video_path)}")
        if self.isVisible():
            self.start_ffplay()

    def cleanup(self):
        self.monitor_timer.stop()
        if self.process:
            proc = self.process
            self.process = None
            try:
                proc.terminate()
                try: proc.wait(timeout=0.2)
                except: proc.kill()
            except: pass

    def closeEvent(self, event):
        self.cleanup()
        event.accept()