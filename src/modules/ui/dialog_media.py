import os
import subprocess
import signal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, 
    QTableWidgetItem, QHeaderView, QPushButton, QFrame, 
    QToolButton, QSlider, QSizePolicy, QStyle
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

class FrameReaderThread(QThread):
    frame_ready = pyqtSignal(QImage)
    finished = pyqtSignal()
    
    def __init__(self, video_path):
        super().__init__()
        self.video_path = video_path
        self.is_running = True
        self.process = None
        self.width = 640
        self.height = 360
        
    def run(self):
        ffmpeg = DependencyManager.get_ffmpeg_path()
        if not ffmpeg: return

        # FFmpeg command: HW Accel -> Multi-thread -> Native Speed (-re) -> Scale -> Raw RGB Pipe
        cmd = [
            ffmpeg, 
            '-hwaccel', 'auto',
            '-threads', '0',
            '-re', 
            '-i', self.video_path,
            '-vf', f'scale={self.width}:{self.height}:force_original_aspect_ratio=decrease,pad={self.width}:{self.height}:(ow-iw)/2:(oh-ih)/2',
            '-f', 'image2pipe',
            '-pix_fmt', 'rgb24',
            '-vcodec', 'rawvideo',
            '-an', # Audio handled separately
            '-'
        ]
        
        try:
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                
            self.process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.DEVNULL,
                bufsize=10**7,
                startupinfo=startupinfo,
                env=EnvUtils.get_clean_env()
            )
            
            frame_size = self.width * self.height * 3
            
            while self.is_running:
                raw_frame = self.process.stdout.read(frame_size)
                if not raw_frame or len(raw_frame) != frame_size: break
                img = QImage(raw_frame, self.width, self.height, QImage.Format.Format_RGB888)
                self.frame_ready.emit(img.copy())
                
        except Exception as e: print(f"Preview Error: {e}")
        finally:
            self.stop_process()
            self.finished.emit()

    def stop(self):
        self.is_running = False
        self.stop_process()
        
    def stop_process(self):
        if self.process:
            proc = self.process
            self.process = None
            try:
                proc.terminate()
                try: proc.wait(timeout=0.5)
                except: proc.kill()
            except: pass

class VideoPreviewDialog(QDialog):
    def __init__(self, video_path, parent=None):
        super().__init__(parent); self.setWindowTitle(f"Preview: {os.path.basename(video_path)}"); self.resize(700, 450)
        self.video_path = video_path; self.reader = None; self.audio_process = None
        
        layout = QVBoxLayout(); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(0); self.setLayout(layout)
        
        self.video_label = QLabel()
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setStyleSheet("background-color: black;")
        self.video_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.video_label)
        
        status_bar = QFrame(); status_bar.setFixedHeight(40); status_bar.setStyleSheet("background-color: #222; color: #ccc; border-top: 1px solid #444;")
        sb_lay = QHBoxLayout(status_bar); sb_lay.setContentsMargins(10, 0, 10, 0)
        self.lbl_status = QLabel("Loading preview..."); sb_lay.addWidget(self.lbl_status)
        sb_lay.addStretch()
        sb_lay.addWidget(QLabel("Video + Audio Preview"))
        sb_lay.addSpacing(20)
        btn_close = QPushButton("Close"); btn_close.setFixedSize(80, 24); btn_close.clicked.connect(self.close)
        btn_close.setStyleSheet("background-color: #C0392B; color: white; border: none; border-radius: 3px;")
        sb_lay.addWidget(btn_close)
        layout.addWidget(status_bar)

    def showEvent(self, event):
        super().showEvent(event)
        self.start_preview()

    def start_preview(self):
        self.cleanup()
        self.lbl_status.setText(f"Playing: {os.path.basename(self.video_path)}")
        
        # 1. Start Video Pipe
        self.reader = FrameReaderThread(self.video_path)
        self.reader.frame_ready.connect(self.update_frame)
        self.reader.finished.connect(self.on_finished)
        self.reader.start()
        
        # 2. Start Audio Player (Parallel)
        ffplay = DependencyManager.get_binary_path("ffplay")
        if ffplay:
            try:
                cmd = [ffplay, '-nodisp', '-autoexit', '-loglevel', 'quiet', self.video_path]
                self.audio_process = subprocess.Popen(cmd, env=EnvUtils.get_clean_env())
            except: pass

    def update_frame(self, image):
        scaled = QPixmap.fromImage(image).scaled(self.video_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation)
        self.video_label.setPixmap(scaled)

    def load_video(self, video_path):
        self.video_path = video_path
        self.setWindowTitle(f"Preview: {os.path.basename(video_path)}")
        if self.isVisible(): self.start_preview()

    def on_finished(self):
        self.lbl_status.setText("Preview finished.")

    def cleanup(self):
        if self.reader:
            self.reader.stop()
            self.reader.wait()
            self.reader = None
        if self.audio_process:
            try:
                self.audio_process.terminate()
                self.audio_process.wait(timeout=0.2)
            except: 
                try: self.audio_process.kill()
                except: pass
            self.audio_process = None

    def closeEvent(self, event):
        self.cleanup()
        event.accept()