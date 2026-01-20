import os
import subprocess
import signal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, 
    QTableWidgetItem, QHeaderView, QPushButton, QFrame, 
    QToolButton, QSlider, QSizePolicy, QStyle
)
from PyQt6.QtCore import Qt, QUrl
from ..utils import DependencyManager

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
        super().__init__(parent); self.setWindowTitle(f"Preview: {os.path.basename(video_path)}"); self.resize(900, 600)
        self.video_path = video_path; self.process = None
        
        layout = QVBoxLayout(); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(0); self.setLayout(layout)
        
        # Container for FFplay embedding
        self.video_container = QFrame()
        self.video_container.setStyleSheet("background-color: black;")
        self.video_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.video_container)
        
        # Instructions / Status Bar
        status_bar = QFrame(); status_bar.setFixedHeight(30); status_bar.setStyleSheet("background-color: #222; color: #888;")
        sb_lay = QHBoxLayout(status_bar); sb_lay.setContentsMargins(10, 0, 10, 0)
        self.lbl_status = QLabel("Loading player..."); sb_lay.addWidget(self.lbl_status)
        sb_lay.addStretch()
        sb_lay.addWidget(QLabel("Controls: [Space] Pause  [Right/Left] Seek  [F] Fullscreen  [Esc] Close"))
        layout.addWidget(status_bar)

    def showEvent(self, event):
        super().showEvent(event)
        # Use QTimer to delay starting ffplay until the window is fully shown and window handle is valid
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(100, self.start_ffplay)

    def start_ffplay(self):
        self.cleanup()
        
        # Locate ffplay
        ffplay = DependencyManager.get_binary_path("ffplay")
        if not ffplay:
            # Fallback to assuming it's next to ffmpeg or in path
            ffmpeg = DependencyManager.get_ffmpeg_path()
            if ffmpeg:
                d = os.path.dirname(ffmpeg)
                guess = os.path.join(d, "ffplay" if os.name != 'nt' else "ffplay.exe")
                if os.path.exists(guess): ffplay = guess
        
        if not ffplay:
            # Last ditch attempt
            try:
                subprocess.run(['ffplay', '-version'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                ffplay = 'ffplay'
            except: pass

        if not ffplay:
            self.lbl_status.setText("Error: ffplay not found.")
            return

        self.lbl_status.setText(f"Playing: {os.path.basename(self.video_path)}")
        
        # Build Command
        # -noborder: Remove window decorations
        # -loglevel quiet: Suppress console output
        # -infbuf: Infinite buffer for robustness (prevents dropouts)
        cmd = [ffplay, self.video_path, '-noborder', '-loglevel', 'quiet', '-infbuf', '-window_title', 'CineBridge_Embed']
        
        # Embedding
        # Linux/Unix use SDL_WINDOWID environment variable
        env = os.environ.copy()
        
        # Ensure we have a valid window ID
        win_id = int(self.video_container.winId())
        if win_id:
            env['SDL_WINDOWID'] = str(win_id)
        
        try:
            self.process = subprocess.Popen(cmd, env=env)
        except Exception as e:
            self.lbl_status.setText(f"Error launching player: {e}")

    def load_video(self, video_path):
        self.video_path = video_path
        self.setWindowTitle(f"Preview: {os.path.basename(video_path)}")
        if self.isVisible():
            self.start_ffplay()

    def cleanup(self):
        if self.process:
            if self.process.poll() is None:
                # Try graceful termination first
                self.process.terminate()
                try:
                    self.process.wait(timeout=0.5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
            self.process = None

    def closeEvent(self, event):
        self.cleanup()
        event.accept()