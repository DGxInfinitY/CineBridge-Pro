import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
    QFileDialog, QProgressBar, QGroupBox, QFrame
)
from PyQt6.QtCore import Qt
from ..workers import BatchTranscodeWorker
from ..ui import TranscodeSettingsWidget, JobReportDialog, FileDropLineEdit
from ..utils import SystemNotifier

class DeliveryTab(QWidget):
    def __init__(self):
        super().__init__(); self.setAcceptDrops(True); self.is_processing = False
        layout = QVBoxLayout(); layout.setSpacing(15); layout.setContentsMargins(20, 20, 20, 20); self.setLayout(layout)
        self.settings = TranscodeSettingsWidget("1. Delivery Settings", mode="delivery"); self.settings.preset_combo.setCurrentText("H.264 / AVC (Standard)"); layout.addWidget(self.settings)
        master_group = QGroupBox("2. Master File"); master_lay = QVBoxLayout(); self.inp_file = FileDropLineEdit()
        self.btn_sel_master = QPushButton("Select Master File..."); self.btn_sel_master.clicked.connect(lambda: self.inp_file.setText(QFileDialog.getOpenFileName(self, "Select Master File")[0]))
        self.drop_area = QLabel("\n⬇️\n\nDRAG MASTER FILE HERE\n\n"); self.drop_area.setAlignment(Qt.AlignmentFlag.AlignCenter); self.drop_area.setStyleSheet("QLabel { border: 3px dashed #666; border-radius: 10px; background-color: #2b2b2b; color: #aaa; font-weight: bold; } QLabel:hover { border-color: #3498DB; background-color: #333; color: white; }")
        master_lay.addWidget(self.btn_sel_master); master_lay.addWidget(self.inp_file); master_lay.addWidget(self.drop_area, 1); master_group.setLayout(master_lay); layout.addWidget(master_group, 1)
        dest_group = QGroupBox("3. Destination (Optional)"); dest_lay = QHBoxLayout(); self.inp_dest = QLineEdit(); self.btn_b2 = QPushButton("Browse...")
        self.btn_b2.clicked.connect(lambda: self.inp_dest.setText(QFileDialog.getExistingDirectory(self, "Pick a Destination"))); dest_lay.addWidget(self.inp_dest); dest_lay.addWidget(self.btn_b2); dest_group.setLayout(dest_lay); layout.addWidget(dest_group)
        dash_frame = QFrame(); dash_frame.setObjectName("DashFrame"); dash_layout = QVBoxLayout(dash_frame)
        self.status_label = QLabel("Ready to Render"); dash_layout.addWidget(self.status_label)
        self.metrics_label = QLabel(""); self.metrics_label.setVisible(False); self.metrics_label.setStyleSheet("color: #3498DB; font-family: Consolas; font-size: 11px;"); dash_layout.addWidget(self.metrics_label)
        self.pbar = QProgressBar(); dash_layout.addWidget(self.pbar); layout.addWidget(dash_frame)
        self.btn_go = QPushButton("GENERATE DELIVERY MASTER"); self.btn_go.setObjectName("StartBtn"); self.btn_go.setMinimumHeight(50); self.btn_go.clicked.connect(self.on_btn_click); layout.addWidget(self.btn_go); layout.addStretch() 
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls(): e.accept()
    def dropEvent(self, e):
        urls = e.mimeData().urls()
        if urls: f = urls[0].toLocalFile(); self.inp_file.setText(f)
    def on_btn_click(self):
        if self.is_processing: self.stop()
        else: self.start()
    def toggle_ui_state(self, running):
        self.is_processing = running; self.metrics_label.setVisible(running)
        if not running: self.metrics_label.setText("")
        if running: self.btn_go.setText("STOP RENDER"); self.btn_go.setObjectName("StopBtn")
        else: self.btn_go.setText("RENDER"); self.btn_go.setObjectName("StartBtn")
        self.btn_go.style().unpolish(self.btn_go); self.btn_go.style().polish(self.btn_go)
    def start(self):
        if not self.inp_file.text(): return QMessageBox.warning(self, "Missing", "Select master file.")
        self.toggle_ui_state(True); self.worker = BatchTranscodeWorker([self.inp_file.text()], self.inp_dest.text().strip(), self.settings.get_settings(), mode="delivery", use_gpu=self.settings.is_gpu_enabled())
        self.worker.progress_signal.connect(self.pbar.setValue); self.worker.status_signal.connect(self.status_label.setText); self.worker.metrics_signal.connect(self.metrics_label.setText); self.worker.finished_signal.connect(self.on_finished); self.worker.start()
    def stop(self):
        if hasattr(self, 'worker'): self.worker.stop(); self.status_label.setText("Stopping...")
    def on_finished(self, success, msg):
        if success:
            SystemNotifier.notify("Render Complete", "Delivery render finished."); self.status_label.setText("Delivery Render Complete!")
            JobReportDialog("Render Complete", "Final Render Successful. Your master is ready for distribution.", self).exec()
        else:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Render Failed", msg); self.status_label.setText("Failed.")
        self.toggle_ui_state(False)