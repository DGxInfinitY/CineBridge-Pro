import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
    QFileDialog, QProgressBar, QListWidget, QGroupBox, QFrame, 
    QAbstractItemView, QMenu, QMessageBox
)
from PyQt6.QtGui import QAction, QIcon, QPixmap
from PyQt6.QtCore import Qt, QSize

from ..utils import SystemNotifier, MediaInfoExtractor
from ..workers import BatchTranscodeWorker, ThumbnailWorker, SystemMonitor
from ..ui import TranscodeSettingsWidget, JobReportDialog, MediaInfoDialog

class ConvertTab(QWidget):
    def __init__(self):
        super().__init__(); self.setAcceptDrops(True); self.is_processing = False; self.thumb_workers = []
        self.sys_mon = SystemMonitor()
        self.sys_mon.stats_signal.connect(self.update_load_display)
        
        layout = QVBoxLayout(); layout.setSpacing(15); layout.setContentsMargins(20, 20, 20, 20); self.setLayout(layout)
        self.settings = TranscodeSettingsWidget("1. Conversion Settings", mode="general"); layout.addWidget(self.settings)
        input_group = QGroupBox("2. Input Media"); input_lay = QVBoxLayout(); self.btn_browse = QPushButton("Select Video Files..."); self.btn_browse.clicked.connect(self.browse_files); input_lay.addWidget(self.btn_browse)
        self.drop_area = QLabel("\n⬇️\n\nDRAG & DROP VIDEO FILES HERE\n\n"); self.drop_area.setAlignment(Qt.AlignmentFlag.AlignCenter); self.drop_area.setStyleSheet("QLabel { border: 3px dashed #666; border-radius: 10px; background-color: #2b2b2b; color: #aaa; font-weight: bold; } QLabel:hover { border-color: #3498DB; background-color: #333; color: white; }")
        input_lay.addWidget(self.drop_area, 1); input_group.setLayout(input_lay); layout.addWidget(input_group, 1)
        out_group = QGroupBox("3. Destination (Optional)"); out_lay = QHBoxLayout(); self.out_input = QLineEdit(); self.btn_browse_out = QPushButton("Browse..."); self.btn_browse_out.clicked.connect(self.browse_dest)
        out_lay.addWidget(self.out_input); out_lay.addWidget(self.btn_browse_out); out_group.setLayout(out_lay); layout.addWidget(out_group)
        queue_group = QGroupBox("4. Batch Queue"); queue_lay = QVBoxLayout(); self.list = QListWidget(); self.list.setMaximumHeight(150); self.list.setIconSize(QSize(96, 54)); queue_lay.addWidget(self.list)
        dash_frame = QFrame(); dash_frame.setObjectName("DashFrame"); dash_layout = QVBoxLayout(dash_frame); dash_row = QHBoxLayout(); self.status_label = QLabel("Waiting..."); self.stats_row = QWidget(); self.stats_row.setVisible(False); sr_lay = QHBoxLayout(self.stats_row)
        self.cpu_load_lbl = QLabel("CPU: 0%"); self.cpu_temp_lbl = QLabel(""); self.gpu_load_lbl = QLabel(""); self.gpu_temp_lbl = QLabel(""); sr_lay.addWidget(self.cpu_load_lbl); sr_lay.addWidget(self.cpu_temp_lbl); sr_lay.addWidget(self.gpu_load_lbl); sr_lay.addWidget(self.gpu_temp_lbl)
        dash_row.addWidget(self.status_label); dash_row.addStretch(); dash_layout.addLayout(dash_row)
        self.metrics_label = QLabel(""); self.metrics_label.setVisible(False); self.metrics_label.setStyleSheet("color: #3498DB; font-family: Consolas; font-size: 11px;"); dash_layout.addWidget(self.metrics_label)
        dash_layout.addWidget(self.stats_row)
        self.pbar = QProgressBar(); dash_layout.addWidget(self.pbar); queue_lay.addWidget(dash_frame)
        h = QHBoxLayout(); b_clr = QPushButton("Clear Queue"); b_clr.clicked.connect(self.list.clear); self.btn_go = QPushButton("START BATCH"); self.btn_go.setObjectName("StartBtn"); self.btn_go.clicked.connect(self.on_btn_click)
        h.addWidget(b_clr); h.addWidget(self.btn_go); queue_lay.addLayout(h); queue_group.setLayout(queue_lay); layout.addWidget(queue_group); layout.addStretch()
                
    def update_load_display(self, stats):
        self.cpu_load_lbl.setText(f"CPU: {stats['cpu_load']}")
        self.cpu_temp_lbl.setText(f"({stats['cpu_temp']}°C)" if stats['cpu_temp'] > 0 else "")
        if stats['has_gpu']:
            vendor = stats.get('gpu_vendor', 'GPU')
            self.gpu_load_lbl.setText(f"{vendor}: {stats['gpu_load']}")
            self.gpu_temp_lbl.setText(f"({stats['gpu_temp']}°C)" if stats['gpu_temp'] > 0 else "")
            self.gpu_load_lbl.setVisible(True); self.gpu_temp_lbl.setVisible(True)
        else:
            self.gpu_load_lbl.setVisible(False); self.gpu_temp_lbl.setVisible(False)

    def browse_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Videos", "", "Video Files (*.mp4 *.mov *.mkv *.avi)")
        if files: [self.list.addItem(f) for f in files]; self.start_thumb_process(files)
    def browse_dest(self):
        d = QFileDialog.getExistingDirectory(self, "Pick a Destination")
        if d: self.out_input.setText(d)
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls(): e.accept()
    def dropEvent(self, e):
        new = [u.toLocalFile() for u in e.mimeData().urls() if u.toLocalFile().lower().endswith(('.mp4','.mov','.mkv','.avi'))]
        if new: [self.list.addItem(f) for f in new]; self.start_thumb_process(new)
    def on_btn_click(self):
        if self.is_processing: self.stop()
        else: self.start()
    def toggle_ui_state(self, running):
        self.is_processing = running; self.stats_row.setVisible(running); self.metrics_label.setVisible(running)
        if running:
            self.sys_mon.start()
            self.btn_go.setText("STOP BATCH"); self.btn_go.setObjectName("StopBtn")
        else:
            self.sys_mon.stop()
            self.btn_go.setText("START BATCH"); self.btn_go.setObjectName("StartBtn")
            self.metrics_label.setText("")
        
        self.btn_go.style().unpolish(self.btn_go); self.btn_go.style().polish(self.btn_go)
    def start(self):
        files = [self.list.item(i).text() for i in range(self.list.count())]
        if not files: return QMessageBox.warning(self, "Empty", "Queue is empty.")
        self.toggle_ui_state(True); self.worker = BatchTranscodeWorker(files, self.out_input.text().strip(), self.settings.get_settings(), mode="convert", use_gpu=self.settings.is_gpu_enabled())
        self.worker.progress_signal.connect(self.pbar.setValue); self.worker.status_signal.connect(self.status_label.setText); self.worker.metrics_signal.connect(self.metrics_label.setText); self.worker.finished_signal.connect(self.on_finished); self.worker.start()
    def start_thumb_process(self, files):
        worker = ThumbnailWorker(files); worker.thumb_ready.connect(self.update_thumbnail); worker.start(); self.thumb_workers.append(worker)
    def update_thumbnail(self, path, image):
        pix = QPixmap.fromImage(image); items = self.list.findItems(path, Qt.MatchFlag.MatchExactly)
        for i in items: i.setIcon(QIcon(pix))
    def stop(self):
        if hasattr(self, 'worker'): self.worker.stop(); self.status_label.setText("Stopping...")
    def on_finished(self, success, msg):
        if success:
            SystemNotifier.notify("Conversion Complete", "Batch transcode finished."); self.status_label.setText("Batch Complete!")
            JobReportDialog("Conversion Complete", "Transcode Successful. Your media is ready for edit.", self).exec()
        else:
            QMessageBox.critical(self, "Transcode Failed", msg); self.status_label.setText("Failed.")
        self.toggle_ui_state(False)
    def show_context_menu(self, pos):
        i = self.list.itemAt(pos)
        if i:
            m = QMenu(self); a = QAction("Inspect Media Info", self); a.triggered.connect(lambda: MediaInfoDialog(MediaInfoExtractor.get_info(i.text()), self).exec()); m.addAction(a); m.exec(self.list.mapToGlobal(pos))
    def inspect_file(self, item):
        path = item.text()
        if os.path.exists(path):
            info = MediaInfoExtractor.get_info(path); dlg = MediaInfoDialog(info, self); dlg.exec()

    def closeEvent(self, event):
        if hasattr(self, 'sys_mon'): self.sys_mon.stop(); self.sys_mon.wait()
        super().closeEvent(event)