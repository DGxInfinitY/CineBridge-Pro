import os
import signal
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
    QFileDialog, QProgressBar, QTextEdit, QMessageBox, QCheckBox, QGroupBox, 
    QComboBox, QTabWidget, QFrame, QSplitter, QTreeWidget, QTreeWidgetItem, 
    QGridLayout, QAbstractItemView, QListWidget, QMenu, QFormLayout, QSpinBox
)
from PyQt6.QtGui import QAction, QIcon, QPixmap, QImage
from PyQt6.QtCore import Qt, QTimer, QSize, QBuffer, QByteArray, QIODevice

from .config import DEBUG_MODE, GUI_LOG_QUEUE, debug_log, info_log, error_log
from .utils import DeviceRegistry, ReportGenerator, MHLGenerator, SystemNotifier, MediaInfoExtractor, TranscodeEngine
from .workers import (
    ScanWorker, IngestScanner, AsyncTranscoder, CopyWorker, 
    BatchTranscodeWorker, ThumbnailWorker, SystemMonitor
)
from .widgets import (
    TranscodeSettingsWidget, JobReportDialog, FileDropLineEdit, 
    TranscodeConfigDialog, MediaInfoDialog, VideoPreviewDialog
)

class IngestTab(QWidget):
    def __init__(self, parent_app):
        super().__init__(); self.app = parent_app; self.layout = QVBoxLayout(); self.layout.setSpacing(10); self.layout.setContentsMargins(20, 20, 20, 20); self.setLayout(self.layout)
        self.copy_worker = None; self.transcode_worker = None; self.scan_worker = None; self.found_devices = []; self.current_detected_path = None
        self.ingest_mode = "scan"; self.last_scan_results = None; self.preview_dlg = None
        self.setup_ui(); self.load_tab_settings()
        self.scan_watchdog = QTimer(); self.scan_watchdog.setSingleShot(True); self.scan_watchdog.timeout.connect(self.on_scan_timeout); QTimer.singleShot(500, self.run_auto_scan)
    def setup_ui(self):
        # 1. Source Group
        source_group = QGroupBox("1. Source Media"); source_inner = QVBoxLayout(); self.source_tabs = QTabWidget(); self.tab_auto = QWidget(); auto_lay = QVBoxLayout()
        self.scan_btn = QPushButton(" REFRESH DEVICES "); self.scan_btn.setMinimumHeight(50); self.scan_btn.clicked.connect(self.run_auto_scan)
        self.auto_info_label = QLabel("Scanning..."); self.auto_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.result_card = QFrame(); self.result_card.setVisible(False); self.result_card.setObjectName("ResultCard"); res_lay = QVBoxLayout()
        self.result_label = QLabel(); self.result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.select_device_box = QComboBox(); self.select_device_box.setVisible(False); 
        self.select_device_box.currentIndexChanged.connect(self.on_device_selection_change)
        self.select_device_box.currentIndexChanged.connect(self.reset_ingest_mode)
        res_lay.addWidget(self.result_label); res_lay.addWidget(self.select_device_box); self.result_card.setLayout(res_lay)
        auto_lay.addWidget(self.scan_btn); auto_lay.addWidget(self.auto_info_label); auto_lay.addWidget(self.result_card); auto_lay.addStretch()
        self.tab_auto.setLayout(auto_lay); self.tab_manual = QWidget(); man_lay = QVBoxLayout()
        self.source_input = QLineEdit(); self.browse_src = QPushButton("Browse"); self.browse_src.clicked.connect(self.browse_source)
        self.source_input.textChanged.connect(self.reset_ingest_mode)
        man_lay.addWidget(QLabel("Path:")); man_lay.addWidget(self.source_input); man_lay.addWidget(self.browse_src); man_lay.addStretch()
        self.tab_manual.setLayout(man_lay); self.source_tabs.addTab(self.tab_auto, "Auto"); self.source_tabs.addTab(self.tab_manual, "Manual")
        source_inner.addWidget(self.source_tabs); source_inner.addStretch(); source_group.setLayout(source_inner)

        # 2. Dest Group
        dest_group = QGroupBox("2. Destination"); self.dest_inner = QVBoxLayout()
        self.project_name_input = QLineEdit(); self.project_name_input.setPlaceholderText("Project Name")
        self.dest_input = QLineEdit(); self.browse_dest_btn = QPushButton("Browse"); self.browse_dest_btn.clicked.connect(self.browse_dest)
        
        self.dest_inner.addWidget(QLabel("Project Name:")); self.dest_inner.addWidget(self.project_name_input); 
        self.dest_lbl_1 = QLabel("Main Location:"); self.dest_inner.addWidget(self.dest_lbl_1); 
        self.dest_inner.addWidget(self.dest_input); self.dest_inner.addWidget(self.browse_dest_btn)
        
        # Pro Destinations (Multi-Dest)
        self.dest_2_wrap = QWidget(); d2_lay = QVBoxLayout(); d2_lay.setContentsMargins(0,0,0,0); self.dest_2_wrap.setLayout(d2_lay)
        self.dest_input_2 = QLineEdit(); self.btn_b2 = QPushButton("Browse (Dest 2)"); self.btn_b2.clicked.connect(lambda: self.browse_dest_field(self.dest_input_2))
        d2_lay.addWidget(QLabel("Destination 2:")); d2_lay.addWidget(self.dest_input_2); d2_lay.addWidget(self.btn_b2)
        self.dest_inner.addWidget(self.dest_2_wrap); self.dest_2_wrap.setVisible(False)

        self.dest_3_wrap = QWidget(); d3_lay = QVBoxLayout(); d3_lay.setContentsMargins(0,0,0,0); self.dest_3_wrap.setLayout(d3_lay)
        self.dest_input_3 = QLineEdit(); self.btn_b3 = QPushButton("Browse (Dest 3)"); self.btn_b3.clicked.connect(lambda: self.browse_dest_field(self.dest_input_3))
        d3_lay.addWidget(QLabel("Destination 3:")); d3_lay.addWidget(self.dest_input_3); d3_lay.addWidget(self.btn_b3)
        self.dest_inner.addWidget(self.dest_3_wrap); self.dest_3_wrap.setVisible(False)

        self.dest_inner.addStretch()
        dest_group.setLayout(self.dest_inner)

        # 3. Settings Group
        settings_group = QGroupBox("3. Processing Settings"); settings_layout = QVBoxLayout()
        logic_row = QHBoxLayout(); logic_row.addWidget(QLabel("Camera Profile:")); 
        self.device_combo = QComboBox(); 
        self.device_combo.setToolTip("Select a specific camera profile or use Auto-Detect for intelligent folder naming.")
        self.device_combo.addItem("Auto-Detect", "auto")
        for profile_name in sorted(DeviceRegistry.PROFILES.keys()):
            self.device_combo.addItem(profile_name, profile_name)
        self.device_combo.addItem("Generic Storage", "Generic_Device")
        logic_row.addWidget(self.device_combo)
        settings_layout.addLayout(logic_row)

        rules_grid = QGridLayout()
        self.check_date = QCheckBox("Sort Date"); self.check_date.setToolTip("Organizes offloaded media into folders by capture date.")
        rules_grid.addWidget(self.check_date, 0, 0)
        self.check_dupe = QCheckBox("Skip Dupes"); self.check_dupe.setToolTip("Skips copying files that already exist in the destination with the same size.")
        rules_grid.addWidget(self.check_dupe, 0, 1)
        self.check_videos_only = QCheckBox("Video Only"); self.check_videos_only.setToolTip("Only scans and transfers video file formats, ignoring photos and metadata.")
        self.check_videos_only.toggled.connect(self.refresh_tree_view); rules_grid.addWidget(self.check_videos_only, 0, 2)
        
        self.check_verify = QCheckBox("Verify Copy"); self.check_verify.setStyleSheet("color: #27AE60; font-weight: bold;")
        self.check_verify.setToolTip("Performs xxHash64 or MD5 checksum verification after copy to ensure bit-perfect data integrity.")
        rules_grid.addWidget(self.check_verify, 1, 0)
        
        self.check_report = QCheckBox("Gen Report")
        self.check_report.setToolTip("Generates a professional PDF Transfer Report upon completion.")
        rules_grid.addWidget(self.check_report, 1, 1)
        
        self.check_mhl = QCheckBox("Gen MHL")
        self.check_mhl.setToolTip("Generates an industry-standard ASC-MHL compliant media hash list for data tracking.")
        rules_grid.addWidget(self.check_mhl, 1, 2)

        self.check_transcode = QCheckBox("Enable Transcode"); self.check_transcode.setStyleSheet("color: #E67E22; font-weight: bold;")
        self.check_transcode.setToolTip("Automatically queues all transferred videos for proxy or dailies conversion.")
        self.check_transcode.toggled.connect(self.toggle_transcode_ui)
        rules_grid.addWidget(self.check_transcode, 2, 0, 1, 1, Qt.AlignmentFlag.AlignLeft)
        settings_layout.addLayout(rules_grid)
        
        # Pro Config Buttons
        config_btns = QHBoxLayout()
        self.btn_config_trans = QPushButton("Configure Transcode..."); self.btn_config_trans.setVisible(False); self.btn_config_trans.clicked.connect(self.open_transcode_config)
        self.btn_config_reports = QPushButton("Reports Settings..."); self.btn_config_reports.setVisible(False); self.btn_config_reports.clicked.connect(self.open_report_config)
        config_btns.addWidget(self.btn_config_trans); config_btns.addWidget(self.btn_config_reports)
        settings_layout.addLayout(config_btns)
        
        self.transcode_widget = TranscodeSettingsWidget(mode="general")
        self.report_custom_path = "" # State for custom destination
        settings_layout.addStretch()
        settings_group.setLayout(settings_layout)
        
        # 4. Review Group
        self.review_group = QGroupBox("4. Select Media"); review_lay = QVBoxLayout()
        self.tree = QTreeWidget(); self.tree.setHeaderLabel("Media Review")
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.tree.itemChanged.connect(self.update_transfer_button_text)
        self.tree.itemDoubleClicked.connect(self.open_video_preview)
        # Add Placeholder
        placeholder = QTreeWidgetItem(self.tree); placeholder.setText(0, "Scan source to review media selection."); placeholder.setFlags(placeholder.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
        review_lay.addWidget(self.tree)
        hint_lbl = QLabel("💡 Hint: Double-click a video file to preview it."); hint_lbl.setStyleSheet("color: #777; font-style: italic; font-size: 10px; margin-top: 2px;"); hint_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        review_lay.addWidget(hint_lbl); review_lay.addStretch()
        self.review_group.setLayout(review_lay)
        self.review_group.setVisible(True) # Persistent

        # GRID LAYOUT
        grid = QGridLayout()
        grid.addWidget(source_group, 0, 0)
        grid.addWidget(dest_group, 0, 1)
        grid.addWidget(settings_group, 1, 0)
        grid.addWidget(self.review_group, 1, 1)
        grid.setRowStretch(1, 1); grid.setColumnStretch(0, 1); grid.setColumnStretch(1, 1)
        self.layout.addLayout(grid)

        dash_frame = QFrame(); dash_frame.setObjectName("DashFrame"); dash_layout = QVBoxLayout(); dash_frame.setLayout(dash_layout)
        top_row = QHBoxLayout(); self.status_label = QLabel("READY TO INGEST"); self.status_label.setObjectName("StatusLabel"); self.speed_label = QLabel(""); self.speed_label.setObjectName("SpeedLabel")
        top_row.addWidget(self.status_label, 1); top_row.addWidget(self.speed_label); dash_layout.addLayout(top_row)
        self.storage_bar = QProgressBar(); self.storage_bar.setFormat("Destination Storage: %v%"); self.storage_bar.setStyleSheet("QProgressBar::chunk { background-color: #3498DB; }"); self.storage_bar.setVisible(False); dash_layout.addWidget(self.storage_bar)
        self.progress_bar = QProgressBar(); self.progress_bar.setTextVisible(True); dash_layout.addWidget(self.progress_bar)
        self.transcode_status_label = QLabel(""); self.transcode_status_label.setStyleSheet("color: #E67E22; font-weight: bold;"); self.transcode_status_label.setVisible(False); dash_layout.addWidget(self.transcode_status_label)
        
        # System Stats Row
        self.stats_row = QWidget(); self.stats_row.setVisible(False); sr_lay = QHBoxLayout(self.stats_row); sr_lay.setContentsMargins(0,0,0,0); sr_lay.setSpacing(10)
        self.cpu_load_lbl = QLabel("CPU: 0%"); self.cpu_load_lbl.setStyleSheet("color: #E74C3C; font-weight: bold; font-size: 11px;")
        self.cpu_temp_lbl = QLabel(""); self.cpu_temp_lbl.setStyleSheet("color: #E74C3C; font-size: 11px;")
        self.gpu_load_lbl = QLabel(""); self.gpu_load_lbl.setStyleSheet("color: #3498DB; font-weight: bold; font-size: 11px;")
        self.gpu_temp_lbl = QLabel(""); self.gpu_temp_lbl.setStyleSheet("color: #3498DB; font-size: 11px;")
        sr_lay.addStretch(); sr_lay.addWidget(self.cpu_load_lbl); sr_lay.addWidget(self.cpu_temp_lbl); sr_lay.addWidget(self.gpu_load_lbl); sr_lay.addWidget(self.gpu_temp_lbl); sr_lay.addStretch()
        dash_layout.addWidget(self.stats_row); self.layout.addWidget(dash_frame)
        btn_layout = QHBoxLayout()
        self.import_btn = QPushButton("SCAN SOURCE"); self.import_btn.setObjectName("StartBtn"); self.import_btn.clicked.connect(self.on_import_click)
        self.import_btn.setToolTip("Click to scan the source media or start the transfer process.")
        self.cancel_btn = QPushButton("STOP"); self.cancel_btn.setObjectName("StopBtn"); self.cancel_btn.clicked.connect(self.cancel_import); self.cancel_btn.setEnabled(False)
        self.cancel_btn.setToolTip("Aborts all current copy and transcode operations.")
        self.clear_logs_btn = QPushButton("Clear Logs"); self.clear_logs_btn.setToolTip("Clear the status logs below."); self.clear_logs_btn.clicked.connect(self.clear_logs)
        btn_layout.addWidget(self.import_btn); btn_layout.addWidget(self.cancel_btn); btn_layout.addWidget(self.clear_logs_btn); self.layout.addLayout(btn_layout)
        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.copy_log = QTextEdit(); self.copy_log.setReadOnly(True); self.copy_log.setMinimumHeight(40); self.copy_log.setStyleSheet("background-color: #1e1e1e; color: #2ECC71; font-family: Consolas; font-size: 11px;"); self.copy_log.setPlaceholderText("Copy Log...")
        self.transcode_log = QTextEdit(); self.transcode_log.setReadOnly(True); self.transcode_log.setMinimumHeight(40); self.transcode_log.setStyleSheet("background-color: #2c2c2c; color: #3498DB; font-family: Consolas; font-size: 11px;"); self.transcode_log.setPlaceholderText("Transcode Log..."); self.splitter.addWidget(self.copy_log); self.splitter.addWidget(self.transcode_log); self.layout.addWidget(self.splitter, 1)
        self.transcode_log.setVisible(False)
    def clear_logs(self): self.copy_log.clear(); self.transcode_log.clear()
    def toggle_logs(self, show_copy, show_transcode): self.copy_log.setVisible(show_copy); self.transcode_log.setVisible(show_transcode); self.splitter.setVisible(show_copy or show_transcode)
    def toggle_transcode_ui(self, checked): 
        self.btn_config_trans.setVisible(checked); self.transcode_status_label.setVisible(checked)
        self.update_transfer_button_text()
    def open_transcode_config(self):
        dlg = TranscodeConfigDialog(self.transcode_widget, self); dlg.exec()
    def update_load_display(self, stats):
        self.cpu_load_lbl.setText(f"CPU: {stats['cpu_load']}%")
        self.cpu_temp_lbl.setText(f"({stats['cpu_temp']}°C)" if stats['cpu_temp'] > 0 else "")
        
        # GPU Stats - Only show if detected and HW Accel might be in use
        if stats['has_gpu']:
            vendor = stats.get('gpu_vendor', 'GPU')
            self.gpu_load_lbl.setText(f"{vendor}: {stats['gpu_load']}%")
            self.gpu_temp_lbl.setText(f"({stats['gpu_temp']}°C)" if stats['gpu_temp'] > 0 else "")
            self.gpu_load_lbl.setVisible(True); self.gpu_temp_lbl.setVisible(True)
        else:
            self.gpu_load_lbl.setVisible(False); self.gpu_temp_lbl.setVisible(False)

    def set_transcode_active(self, active): self.stats_row.setVisible(active); self.transcode_status_label.setVisible(active)
    def browse_source(self):
        d = QFileDialog.getExistingDirectory(self, "Source", self.source_input.text()); 
        if d: self.source_input.setText(d)
    def browse_dest(self):
        d = QFileDialog.getExistingDirectory(self, "Pick a Destination", self.dest_input.text()); 
        if d: self.dest_input.setText(d)
    def browse_dest_field(self, field):
        d = QFileDialog.getExistingDirectory(self, "Pick a Destination", field.text()); 
        if d: field.setText(d)
    def update_pro_features_ui(self, show_multi, show_visual):
        self.dest_lbl_1.setText("Main Location:" if show_multi else "Location:")
        self.dest_2_wrap.setVisible(show_multi)
        self.dest_3_wrap.setVisible(show_multi)
        
        # New Report/MHL Visibility Logic
        show_pdf = self.app.settings.value("feature_pdf_report", True, type=bool)
        show_mhl = self.app.settings.value("feature_mhl", False, type=bool)
        dest_mode = self.app.settings.value("report_dest_mode", "project")
        
        self.check_report.setVisible(show_pdf)
        self.check_report.setText("Gen Visual Report" if show_visual else "Gen Report")
        self.check_mhl.setVisible(show_mhl)
        
        # Only show Report Settings button if PDF/MHL is on AND mode is 'custom'
        self.btn_config_reports.setVisible((show_pdf or show_mhl) and dest_mode == "custom")

    def open_report_config(self):
        d = QFileDialog.getExistingDirectory(self, "Select Custom Report Destination", self.report_custom_path or self.dest_input.text())
        if d: self.report_custom_path = d

    def append_copy_log(self, text): self.copy_log.append(text); sb = self.copy_log.verticalScrollBar(); sb.setValue(sb.maximum())
    def append_transcode_log(self, text): self.transcode_log.append(text); sb = self.transcode_log.verticalScrollBar(); sb.setValue(sb.maximum())
    def run_auto_scan(self): self.auto_info_label.setText("Scanning..."); self.result_card.setVisible(False); self.select_device_box.setVisible(False); self.scan_btn.setEnabled(False); self.scan_watchdog.start(30000); self.scan_worker = ScanWorker(); self.scan_worker.finished_signal.connect(self.on_scan_finished); self.scan_worker.start()
    def on_scan_timeout(self):
        if self.scan_worker.isRunning(): self.scan_worker.terminate(); self.auto_info_label.setText("Scan Timed Out")
    def on_scan_finished(self, results): 
        self.scan_watchdog.stop(); self.found_devices = results; self.scan_btn.setEnabled(True)
        if results: self.auto_info_label.setText("✅ Scan Complete"); self.update_result_ui(results[0], len(results)>1)
        else: self.result_card.setVisible(False); self.auto_info_label.setText("No devices")
    def reset_ingest_mode(self):
        """Resets the UI state when source changes."""
        if self.ingest_mode != "scan":
            self.ingest_mode = "scan"
            self.last_scan_results = None
            self.update_transfer_button_text()
            self.import_btn.setText("SCAN SOURCE"); self.import_btn.setStyleSheet("")
            # Clear tree placeholder or previous results
            self.tree.clear()
            p = QTreeWidgetItem(self.tree); p.setText(0, "Select a source and click 'SCAN SOURCE' to view media."); p.setFlags(p.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)

    def on_device_selection_change(self, idx): 
        if idx >= 0: self.update_result_ui(self.found_devices[idx], True)
    def update_result_ui(self, dev, multi):
        self.current_detected_path = dev['path']; self.source_input.setText(dev['path']); name = dev.get('display_name', dev.get('type', 'Unknown')); path_short = dev['path']; msg = f"✅ {name}" if not dev['empty'] else f"⚠️ {name} (Empty)"
        if len(path_short) > 35: path_short = path_short[:15] + "..." + path_short[-15:]
        self.result_label.setText(f"<h3 style='color:{'#27AE60' if not dev['empty'] else '#F39C12'}'>{msg}</h3><span style='color:white;'>{path_short}</span>")
        self.result_card.setStyleSheet(f"background-color: {'#2e3b33' if not dev['empty'] else '#4d3d2a'}; border: 2px solid {'#27AE60' if not dev['empty'] else '#F39C12'};"); self.result_card.setVisible(True)
        
        # Sync Camera Profile Dropdown
        idx = self.device_combo.findText(name)
        if idx >= 0: self.device_combo.setCurrentIndex(idx)
        elif name == "Generic Storage": self.device_combo.setCurrentIndex(self.device_combo.findData("Generic_Device"))
        
        if multi:
            self.select_device_box.setVisible(True); self.select_device_box.blockSignals(True); self.select_device_box.clear()
            for d in self.found_devices: self.select_device_box.addItem(f"{d.get('display_name', d.get('type', 'Unknown'))} ({'Empty' if d['empty'] else 'Data'})")
            self.select_device_box.setCurrentIndex(self.found_devices.index(dev)); self.select_device_box.blockSignals(False); self.select_device_box.setStyleSheet(f"background-color: #1e1e1e; color: white; border: 1px solid {'#27AE60' if not dev['empty'] else '#F39C12'};")
    def on_import_click(self):
        debug_log(f"UI: Ingest Click | Mode: {self.ingest_mode}")
        if self.ingest_mode == "scan": self.start_scan()
        else: self.start_transfer()
    def start_scan(self):
        src = self.current_detected_path if self.source_tabs.currentIndex() == 0 else self.source_input.text()
        debug_log(f"UI: Scan Started | Source: {src}")
        if not src or not os.path.exists(src): 
            debug_log("UI: Scan Aborted - Invalid source path.")
            return QMessageBox.warning(self, "Error", "Invalid Source")
        self.import_btn.setEnabled(False); self.status_label.setText("SCANNING SOURCE..."); self.tree.clear(); self.review_group.setVisible(False)
        
        allowed_exts = None
        if self.source_tabs.currentIndex() == 0 and self.found_devices:
             idx = self.select_device_box.currentIndex()
             if idx >= 0 and idx < len(self.found_devices):
                 allowed_exts = self.found_devices[idx].get('exts')
                 debug_log(f"UI: Using device specific extensions: {allowed_exts}")

        self.scanner = IngestScanner(src, self.check_videos_only.isChecked(), allowed_exts)
        self.scanner.finished_signal.connect(self.on_scan_complete); self.scanner.start()
    def on_scan_complete(self, grouped_files):
        self.last_scan_results = grouped_files
        self.refresh_tree_view()

    def open_video_preview(self, item, column):
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if path and os.path.exists(path):
            ext = os.path.splitext(path)[1].upper()
            if ext in DeviceRegistry.VIDEO_EXTS:
                try:
                    if not self.preview_dlg:
                         self.preview_dlg = VideoPreviewDialog(self)
                    
                    self.preview_dlg.load_video(path)
                    self.preview_dlg.show()
                    self.preview_dlg.raise_()
                    self.preview_dlg.activateWindow()
                except Exception as e:
                    error_log(f"Preview Error: {e}")

    def refresh_tree_view(self):
        try:
            self.tree.clear(); total_files = 0
            
            # State 1: Haven't scanned yet (Idle)
            if self.last_scan_results is None:
                p = QTreeWidgetItem(self.tree); p.setText(0, "Select a source and click 'SCAN SOURCE' to view media."); p.setFlags(p.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
                self.review_group.setVisible(True)
                return
            
            # State 2: Scanned, but result is empty
            if not self.last_scan_results:
                p = QTreeWidgetItem(self.tree); p.setText(0, "Scan Complete: No media found on device."); p.setFlags(p.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
                self.review_group.setVisible(True)
                self.ingest_mode = "transfer"
                self.update_transfer_button_text()
                return
            
            sorted_dates = sorted(self.last_scan_results.keys(), reverse=True); video_exts = DeviceRegistry.VIDEO_EXTS
            
            for i, date in enumerate(sorted_dates):
                # Keep UI responsive during large list generation
                if i % 5 == 0: QApplication.processEvents()
                
                all_files = self.last_scan_results[date]
                files = [f for f in all_files if os.path.splitext(f)[1].upper() in video_exts] if self.check_videos_only.isChecked() else all_files
                
                if not files: continue
                total_files += len(files)
                date_item = QTreeWidgetItem(self.tree); date_item.setText(0, f"{date} ({len(files)} files)"); date_item.setFlags(date_item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsAutoTristate); date_item.setCheckState(0, Qt.CheckState.Checked)
                for f in files:
                    f_item = QTreeWidgetItem(date_item); f_item.setText(0, os.path.basename(f)); f_item.setData(0, Qt.ItemDataRole.UserRole, f); f_item.setFlags(f_item.flags() | Qt.ItemFlag.ItemIsUserCheckable); f_item.setCheckState(0, Qt.CheckState.Checked)
            
            if total_files == 0:
                p = QTreeWidgetItem(self.tree)
                msg = "No video files found." if self.check_videos_only.isChecked() else "No matching media found."
                p.setText(0, msg)
                p.setFlags(p.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
            
            self.tree.expandAll()
            self.ingest_mode = "transfer"
            self.status_label.setText(f"FOUND {total_files} FILES. SELECT MEDIA TO TRANSFER.")
            self.update_transfer_button_text()
            
        except Exception as e:
            error_log(f"UI Error in refresh_tree_view: {e}")
            self.status_label.setText("ERROR DISPLAYING FILES")
            
        finally:
            self.review_group.setVisible(True)
            self.import_btn.setEnabled(True)

    def update_transfer_button_text(self):
        if not hasattr(self, 'import_btn'): return
        
        # If we haven't scanned yet, keep default text
        if self.ingest_mode == "scan":
            self.import_btn.setText("SCAN SOURCE"); return
        
        count = 0; root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            date_item = root.child(i)
            # Only count if the item is checkable (actual files/dates)
            if date_item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                for j in range(date_item.childCount()):
                    if date_item.child(j).checkState(0) == Qt.CheckState.Checked: count += 1
        
        if self.ingest_mode == "transfer" and count == 0:
            # Special case: Scan finished but nothing found or nothing selected
            if not self.last_scan_results:
                self.import_btn.setText("SCAN SOURCE (NO MEDIA FOUND)")
            else:
                self.import_btn.setText("START (SELECT FILES FIRST)")
            return

        action = "TRANSFER/TRANSCODE" if self.check_transcode.isChecked() else "TRANSFER"
        self.import_btn.setText(f"START {action} ({count} FILES)")

    def start_transfer(self):
        selected_files = []
        if self.ingest_mode == "transfer":
             root = self.tree.invisibleRootItem()
             for i in range(root.childCount()):
                 date_item = root.child(i)
                 for j in range(date_item.childCount()):
                     f_item = date_item.child(j)
                     if f_item.checkState(0) == Qt.CheckState.Checked:
                         selected_files.append(f_item.data(0, Qt.ItemDataRole.UserRole))
             if not selected_files: return QMessageBox.warning(self, "Error", "No files selected.")

        src = self.current_detected_path if self.source_tabs.currentIndex() == 0 else self.source_input.text()
        dest_list = [self.dest_input.text()]
        if self.dest_input_2.text().strip(): dest_list.append(self.dest_input_2.text().strip())
        if self.dest_input_3.text().strip(): dest_list.append(self.dest_input_3.text().strip())
        
        if not src or not dest_list[0]: return QMessageBox.warning(self, "Error", "Set Source/Main Dest")
        
        self.save_tab_settings(); self.import_btn.setEnabled(False); self.cancel_btn.setEnabled(True); self.status_label.setText("INITIALIZING..."); self.copy_log.clear(); self.transcode_log.clear()
        self.import_btn.setText("INGESTING..."); self.import_btn.setStyleSheet("") # Reset to default style
        if DEBUG_MODE and GUI_LOG_QUEUE:
            for msg in GUI_LOG_QUEUE: self.append_copy_log(msg)
            GUI_LOG_QUEUE.clear()
        self.storage_bar.setVisible(False) 
        tc_enabled = self.check_transcode.isChecked(); tc_settings = self.transcode_widget.get_settings(); use_gpu = self.transcode_widget.is_gpu_enabled()
        if tc_enabled:
            self.transcode_worker = AsyncTranscoder(tc_settings, use_gpu); self.transcode_worker.log_signal.connect(self.append_transcode_log); self.transcode_worker.status_signal.connect(self.transcode_status_label.setText); self.transcode_worker.metrics_signal.connect(self.transcode_status_label.setText); self.transcode_worker.all_finished_signal.connect(self.on_all_transcodes_finished); self.transcode_worker.start(); self.set_transcode_active(True)
        else: self.transcode_status_label.setVisible(False)
        # Determine Camera Name for folder structure
        cam_name = self.device_combo.currentText()
        if self.device_combo.currentData() == "auto":
            # If auto-detect is selected, use the detected name or Generic
            if self.found_devices and self.select_device_box.currentIndex() >= 0:
                cam_name = self.found_devices[self.select_device_box.currentIndex()].get('display_name', "Generic_Device")
            else:
                cam_name = "Generic_Device"
        elif self.device_combo.currentData() == "Generic_Device":
            cam_name = "Generic_Device"

        self.copy_worker = CopyWorker(src, dest_list, self.project_name_input.text(), self.check_date.isChecked(), self.check_dupe.isChecked(), self.check_videos_only.isChecked(), cam_name, self.check_verify.isChecked(), file_list=selected_files)
        self.copy_worker.log_signal.connect(self.append_copy_log); self.copy_worker.progress_signal.connect(self.progress_bar.setValue); self.copy_worker.status_signal.connect(self.status_label.setText); self.copy_worker.speed_signal.connect(self.speed_label.setText); self.copy_worker.finished_signal.connect(self.on_copy_finished)
        self.copy_worker.storage_check_signal.connect(self.update_storage_display_bar)
        if tc_enabled: self.copy_worker.transcode_count_signal.connect(self.transcode_worker.set_total_jobs); self.copy_worker.file_ready_signal.connect(self.queue_for_transcode)
        self.copy_worker.start()
    def update_storage_display_bar(self, needed, free, is_enough):
        self.storage_bar.setVisible(True); needed_gb = needed / (1024**3); free_gb = free / (1024**3)
        if is_enough:
            percent_usage = int((needed / free) * 100) if free > 0 else 100
            self.storage_bar.setValue(percent_usage); self.storage_bar.setFormat(f"Storage: Will use {needed_gb:.2f} GB of {free_gb:.2f} GB Free"); self.storage_bar.setStyleSheet("QProgressBar::chunk { background-color: #27AE60; }")
        else:
            self.storage_bar.setValue(100); self.storage_bar.setFormat(f"⚠️ INSUFFICIENT SPACE! Need {needed_gb:.2f} GB, Have {free_gb:.2f} GB"); self.storage_bar.setStyleSheet("QProgressBar::chunk { background-color: #C0392B; }")
        if not is_enough: SystemNotifier.notify("Ingest Failed", "Insufficient storage space on destination drive.")
    def queue_for_transcode(self, src_path, dest_path, filename):
        if self.transcode_worker:
            # Check if file is already edit-friendly
            settings = self.transcode_widget.get_settings()
            if TranscodeEngine.is_edit_friendly(dest_path, settings.get('v_codec')):
                self.append_copy_log(f"⏩ Smart Skip: {filename} is already {settings.get('v_codec')}.")
                self.transcode_worker.report_skipped(filename)
                return

            base_dir = os.path.dirname(dest_path); tc_dir = os.path.join(base_dir, "Edit_Ready"); os.makedirs(tc_dir, exist_ok=True); name_only = os.path.splitext(filename)[0]; transcode_dest = os.path.join(tc_dir, f"{name_only}_EDIT.mov"); self.transcode_worker.add_job(dest_path, transcode_dest, filename)
    def cancel_import(self):
        if self.copy_worker: self.copy_worker.stop(); self.copy_worker.wait()
        if self.transcode_worker: self.transcode_worker.stop(); self.transcode_worker.wait()
        self.status_label.setText("CANCELLED"); self.import_btn.setEnabled(True); self.cancel_btn.setEnabled(False); self.set_transcode_active(False)
    def on_copy_finished(self, success, msg):
        self.speed_label.setText(""); 
        if success: 
            # 1. Determine Deliverables Destination
            dest_mode = self.app.settings.value("report_dest_mode", "project")
            if dest_mode == "fixed":
                deliverables_path = self.app.settings.value("report_fixed_path", self.dest_input.text())
            elif dest_mode == "custom" and self.report_custom_path:
                deliverables_path = self.report_custom_path
            else: # 'project'
                deliverables_path = self.dest_input.text()
            
            os.makedirs(deliverables_path, exist_ok=True)

            # 2. Generate Report if checked
            if self.check_report.isVisible() and self.check_report.isChecked() and self.copy_worker:
                self.finalize_report(deliverables_path)
            
            # 3. Generate MHL if checked
            if self.check_mhl.isVisible() and self.check_mhl.isChecked() and self.copy_worker:
                try:
                    mhl_path = MHLGenerator.generate(deliverables_path, self.copy_worker.transfer_data, self.project_name_input.text() or "CineBridge")
                    self.append_copy_log(f"🛡️ MHL: {mhl_path}")
                except Exception as e:
                    error_log(f"MHL: Failed to generate: {e}")

        self.status_label.setText(msg)
        
        # If transcode is active, don't enable button yet, wait for transcode worker to notify
        if self.check_transcode.isChecked() and self.transcode_worker:
            self.transcode_worker.set_producer_finished()
            self.import_btn.setText("TRANSCODING...")
        else:
            # ONLY NOTIFY HERE IF NO TRANSCODE IS PENDING
            if success:
                v_msg = " and verified" if self.check_verify.isChecked() else ""
                SystemNotifier.notify("Ingest Complete", f"All files offloaded{v_msg}.")
                dlg = JobReportDialog("Ingest Complete", f"<h3>Ingest Successful</h3><p>All selected media has been offloaded{v_msg}.</p>", self)
                dlg.exec()

            self.import_btn.setEnabled(True); self.cancel_btn.setEnabled(False)
            self.import_btn.setText("COMPLETE"); self.import_btn.setStyleSheet("background-color: #27AE60; color: white;")
            self.set_transcode_active(False)

    def finalize_report(self, deliverables_path):
        project = self.project_name_input.text() or "Unnamed"
        report_name = f"Transfer_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        report_path = os.path.join(deliverables_path, report_name)
        is_visual = self.app.settings.value("feature_visual_report", False, type=bool)
        
        if is_visual:
            video_files = [f['path'] for f in self.copy_worker.transfer_data if f['name'].upper().endswith(tuple(DeviceRegistry.VIDEO_EXTS))]
            if video_files:
                self.status_label.setText(f"PREPARING REPORT (0/{len(video_files)} THUMBS)...")
                self.report_thumbs = {}
                self.report_thumb_worker = ThumbnailWorker(video_files)
                self.report_thumb_worker.status_signal.connect(self.status_label.setText)
                self.report_thumb_worker.thumb_ready.connect(self.on_report_thumb_ready)
                self.report_thumb_worker.finished.connect(lambda: self.generate_final_pdf(report_path, project))
                self.report_thumb_worker.start()
                return 
        self.generate_final_pdf(report_path, project)

    def on_report_thumb_ready(self, path, image):
        ba = QByteArray(); buffer = QBuffer(ba); buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        image.save(buffer, "PNG")
        self.report_thumbs[os.path.basename(path)] = ba.toBase64().data().decode()

    def generate_final_pdf(self, report_path, project):
        try:
            thumbs = getattr(self, 'report_thumbs', None)
            ReportGenerator.generate_pdf(report_path, self.copy_worker.transfer_data, project, thumbs)
            self.append_copy_log(f"📝 Report: {report_path}")
            if hasattr(self, 'report_thumbs'): del self.report_thumbs
            self.status_label.setText("✅ Ingest & Report Complete!")
        except Exception as e: error_log(f"Report: Failed to generate PDF: {e}")

    def on_all_transcodes_finished(self):
        SystemNotifier.notify("Job Complete", "Ingest and Transcoding finished.")
        self.import_btn.setEnabled(True); self.cancel_btn.setEnabled(False)
        self.import_btn.setText("COMPLETE"); self.import_btn.setStyleSheet("background-color: #27AE60; color: white;")
        self.set_transcode_active(False); self.transcode_status_label.setText("All Transcodes Complete!")
        
        v_msg = " and verified" if self.check_verify.isChecked() else ""
        dlg = JobReportDialog("Job Complete", f"<h3>Job Successful</h3><p>All ingest{v_msg} and transcode operations finished successfully.<br>Your media is ready for edit.</p>", self)
        dlg.exec()
    def save_tab_settings(self):
        s = self.app.settings; s.setValue("last_source", self.source_input.text()); s.setValue("last_dest", self.dest_input.text()); s.setValue("sort_date", self.check_date.isChecked()); s.setValue("skip_dupe", self.check_dupe.isChecked()); s.setValue("videos_only", self.check_videos_only.isChecked()); s.setValue("transcode_dnx", self.check_transcode.isChecked()); s.setValue("verify_copy", self.check_verify.isChecked()); s.setValue("gen_report", self.check_report.isChecked()); s.setValue("gen_mhl", self.check_mhl.isChecked())
        s.setValue("show_copy_log", self.copy_log.isVisible()); s.setValue("show_trans_log", self.transcode_log.isVisible())
    def load_tab_settings(self):
        s = self.app.settings; self.source_input.setText(s.value("last_source", "")); self.dest_input.setText(s.value("last_dest", "")); self.check_date.setChecked(s.value("sort_date", True, type=bool)); self.check_dupe.setChecked(s.value("skip_dupe", True, type=bool)); self.check_videos_only.setChecked(s.value("videos_only", False, type=bool)); self.check_transcode.setChecked(s.value("transcode_dnx", False, type=bool)); self.check_verify.setChecked(s.value("verify_copy", False, type=bool)); self.check_report.setChecked(s.value("gen_report", True, type=bool)); self.check_mhl.setChecked(s.value("gen_mhl", False, type=bool))
        show_copy = s.value("show_copy_log", True, type=bool); show_trans = s.value("show_trans_log", False, type=bool); self.toggle_logs(show_copy, show_trans); self.toggle_transcode_ui(self.check_transcode.isChecked())

class ConvertTab(QWidget):
    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True); self.is_processing = False; self.thumb_workers = []
        layout = QVBoxLayout(); layout.setSpacing(15); layout.setContentsMargins(20, 20, 20, 20); self.setLayout(layout)
        
        self.settings = TranscodeSettingsWidget("1. Conversion Settings", mode="general")
        layout.addWidget(self.settings)
        
        # 2. Input Media
        input_group = QGroupBox("2. Input Media"); input_lay = QVBoxLayout()
        self.btn_browse = QPushButton("Select Video Files..."); self.btn_browse.clicked.connect(self.browse_files); input_lay.addWidget(self.btn_browse)
        self.btn_browse.setToolTip("Add video files to the batch conversion queue.")
        self.drop_area = QLabel("\n⬇️\n\nDRAG & DROP VIDEO FILES HERE\n\n"); self.drop_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_area.setStyleSheet("QLabel { border: 3px dashed #666; border-radius: 10px; background-color: #2b2b2b; color: #aaa; font-weight: bold; } QLabel:hover { border-color: #3498DB; background-color: #333; color: white; }")
        input_lay.addWidget(self.drop_area, 1); input_group.setLayout(input_lay); layout.addWidget(input_group, 1)

        # 3. Destination
        out_group = QGroupBox("3. Destination (Optional)"); out_lay = QHBoxLayout()
        self.out_input = QLineEdit(); self.out_input.setPlaceholderText("Default: Creates 'Converted' folder next to source files")
        self.btn_browse_out = QPushButton("Browse..."); self.btn_browse_out.clicked.connect(self.browse_dest)
        self.btn_clear_out = QPushButton("Reset"); self.btn_clear_out.clicked.connect(self.out_input.clear)
        out_lay.addWidget(self.out_input); out_lay.addWidget(self.btn_browse_out); out_lay.addWidget(self.btn_clear_out); out_group.setLayout(out_lay); layout.addWidget(out_group)
        
        # 4. Batch Queue
        queue_group = QGroupBox("4. Batch Queue"); queue_lay = QVBoxLayout()
        self.list = QListWidget(); self.list.setMaximumHeight(150); self.list.setDragDropMode(QAbstractItemView.DragDropMode.DropOnly); self.list.setIconSize(QSize(96, 54)); self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu); self.list.customContextMenuRequested.connect(self.show_context_menu); queue_lay.addWidget(self.list)
        
        dash_frame = QFrame(); dash_frame.setObjectName("DashFrame"); dash_layout = QVBoxLayout(); dash_frame.setLayout(dash_layout)
        dash_row = QHBoxLayout(); self.status_label = QLabel("Waiting..."); self.status_label.setStyleSheet("color: #888;"); dash_row.addWidget(self.status_label); dash_row.addStretch(); dash_layout.addLayout(dash_row)
        
        # System Stats Row
        self.stats_row = QWidget(); self.stats_row.setVisible(False); sr_lay = QHBoxLayout(self.stats_row); sr_lay.setContentsMargins(0,0,0,0); sr_lay.setSpacing(10)
        self.cpu_load_lbl = QLabel("CPU: 0%"); self.cpu_load_lbl.setStyleSheet("color: #E74C3C; font-weight: bold; font-size: 11px;")
        self.cpu_temp_lbl = QLabel(""); self.cpu_temp_lbl.setStyleSheet("color: #E74C3C; font-size: 11px;")
        self.gpu_load_lbl = QLabel(""); self.gpu_load_lbl.setStyleSheet("color: #3498DB; font-weight: bold; font-size: 11px;")
        self.gpu_temp_lbl = QLabel(""); self.gpu_temp_lbl.setStyleSheet("color: #3498DB; font-size: 11px;")
        sr_lay.addStretch(); sr_lay.addWidget(self.cpu_load_lbl); sr_lay.addWidget(self.cpu_temp_lbl); sr_lay.addWidget(self.gpu_load_lbl); sr_lay.addWidget(self.gpu_temp_lbl); sr_lay.addStretch()
        dash_layout.addWidget(self.stats_row)

        self.pbar = QProgressBar(); self.pbar.setTextVisible(True); dash_layout.addWidget(self.pbar); queue_lay.addWidget(dash_frame)
        
        h = QHBoxLayout(); b_clr = QPushButton("Clear Queue"); b_clr.clicked.connect(self.list.clear)
        self.btn_go = QPushButton("START BATCH"); self.btn_go.setObjectName("StartBtn"); self.btn_go.clicked.connect(self.on_btn_click)
        self.btn_go.setToolTip("Start the batch conversion process for all files in the queue.")
        h.addWidget(b_clr); h.addWidget(self.btn_go); queue_lay.addLayout(h); queue_group.setLayout(queue_lay); layout.addWidget(queue_group); layout.addStretch()
                
    def update_load_display(self, stats):
        self.cpu_load_lbl.setText(f"CPU: {stats['cpu_load']}%")
        self.cpu_temp_lbl.setText(f"({stats['cpu_temp']}°C)" if stats['cpu_temp'] > 0 else "")
        if stats['has_gpu']:
            vendor = stats.get('gpu_vendor', 'GPU')
            self.gpu_load_lbl.setText(f"{vendor}: {stats['gpu_load']}%")
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

    def toggle_ui_state(self, running):
        self.is_processing = running
        self.stats_row.setVisible(running)
        if running: self.btn_go.setText("STOP BATCH"); self.btn_go.setObjectName("StopBtn")
        else: self.btn_go.setText("START BATCH"); self.btn_go.setObjectName("StartBtn")
        self.btn_go.style().unpolish(self.btn_go); self.btn_go.style().polish(self.btn_go)

    def start(self):
        files = [self.list.item(i).text() for i in range(self.list.count())]
        if not files: return QMessageBox.warning(self, "Empty", "Queue is empty.")
        self.toggle_ui_state(True); dest_folder = self.out_input.text().strip(); use_gpu = self.settings.is_gpu_enabled()
        self.worker = BatchTranscodeWorker(files, dest_folder, self.settings.get_settings(), mode="convert", use_gpu=use_gpu)
        self.worker.progress_signal.connect(self.pbar.setValue); self.worker.status_signal.connect(self.status_label.setText); self.worker.log_signal.connect(lambda s: self.status_label.setText(s)); self.worker.finished_signal.connect(self.on_finished); self.worker.start()

    def start_thumb_process(self, files):
        worker = ThumbnailWorker(files); worker.thumb_ready.connect(self.update_thumbnail)
        worker.finished.connect(lambda: self.thumb_workers.remove(worker) if worker in self.thumb_workers else None)
        worker.start(); self.thumb_workers.append(worker)

    def update_thumbnail(self, path, image):
        pixmap = QPixmap.fromImage(image)
        items = self.list.findItems(path, Qt.MatchFlag.MatchExactly)
        for item in items: item.setIcon(QIcon(pixmap))

    def stop(self):
        if self.worker: self.worker.stop(); self.status_label.setText("Stopping...")

    def on_finished(self):
        SystemNotifier.notify("Conversion Complete", "Batch transcode finished.")
        self.toggle_ui_state(False); self.status_label.setText("Batch Complete!"); dest = self.out_input.text(); msg = f"Files saved to:\n{dest}" if dest else "Files saved to 'Converted' folder next to the source file(s)."; 
        dlg = JobReportDialog("Conversion Complete", f"<h3>Transcode Successful</h3><p>All files in the queue have been converted.<br>Your media is ready for edit.</p>", self)
        dlg.exec()

    def show_context_menu(self, pos):
        item = self.list.itemAt(pos)
        if item:
            menu = QMenu(self); action = QAction("Inspect Media Info", self); action.triggered.connect(lambda: self.inspect_file(item)); menu.addAction(action); menu.exec(self.list.mapToGlobal(pos))

    def inspect_file(self, item):
        path = item.text()
        if os.path.exists(path):
            info = MediaInfoExtractor.get_info(path); dlg = MediaInfoDialog(info, self); dlg.exec()

class DeliveryTab(QWidget):
    def __init__(self):
        super().__init__(); self.setAcceptDrops(True); self.is_processing = False
        layout = QVBoxLayout(); layout.setSpacing(15); layout.setContentsMargins(20, 20, 20, 20); self.setLayout(layout)
        
        self.settings = TranscodeSettingsWidget("1. Delivery Settings", mode="delivery")
        self.settings.preset_combo.setCurrentText("H.264 / AVC (Standard)")
        layout.addWidget(self.settings)
        
        # 2. Master File
        master_group = QGroupBox("2. Master File"); master_lay = QVBoxLayout()
        self.inp_file = FileDropLineEdit(); self.inp_file.setPlaceholderText("Drag Master File Here or Browse")
        self.btn_sel_master = QPushButton("Select Master File..."); self.btn_sel_master.clicked.connect(lambda: self.inp_file.setText(QFileDialog.getOpenFileName(self, "Select Master File")[0]))
        self.btn_sel_master.setToolTip("Select the high-quality master file for final delivery rendering.")
        self.drop_area = QLabel("\n⬇️\n\nDRAG MASTER FILE HERE\n\n"); self.drop_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_area.setStyleSheet("QLabel { border: 3px dashed #666; border-radius: 10px; background-color: #2b2b2b; color: #aaa; font-weight: bold; } QLabel:hover { border-color: #3498DB; background-color: #333; color: white; }")
        master_lay.addWidget(self.btn_sel_master); master_lay.addWidget(self.inp_file); master_lay.addWidget(self.drop_area, 1); master_group.setLayout(master_lay); layout.addWidget(master_group, 1)

        # 3. Destination
        dest_group = QGroupBox("3. Destination (Optional)"); dest_lay = QHBoxLayout()
        self.inp_dest = QLineEdit(); self.inp_dest.setPlaceholderText("Default: Creates 'Final_Render' folder next to master")
        self.btn_b2 = QPushButton("Browse..."); self.btn_b2.clicked.connect(lambda: self.inp_dest.setText(QFileDialog.getExistingDirectory(self, "Pick a Destination")))
        dest_lay.addWidget(self.inp_dest); dest_lay.addWidget(self.btn_b2); dest_group.setLayout(dest_lay); layout.addWidget(dest_group)
        
        # 4. Render Dashboard
        dash_frame = QFrame(); dash_frame.setObjectName("DashFrame"); dash_layout = QVBoxLayout(); dash_frame.setLayout(dash_layout)
        self.status_label = QLabel("Ready to Render"); dash_layout.addWidget(self.status_label)
        self.pbar = QProgressBar(); self.pbar.setTextVisible(True); dash_layout.addWidget(self.pbar); layout.addWidget(dash_frame)
        
        self.btn_go = QPushButton("GENERATE DELIVERY MASTER"); self.btn_go.setObjectName("StartBtn"); self.btn_go.setMinimumHeight(50); self.btn_go.clicked.connect(self.on_btn_click)
        self.btn_go.setToolTip("Start the final render using delivery-optimized presets.")
        layout.addWidget(self.btn_go); layout.addStretch()

    def dragEnterEvent(self, e): 
        if e.mimeData().hasUrls(): e.accept()

    def dropEvent(self, e):
        urls = e.mimeData().urls() 
        if urls:
            fpath = urls[0].toLocalFile()
            if fpath.lower().endswith(('.mp4','.mov','.mkv','.avi')): self.inp_file.setText(fpath)

    def on_btn_click(self):
        if self.is_processing: self.stop() 
        else: self.start()

    def toggle_ui_state(self, running):
        self.is_processing = running
        if running: self.btn_go.setText("STOP RENDER"); self.btn_go.setObjectName("StopBtn")
        else: self.btn_go.setText("RENDER"); self.btn_go.setObjectName("StartBtn")
        self.btn_go.style().unpolish(self.btn_go); self.btn_go.style().polish(self.btn_go)

    def start(self):
        if not self.inp_file.text(): return QMessageBox.warning(self, "Missing Info", "Please select a master file.")
        self.toggle_ui_state(True); use_gpu = self.settings.is_gpu_enabled(); dest_folder = self.inp_dest.text().strip()
        self.worker = BatchTranscodeWorker([self.inp_file.text()], dest_folder, self.settings.get_settings(), mode="delivery", use_gpu=use_gpu)
        self.worker.progress_signal.connect(self.pbar.setValue); self.worker.status_signal.connect(self.status_label.setText); self.worker.finished_signal.connect(self.on_finished); self.worker.start()

    def stop(self):
        if self.worker: self.worker.stop(); self.status_label.setText("Stopping...")

    def on_finished(self):
        SystemNotifier.notify("Render Complete", "Delivery render finished.")
        self.toggle_ui_state(False); self.status_label.setText("Delivery Render Complete!"); dest = self.inp_dest.text(); 
        dlg = JobReportDialog("Render Complete", f"<h3>Final Render Successful</h3><p>Your master file has been rendered and is ready for distribution.</p>", self)
        dlg.exec()

class WatchTab(QWidget):
    def __init__(self):
        super().__init__(); layout = QVBoxLayout(); layout.setSpacing(15); layout.setContentsMargins(20, 20, 20, 20); self.setLayout(layout)
        self.is_active = False; self.processed_files = set(); self.timer = QTimer(); self.timer.timeout.connect(self.check_folder)
        self.monitored_files = {}; self.STABILITY_THRESHOLD = 3.0
        
        # 1. Service Configuration
        conf_group = QGroupBox("1. Service Configuration"); conf_lay = QVBoxLayout()
        stab_layout = QHBoxLayout(); stab_layout.addWidget(QLabel("File Stability Check (Seconds):"))
        self.spin_stability = QSpinBox(); self.spin_stability.setRange(1, 60); self.spin_stability.setValue(int(self.STABILITY_THRESHOLD)); self.spin_stability.valueChanged.connect(self.update_threshold)
        self.spin_stability.setToolTip("Wait this many seconds for a file to stop changing size before starting transcode (useful for slow network copies).")
        stab_layout.addWidget(self.spin_stability); stab_layout.addStretch(); conf_lay.addLayout(stab_layout)
        self.settings = TranscodeSettingsWidget(mode="general"); conf_lay.addWidget(self.settings); conf_group.setLayout(conf_lay); layout.addWidget(conf_group)

        # 2. Folder Selection
        fold_group = QGroupBox("2. Folder Selection"); fold_lay = QFormLayout()
        self.inp_watch = QLineEdit(); self.btn_watch = QPushButton("Browse..."); self.btn_watch.clicked.connect(self.browse_watch)
        w_row = QHBoxLayout(); w_row.addWidget(self.inp_watch); w_row.addWidget(self.btn_watch)
        self.inp_dest = QLineEdit(); self.btn_dest = QPushButton("Browse..."); self.btn_dest.clicked.connect(self.browse_dest)
        d_row = QHBoxLayout(); d_row.addWidget(self.inp_dest); d_row.addWidget(self.btn_dest)
        fold_lay.addRow("Watch Folder:", w_row); fold_lay.addRow("Destination:", d_row); fold_group.setLayout(fold_lay); layout.addWidget(fold_group)

        # 3. Service Dashboard
        dash_frame = QFrame(); dash_frame.setObjectName("DashFrame"); dash_layout = QVBoxLayout(); dash_frame.setLayout(dash_layout)
        self.status_label = QLabel("Watch Folder: INACTIVE"); self.status_label.setStyleSheet("color: #888;"); dash_layout.addWidget(self.status_label)
        self.pbar = QProgressBar(); self.pbar.setVisible(False); dash_layout.addWidget(self.pbar); layout.addWidget(dash_frame)

        self.btn_toggle = QPushButton("ACTIVATE WATCH FOLDER"); self.btn_toggle.setObjectName("StartBtn"); self.btn_toggle.setMinimumHeight(50); self.btn_toggle.clicked.connect(self.toggle_watch)
        self.btn_toggle.setToolTip("Enable or disable the automated background watch folder service.")
        layout.addWidget(self.btn_toggle)
        layout.addStretch()

    def update_threshold(self, val):
        self.STABILITY_THRESHOLD = float(val)

    def browse_watch(self):
        d = QFileDialog.getExistingDirectory(self, "Select Folder to Watch")
        if d: self.inp_watch.setText(d)
    def browse_dest(self):
        d = QFileDialog.getExistingDirectory(self, "Pick a Destination")
        if d: self.inp_dest.setText(d)

    def toggle_watch(self):
        if self.is_active:
            self.is_active = False; self.timer.stop(); self.btn_toggle.setText("ACTIVATE WATCH FOLDER"); self.btn_toggle.setObjectName("StartBtn")
            self.status_label.setText("Watch Folder: INACTIVE"); self.status_label.setStyleSheet("color: #888;")
            self.monitored_files.clear()
        else:
            if not self.inp_watch.text() or not self.inp_dest.text(): return QMessageBox.warning(self, "Error", "Set Watch/Dest folders.")
            self.is_active = True; self.timer.start(2000); self.btn_toggle.setText("DEACTIVATE WATCH FOLDER"); self.btn_toggle.setObjectName("StopBtn")
            self.status_label.setText("Watch Folder: ACTIVE - Scanning..."); self.status_label.setStyleSheet("color: #27AE60;")
        self.btn_toggle.style().unpolish(self.btn_toggle); self.btn_toggle.style().polish(self.btn_toggle)

    def check_folder(self):
        watch_path = self.inp_watch.text()
        if not os.path.exists(watch_path): return
        
        # 1. Scan for new candidates
        current_time = datetime.now().timestamp()
        try:
            candidates = []
            for f in os.listdir(watch_path):
                full = os.path.join(watch_path, f)
                if os.path.isfile(full) and full not in self.processed_files:
                    if f.lower().endswith(tuple(x.lower() for x in DeviceRegistry.VIDEO_EXTS)):
                        candidates.append(full)
            
            # 2. Update monitored files
            ready_to_process = []
            
            for path in candidates:
                try:
                    size = os.path.getsize(path)
                    if path not in self.monitored_files:
                        # New file found
                        self.monitored_files[path] = {'size': size, 'stable_since': current_time}
                        debug_log(f"Watch: Found new file {os.path.basename(path)}")
                    else:
                        # Existing monitored file
                        data = self.monitored_files[path]
                        if size != data['size']:
                            # Size changed, reset timer
                            data['size'] = size
                            data['stable_since'] = current_time
                        elif (current_time - data['stable_since']) >= self.STABILITY_THRESHOLD:
                            # Stable!
                            ready_to_process.append(path)
                            del self.monitored_files[path]
                except: pass
            
            # 3. Process stable files
            if ready_to_process:
                self.status_label.setText(f"Watch Folder: Processing {len(ready_to_process)} new files...")
                self.start_batch(ready_to_process)
                
        except Exception as e:
            error_log(f"Watch Cycle Error: {e}")

    def start_batch(self, files):
        dest = self.inp_dest.text()
        self.worker = BatchTranscodeWorker(files, dest, self.settings.get_settings(), mode="convert", use_gpu=self.settings.is_gpu_enabled())
        self.worker.progress_signal.connect(self.pbar.setValue); self.worker.finished_signal.connect(self.on_batch_finished)
        self.pbar.setVisible(True); self.timer.stop() # Pause polling
        for f in files: self.processed_files.add(f)
        self.worker.start()

    def on_batch_finished(self):
        self.pbar.setVisible(False); self.timer.start(2000) # Resume polling
        self.status_label.setText("Watch Folder: ACTIVE - Scanning...")
        SystemNotifier.notify("Watch Folder", "New proxies processed.")
