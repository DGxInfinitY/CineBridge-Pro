import os
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
    QFileDialog, QProgressBar, QGroupBox, QFrame, QSpinBox, QFormLayout, QMessageBox,
    QCheckBox
)
from PyQt6.QtCore import Qt, QTimer, QSettings

from modules.ui.widgets import TranscodeSettingsWidget
from modules.workers.transcode import BatchTranscodeWorker
from modules.utils.registry import DeviceRegistry
from modules.utils.notifier import SystemNotifier

class WatchTab(QWidget):
    def __init__(self):
        super().__init__(); layout = QVBoxLayout(); layout.setSpacing(15); layout.setContentsMargins(20, 20, 20, 20); self.setLayout(layout)
        self.is_active = False; self.processed_files = set(); self.timer = QTimer(); self.timer.timeout.connect(self.check_folder)
        self.monitored_files = {}; self.STABILITY_THRESHOLD = 3.0; self.global_settings = QSettings("CineBridgePro", "Config")
        
        conf_group = QGroupBox("1. Service Configuration"); conf_lay = QVBoxLayout(); stab_lay = QHBoxLayout(); stab_lay.addWidget(QLabel("File Stability Check (Seconds):"))
        self.spin_stability = QSpinBox(); self.spin_stability.setRange(1, 60); self.spin_stability.setValue(3); self.spin_stability.valueChanged.connect(self.update_threshold); stab_lay.addWidget(self.spin_stability)
        
        self.chk_auto = QCheckBox("Auto-start service on launch"); self.chk_auto.setChecked(self.global_settings.value("watch_autostart", False, type=bool))
        self.chk_auto.toggled.connect(lambda c: self.global_settings.setValue("watch_autostart", c))
        stab_lay.addWidget(self.chk_auto); stab_lay.addStretch(); conf_lay.addLayout(stab_lay)
        
        self.settings = TranscodeSettingsWidget(mode="general"); conf_lay.addWidget(self.settings); conf_group.setLayout(conf_lay); layout.addWidget(conf_group)
        fold_group = QGroupBox("2. Folder Selection"); fold_lay = QFormLayout(); self.inp_watch = QLineEdit(); self.btn_watch = QPushButton("Browse..."); self.btn_watch.clicked.connect(self.browse_watch)
        
        # Load saved paths
        self.inp_watch.setText(self.global_settings.value("watch_source", "")); 
        self.inp_watch.textChanged.connect(lambda t: self.global_settings.setValue("watch_source", t))
        
        w_row = QHBoxLayout(); w_row.addWidget(self.inp_watch); w_row.addWidget(self.btn_watch); self.inp_dest = QLineEdit(); self.btn_dest = QPushButton("Browse..."); self.btn_dest.clicked.connect(self.browse_dest)
        
        self.inp_dest.setText(self.global_settings.value("watch_dest", "")); 
        self.inp_dest.textChanged.connect(lambda t: self.global_settings.setValue("watch_dest", t))

        d_row = QHBoxLayout(); d_row.addWidget(self.inp_dest); d_row.addWidget(self.btn_dest); fold_lay.addRow("Watch Folder:", w_row); fold_lay.addRow("Destination:", d_row); fold_group.setLayout(fold_lay); layout.addWidget(fold_group)
        dash_frame = QFrame(); dash_frame.setObjectName("DashFrame"); dash_layout = QVBoxLayout(dash_frame)
        self.status_label = QLabel("Watch Folder: INACTIVE"); dash_layout.addWidget(self.status_label)
        self.metrics_label = QLabel(""); self.metrics_label.setVisible(False); self.metrics_label.setStyleSheet("color: #3498DB; font-family: Consolas; font-size: 11px;"); dash_layout.addWidget(self.metrics_label)
        
        self.stats_row = QWidget(); self.stats_row.setVisible(False); sr_lay = QHBoxLayout(self.stats_row); sr_lay.setContentsMargins(0,0,0,0); sr_lay.setSpacing(10)
        self.cpu_load_lbl = QLabel("CPU: 0%"); self.cpu_load_lbl.setStyleSheet("color: #E74C3C; font-weight: bold; font-size: 11px;")
        self.cpu_temp_lbl = QLabel(""); self.cpu_temp_lbl.setStyleSheet("color: #E74C3C; font-size: 11px;")
        self.gpu_load_lbl = QLabel(""); self.gpu_load_lbl.setStyleSheet("color: #3498DB; font-weight: bold; font-size: 11px;")
        self.gpu_temp_lbl = QLabel(""); self.gpu_temp_lbl.setStyleSheet("color: #3498DB; font-size: 11px;")
        sr_lay.addStretch(); sr_lay.addWidget(self.cpu_load_lbl); sr_lay.addWidget(self.cpu_temp_lbl); sr_lay.addWidget(self.gpu_load_lbl); sr_lay.addWidget(self.gpu_temp_lbl); sr_lay.addStretch()
        dash_layout.addWidget(self.stats_row)
        
        self.pbar = QProgressBar(); self.pbar.setVisible(False); dash_layout.addWidget(self.pbar); layout.addWidget(dash_frame)
        self.btn_toggle = QPushButton("ACTIVATE WATCH FOLDER"); self.btn_toggle.setObjectName("StartBtn"); self.btn_toggle.setMinimumHeight(50); self.btn_toggle.clicked.connect(self.toggle_watch); layout.addWidget(self.btn_toggle); layout.addStretch()

        if self.chk_auto.isChecked() and self.inp_watch.text() and self.inp_dest.text():
             QTimer.singleShot(1000, self.toggle_watch)

    def update_load_display(self, stats):
        self.cpu_load_lbl.setText(f"CPU: {stats['cpu_load']}%")
        self.cpu_temp_lbl.setText(f"({stats['cpu_temp']}°C)" if stats['cpu_temp'] > 0 else "")
        if stats['has_gpu']:
            v = stats.get('gpu_vendor', 'GPU'); self.gpu_load_lbl.setText(f"{v}: {stats['gpu_load']}%"); self.gpu_temp_lbl.setText(f"({stats['gpu_temp']}°C)" if stats['gpu_temp'] > 0 else "")
            self.gpu_load_lbl.setVisible(True); self.gpu_temp_lbl.setVisible(True)
        else: self.gpu_load_lbl.setVisible(False); self.gpu_temp_lbl.setVisible(False)

    def update_threshold(self, v): self.STABILITY_THRESHOLD = float(v)
    def browse_watch(self):
        d = QFileDialog.getExistingDirectory(self, "Select Watch Folder"); 
        if d: self.inp_watch.setText(d)
    def browse_dest(self):
        d = QFileDialog.getExistingDirectory(self, "Pick Destination");
        if d: self.inp_dest.setText(d)
    def toggle_watch(self):
        if self.is_active:
            self.is_active = False; self.timer.stop(); self.btn_toggle.setText("ACTIVATE WATCH FOLDER"); self.btn_toggle.setObjectName("StartBtn"); self.status_label.setText("Watch Folder: INACTIVE")
        else:
            if not self.inp_watch.text() or not self.inp_dest.text(): return QMessageBox.warning(self, "Error", "Set folders.")
            self.is_active = True; self.timer.start(2000); self.btn_toggle.setText("DEACTIVATE WATCH FOLDER"); self.btn_toggle.setObjectName("StopBtn"); self.status_label.setText("Watch Folder: ACTIVE")
        self.btn_toggle.style().unpolish(self.btn_toggle); self.btn_toggle.style().polish(self.btn_toggle)
    def check_folder(self):
        path = self.inp_watch.text()
        if not os.path.exists(path): return
        candidates = [os.path.join(path, f) for f in os.listdir(path) if os.path.isfile(os.path.join(path, f)) and os.path.join(path, f) not in self.processed_files and os.path.splitext(f)[1].upper() in DeviceRegistry.VIDEO_EXTS]
        ready = []
        for p in candidates:
            try:
                sz = os.path.getsize(p); now = datetime.now().timestamp()
                if p not in self.monitored_files: self.monitored_files[p] = {'size': sz, 'stable_since': now}
                else:
                    d = self.monitored_files[p]
                    if sz != d['size']: d['size'] = sz; d['stable_since'] = now
                    elif (now - d['stable_since']) >= self.STABILITY_THRESHOLD: ready.append(p); del self.monitored_files[p]
            except: pass
        if ready: self.status_label.setText(f"Processing {len(ready)} files..."); self.start_batch(ready)
    def start_batch(self, files):
        self.worker = BatchTranscodeWorker(files, self.inp_dest.text(), self.settings.get_settings(), mode="convert", use_gpu=self.settings.is_gpu_enabled())
        self.worker.progress_signal.connect(self.pbar.setValue); self.worker.metrics_signal.connect(self.metrics_label.setText); self.worker.finished_signal.connect(self.on_batch_finished)
        self.pbar.setVisible(True); self.metrics_label.setVisible(True); self.stats_row.setVisible(True); self.timer.stop()
        for f in files: self.processed_files.add(f)
        self.worker.start()
    def on_batch_finished(self, success, msg):
        self.pbar.setVisible(False); self.metrics_label.setVisible(False); self.stats_row.setVisible(False); self.metrics_label.setText(""); self.timer.start(2000)
        if success: self.status_label.setText("Watch Folder: ACTIVE"); SystemNotifier.notify("Watch Folder", "New proxies processed.")
        else: self.status_label.setText(f"ERROR: {msg}"); SystemNotifier.notify("Watch Folder Error", msg)
