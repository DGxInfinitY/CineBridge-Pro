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

        # 2. Destination Group
        dest_group = QGroupBox("2. Destination"); self.dest_inner = QVBoxLayout()
        self.project_name_input = QLineEdit(); self.project_name_input.setPlaceholderText("Project Name")
        self.dest_input = QLineEdit(); self.browse_dest_btn = QPushButton("Browse"); self.browse_dest_btn.clicked.connect(self.browse_dest)
        self.dest_inner.addWidget(QLabel("Project Name:")); self.dest_inner.addWidget(self.project_name_input)
        self.dest_lbl_1 = QLabel("Main Location:"); self.dest_inner.addWidget(self.dest_lbl_1)
        self.dest_inner.addWidget(self.dest_input); self.dest_inner.addWidget(self.browse_dest_btn)
        
        # Pro Destinations
        self.dest_2_wrap = QWidget(); d2_lay = QVBoxLayout(); d2_lay.setContentsMargins(0,0,0,0); self.dest_2_wrap.setLayout(d2_lay)
        self.dest_input_2 = QLineEdit(); self.btn_b2 = QPushButton("Browse (Dest 2)"); self.btn_b2.clicked.connect(lambda: self.browse_dest_field(self.dest_input_2))
        d2_lay.addWidget(QLabel("Destination 2:")); d2_lay.addWidget(self.dest_input_2); d2_lay.addWidget(self.btn_b2)
        self.dest_inner.addWidget(self.dest_2_wrap); self.dest_2_wrap.setVisible(False)

        self.dest_3_wrap = QWidget(); d3_lay = QVBoxLayout(); d3_lay.setContentsMargins(0,0,0,0); self.dest_3_wrap.setLayout(d3_lay)
        self.dest_input_3 = QLineEdit(); self.btn_b3 = QPushButton("Browse (Dest 3)"); self.btn_b3.clicked.connect(lambda: self.browse_dest_field(self.dest_input_3))
        d3_lay.addWidget(QLabel("Destination 3:")); d3_lay.addWidget(self.dest_input_3); d3_lay.addWidget(self.btn_b3)
        self.dest_inner.addWidget(self.dest_3_wrap); self.dest_3_wrap.setVisible(False)
        self.dest_inner.addStretch(); dest_group.setLayout(self.dest_inner)

        # 3. Settings Group
        settings_group = QGroupBox("3. Processing Settings"); settings_layout = QVBoxLayout()
        logic_row = QHBoxLayout(); logic_row.addWidget(QLabel("Camera Profile:")); self.device_combo = QComboBox()
        self.device_combo.setToolTip("Select a specific camera profile or use Auto-Detect.")
        self.device_combo.addItem("Auto-Detect", "auto")
        for profile_name in sorted(DeviceRegistry.PROFILES.keys()): self.device_combo.addItem(profile_name, profile_name)
        self.device_combo.addItem("Generic Storage", "Generic_Device"); logic_row.addWidget(self.device_combo); settings_layout.addLayout(logic_row)

        rules_grid = QGridLayout()
        self.check_date = QCheckBox("Sort Date"); self.check_date.setToolTip("Organize media by capture date.")
        self.check_dupe = QCheckBox("Skip Dupes"); self.check_dupe.setToolTip("Skip identical existing files.")
        self.check_videos_only = QCheckBox("Video Only"); self.check_videos_only.toggled.connect(self.refresh_tree_view)
        self.check_verify = QCheckBox("Verify Copy"); self.check_verify.setStyleSheet("color: #27AE60; font-weight: bold;")
        self.check_report = QCheckBox("Gen Report"); self.check_mhl = QCheckBox("Gen MHL")
        self.check_transcode = QCheckBox("Enable Transcode"); self.check_transcode.setStyleSheet("color: #E67E22; font-weight: bold;"); self.check_transcode.toggled.connect(self.toggle_transcode_ui)
        rules_grid.addWidget(self.check_date, 0, 0); rules_grid.addWidget(self.check_dupe, 0, 1); rules_grid.addWidget(self.check_videos_only, 0, 2)
        rules_grid.addWidget(self.check_verify, 1, 0); rules_grid.addWidget(self.check_report, 1, 1); rules_grid.addWidget(self.check_mhl, 1, 2)
        rules_grid.addWidget(self.check_transcode, 2, 0); settings_layout.addLayout(rules_grid)
        
        config_btns = QHBoxLayout()
        self.btn_config_trans = QPushButton("Configure Transcode..."); self.btn_config_trans.setVisible(False); self.btn_config_trans.clicked.connect(self.open_transcode_config)
        self.btn_config_reports = QPushButton("Reports Settings..."); self.btn_config_reports.setVisible(False); self.btn_config_reports.clicked.connect(self.open_report_config)
        config_btns.addWidget(self.btn_config_trans); config_btns.addWidget(self.btn_config_reports); settings_layout.addLayout(config_btns)
        
        self.transcode_widget = TranscodeSettingsWidget(mode="general"); self.report_custom_path = ""
        settings_layout.addStretch(); settings_group.setLayout(settings_layout)
        
        # 4. Review Group
        self.review_group = QGroupBox("4. Select Media"); review_lay = QVBoxLayout()
        self.tree = QTreeWidget(); self.tree.setHeaderLabel("Media Review"); self.tree.itemChanged.connect(self.update_transfer_button_text); self.tree.itemDoubleClicked.connect(self.open_video_preview)
        review_lay.addWidget(self.tree)
        hint_lbl = QLabel("💡 Hint: Double-click a video file to preview it."); hint_lbl.setStyleSheet("color: #777; font-style: italic; font-size: 10px;"); hint_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        review_lay.addWidget(hint_lbl); review_lay.addStretch(); self.review_group.setLayout(review_lay)

        # Main Layout Assembly
        grid = QGridLayout(); grid.addWidget(source_group, 0, 0); grid.addWidget(dest_group, 0, 1); grid.addWidget(settings_group, 1, 0); grid.addWidget(self.review_group, 1, 1)
        grid.setRowStretch(1, 1); self.layout.addLayout(grid)

        # Dashboard
        dash_frame = QFrame(); dash_frame.setObjectName("DashFrame"); dash_layout = QVBoxLayout(dash_frame)
        top_row = QHBoxLayout(); self.status_label = QLabel("READY"); self.speed_label = QLabel(""); top_row.addWidget(self.status_label, 1); top_row.addWidget(self.speed_label); dash_layout.addLayout(top_row)
        self.storage_bar = QProgressBar(); self.storage_bar.setVisible(False); dash_layout.addWidget(self.storage_bar)
        self.progress_bar = QProgressBar(); dash_layout.addWidget(self.progress_bar)
        self.transcode_status_label = QLabel(""); self.transcode_status_label.setVisible(False); self.transcode_status_label.setStyleSheet("color: #E67E22; font-weight: bold;"); dash_layout.addWidget(self.transcode_status_label)
        
        self.stats_row = QWidget(); self.stats_row.setVisible(False); sr_lay = QHBoxLayout(self.stats_row); sr_lay.setContentsMargins(0,0,0,0)
        self.cpu_load_lbl = QLabel("CPU: 0%"); self.cpu_temp_lbl = QLabel(""); self.gpu_load_lbl = QLabel(""); self.gpu_temp_lbl = QLabel("")
        sr_lay.addWidget(self.cpu_load_lbl); sr_lay.addWidget(self.cpu_temp_lbl); sr_lay.addWidget(self.gpu_load_lbl); sr_lay.addWidget(self.gpu_temp_lbl); dash_layout.addWidget(self.stats_row)
        self.layout.addWidget(dash_frame)

        btn_layout = QHBoxLayout(); self.import_btn = QPushButton("SCAN SOURCE"); self.import_btn.setObjectName("StartBtn"); self.import_btn.clicked.connect(self.on_import_click)
        self.cancel_btn = QPushButton("STOP"); self.cancel_btn.setObjectName("StopBtn"); self.cancel_btn.setEnabled(False); self.cancel_btn.clicked.connect(self.cancel_import)
        self.clear_logs_btn = QPushButton("Clear Logs"); self.clear_logs_btn.clicked.connect(self.clear_logs)
        btn_layout.addWidget(self.import_btn); btn_layout.addWidget(self.cancel_btn); btn_layout.addWidget(self.clear_logs_btn); self.layout.addLayout(btn_layout)
        
        self.splitter = QSplitter(Qt.Orientation.Vertical); self.copy_log = QTextEdit(); self.transcode_log = QTextEdit()
        self.copy_log.setReadOnly(True); self.copy_log.setMinimumHeight(40); self.copy_log.setStyleSheet("background-color: #1e1e1e; color: #2ECC71; font-family: Consolas; font-size: 11px;")
        self.copy_log.setPlaceholderText("Copy and Verification Log...")
        self.transcode_log.setReadOnly(True); self.transcode_log.setMinimumHeight(40); self.transcode_log.setStyleSheet("background-color: #2c2c2c; color: #3498DB; font-family: Consolas; font-size: 11px;")
        self.transcode_log.setPlaceholderText("Transcode and Processing Log...")
        self.transcode_log.setVisible(False)
        self.splitter.addWidget(self.copy_log); self.splitter.addWidget(self.transcode_log); self.layout.addWidget(self.splitter, 1)

    # IngestTab Methods
    def clear_logs(self): self.copy_log.clear(); self.transcode_log.clear()
    def toggle_logs(self, show_copy, show_transcode): self.copy_log.setVisible(show_copy); self.transcode_log.setVisible(show_transcode); self.splitter.setVisible(show_copy or show_transcode)
    def toggle_transcode_ui(self, checked): self.btn_config_trans.setVisible(checked); self.transcode_status_label.setVisible(checked); self.update_transfer_button_text()
    def open_transcode_config(self): TranscodeConfigDialog(self.transcode_widget, self).exec()
    def open_report_config(self):
        d = QFileDialog.getExistingDirectory(self, "Select Report Folder", self.report_custom_path or self.dest_input.text())
        if d: self.report_custom_path = d
    def update_load_display(self, stats):
        self.cpu_load_lbl.setText(f"CPU: {stats['cpu_load']}%")
        self.cpu_temp_lbl.setText(f"({stats['cpu_temp']}°C)" if stats['cpu_temp'] > 0 else "")
        if stats['has_gpu']:
            v = stats.get('gpu_vendor', 'GPU'); self.gpu_load_lbl.setText(f"{v}: {stats['gpu_load']}% "); self.gpu_temp_lbl.setText(f"({stats['gpu_temp']}°C)" if stats['gpu_temp'] > 0 else "")
            self.gpu_load_lbl.setVisible(True); self.gpu_temp_lbl.setVisible(True)
        else: self.gpu_load_lbl.setVisible(False); self.gpu_temp_lbl.setVisible(False)
    def set_transcode_active(self, active): self.stats_row.setVisible(active); self.transcode_status_label.setVisible(active)
    def browse_source(self):
        d = QFileDialog.getExistingDirectory(self, "Source", self.source_input.text())
        if d: self.source_input.setText(d)
    def browse_dest(self):
        d = QFileDialog.getExistingDirectory(self, "Pick a Destination", self.dest_input.text())
        if d: self.dest_input.setText(d)
    def browse_dest_field(self, field):
        d = QFileDialog.getExistingDirectory(self, "Pick a Destination", field.text())
        if d: field.setText(d)
    def update_pro_features_ui(self, show_multi, show_visual):
        self.dest_lbl_1.setText("Main Location:" if show_multi else "Location:")
        self.dest_2_wrap.setVisible(show_multi); self.dest_3_wrap.setVisible(show_multi)
        show_pdf = self.app.settings.value("feature_pdf_report", True, type=bool)
        show_mhl = self.app.settings.value("feature_mhl", False, type=bool)
        self.check_report.setVisible(show_pdf); self.check_report.setText("Gen Visual Report" if show_visual else "Gen Report")
        self.check_mhl.setVisible(show_mhl); self.btn_config_reports.setVisible((show_pdf or show_mhl) and self.app.settings.value("report_dest_mode") == "custom")
    def append_copy_log(self, text): self.copy_log.append(text); sb = self.copy_log.verticalScrollBar(); sb.setValue(sb.maximum())
    def append_transcode_log(self, text): self.transcode_log.append(text); sb = self.transcode_log.verticalScrollBar(); sb.setValue(sb.maximum())
    def run_auto_scan(self): self.auto_info_label.setText("Scanning..."); self.scan_btn.setEnabled(False); self.scan_watchdog.start(30000); self.scan_worker = ScanWorker(); self.scan_worker.finished_signal.connect(self.on_scan_finished); self.scan_worker.start()
    def on_scan_timeout(self):
        if hasattr(self, 'scan_worker') and self.scan_worker.isRunning(): self.scan_worker.terminate(); self.auto_info_label.setText("Scan Timed Out")
    def on_scan_finished(self, results):
        self.scan_watchdog.stop(); self.found_devices = results; self.scan_btn.setEnabled(True)
        if results: self.auto_info_label.setText("✅ Scan Complete"); self.update_result_ui(results[0], len(results)>1)
        else: self.result_card.setVisible(False); self.auto_info_label.setText("No devices")
    def reset_ingest_mode(self):
        if self.ingest_mode != "scan":
            self.ingest_mode = "scan"; self.last_scan_results = None; self.update_transfer_button_text()
            self.import_btn.setText("SCAN SOURCE"); self.import_btn.setStyleSheet(""); self.tree.clear()
    def on_device_selection_change(self, idx):
        if idx >= 0: self.update_result_ui(self.found_devices[idx], True)
    def update_result_ui(self, dev, multi):
        self.current_detected_path = dev['path']; self.source_input.setText(dev['path'])
        name = dev.get('display_name', 'Unknown'); path_short = dev['path']
        msg = f"✅ {name}" if not dev['empty'] else f"⚠️ {name} (Empty)"
        if len(path_short) > 35: path_short = path_short[:15] + "..." + path_short[-15:]
        
        self.result_label.setText(f"<h3 style='color:{'#27AE60' if not dev['empty'] else '#F39C12'}'>{msg}</h3><span style='color:white;'>{path_short}</span>")
        self.result_card.setStyleSheet(f"background-color: {'#2e3b33' if not dev['empty'] else '#4d3d2a'}; border: 2px solid {'#27AE60' if not dev['empty'] else '#F39C12'}; border-radius: 8px;")
        self.result_card.setVisible(True)
        
        # Sync Camera Profile Dropdown
        idx = self.device_combo.findText(name)
        if idx >= 0: self.device_combo.setCurrentIndex(idx)
        elif name == "Generic Storage": self.device_combo.setCurrentIndex(self.device_combo.findData("Generic_Device"))
        
        if multi:
            self.select_device_box.blockSignals(True)
            self.select_device_box.setVisible(True); self.select_device_box.clear()
            for d in self.found_devices:
                self.select_device_box.addItem(f"{d.get('display_name', 'Unknown')} ({'Empty' if d['empty'] else 'Data'})")
            self.select_device_box.setCurrentIndex(self.found_devices.index(dev))
            self.select_device_box.blockSignals(False)
            self.select_device_box.setStyleSheet(f"background-color: #1e1e1e; color: white; border: 1px solid {'#27AE60' if not dev['empty'] else '#F39C12'};")
    def on_import_click(self):
        if self.ingest_mode == "scan": self.start_scan()
        else: self.start_transfer()
    def start_scan(self):
        src = self.current_detected_path if self.source_tabs.currentIndex() == 0 else self.source_input.text()
        if not src or not os.path.exists(src): return QMessageBox.warning(self, "Error", "Invalid Source")
        
        self.import_btn.setEnabled(False); self.status_label.setText("SCANNING SOURCE..."); self.tree.clear()
        
        allowed_exts = None
        if self.source_tabs.currentIndex() == 0 and self.found_devices:
             idx = self.select_device_box.currentIndex()
             if idx >= 0 and idx < len(self.found_devices):
                 allowed_exts = self.found_devices[idx].get('exts')

        self.scanner = IngestScanner(src, self.check_videos_only.isChecked(), allowed_exts)
        self.scanner.finished_signal.connect(self.on_scan_complete); self.scanner.start()
    def on_scan_complete(self, grouped_files): self.last_scan_results = grouped_files; self.refresh_tree_view()
    def open_video_preview(self, item, column):
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if path and os.path.exists(path) and os.path.splitext(path)[1].upper() in DeviceRegistry.VIDEO_EXTS:
            if not self.preview_dlg: self.preview_dlg = VideoPreviewDialog(self)
            self.preview_dlg.load_video(path); self.preview_dlg.show()
    def refresh_tree_view(self):
        self.tree.clear(); total = 0
        if not self.last_scan_results:
            p = QTreeWidgetItem(self.tree); p.setText(0, "Select a source and click 'SCAN SOURCE' to view media."); p.setFlags(p.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
            return
            
        for date, files in sorted(self.last_scan_results.items(), reverse=True):
            d_item = QTreeWidgetItem(self.tree); d_item.setText(0, f"{date} ({len(files)} files)")
            d_item.setFlags(d_item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsAutoTristate)
            d_item.setCheckState(0, Qt.CheckState.Checked)
            for f in files:
                f_item = QTreeWidgetItem(d_item); f_item.setText(0, os.path.basename(f)); f_item.setData(0, Qt.ItemDataRole.UserRole, f)
                f_item.setFlags(f_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                f_item.setCheckState(0, Qt.CheckState.Checked); total += 1
        
        if total == 0:
            p = QTreeWidgetItem(self.tree)
            msg = "No video files found." if self.check_videos_only.isChecked() else "No matching media found."
            p.setText(0, msg); p.setFlags(p.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
            
        self.ingest_mode = "transfer"; self.update_transfer_button_text(); self.status_label.setText(f"Found {total} files.")
    def update_transfer_button_text(self):
        if self.ingest_mode == "scan": self.import_btn.setText("SCAN SOURCE")
        else: self.import_btn.setText("START TRANSFER")
    def start_transfer(self):
        selected = []
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            d_item = root.child(i)
            for j in range(d_item.childCount()):
                f_item = d_item.child(j)
                if f_item.checkState(0) == Qt.CheckState.Checked: selected.append(f_item.data(0, Qt.ItemDataRole.UserRole))
        if not selected: return QMessageBox.warning(self, "Error", "No files selected.")
        src = self.current_detected_path if self.source_tabs.currentIndex() == 0 else self.source_input.text()
        dests = [self.dest_input.text()]
        if self.dest_input_2.text().strip(): dests.append(self.dest_input_2.text().strip())
        if self.dest_input_3.text().strip(): dests.append(self.dest_input_3.text().strip())
        self.import_btn.setEnabled(False); self.cancel_btn.setEnabled(True)
        tc_enabled = self.check_transcode.isChecked(); tc_settings = self.transcode_widget.get_settings()
        if tc_enabled:
            self.transcode_worker = AsyncTranscoder(tc_settings, self.transcode_widget.is_gpu_enabled())
            self.transcode_worker.log_signal.connect(self.append_transcode_log); self.transcode_worker.all_finished_signal.connect(self.on_all_transcodes_finished); self.transcode_worker.start(); self.set_transcode_active(True)
        self.copy_worker = CopyWorker(src, dests, self.project_name_input.text(), self.check_date.isChecked(), self.check_dupe.isChecked(), self.check_videos_only.isChecked(), self.device_combo.currentText(), self.check_verify.isChecked(), selected)
        self.copy_worker.log_signal.connect(self.append_copy_log); self.copy_worker.progress_signal.connect(self.progress_bar.setValue); self.copy_worker.finished_signal.connect(self.on_copy_finished)
        if tc_enabled: self.copy_worker.file_ready_signal.connect(self.queue_for_transcode)
        self.copy_worker.start()
    def update_storage_display_bar(self, needed, free, enough):
        self.storage_bar.setVisible(True); self.storage_bar.setValue(int((needed/free)*100) if free > 0 else 100)
    def queue_for_transcode(self, src, dest, name):
        if self.transcode_worker:
            if TranscodeEngine.is_edit_friendly(dest, self.transcode_widget.get_settings().get('v_codec')): self.transcode_worker.report_skipped(name); return
            out = os.path.join(os.path.dirname(dest), "Edit_Ready", f"{os.path.splitext(name)[0]}_EDIT.mov")
            os.makedirs(os.path.dirname(out), exist_ok=True); self.transcode_worker.add_job(dest, out, name)
    def cancel_import(self):
        if self.copy_worker: self.copy_worker.stop()
        if self.transcode_worker: self.transcode_worker.stop()
        self.import_btn.setEnabled(True); self.cancel_btn.setEnabled(False); self.set_transcode_active(False)
    def on_copy_finished(self, success, msg):
        if success:
            mode = self.app.settings.value("report_dest_mode", "project")
            if mode == "fixed": r_path = self.app.settings.value("report_fixed_path", self.dest_input.text())
            elif mode == "custom" and self.report_custom_path: r_path = self.report_custom_path
            else: r_path = self.dest_input.text()
            if self.check_report.isVisible() and self.check_report.isChecked(): self.finalize_report(r_path)
            if self.check_mhl.isVisible() and self.check_mhl.isChecked():
                try: MHLGenerator.generate(r_path, self.copy_worker.transfer_data, self.project_name_input.text() or "CineBridge")
                except: pass
        if self.check_transcode.isChecked() and self.transcode_worker: self.transcode_worker.set_producer_finished(); self.import_btn.setText("TRANSCODING...")
        else:
            if success:
                v = " and verified" if self.check_verify.isChecked() else ""
                SystemNotifier.notify("Ingest Complete", f"All files offloaded{v}."); JobReportDialog("Ingest Complete", f"Ingest Successful. All files offloaded{v}.", self).exec()
            self.import_btn.setEnabled(True); self.import_btn.setText("COMPLETE"); self.import_btn.setStyleSheet("background-color: #27AE60; color: white;"); self.set_transcode_active(False)
    def finalize_report(self, deliverables_path):
        project = self.project_name_input.text() or "Unnamed"
        report_path = os.path.join(deliverables_path, f"Transfer_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
        if self.app.settings.value("feature_visual_report", False, type=bool):
            video_files = [f['path'] for f in self.copy_worker.transfer_data if os.path.splitext(f['name'])[1].upper() in DeviceRegistry.VIDEO_EXTS]
            if video_files:
                self.report_thumbs = {}; self.report_thumb_worker = ThumbnailWorker(video_files)
                self.report_thumb_worker.status_signal.connect(self.status_label.setText); self.report_thumb_worker.thumb_ready.connect(self.on_report_thumb_ready)
                self.report_thumb_worker.finished.connect(lambda: self.generate_final_pdf(report_path, project)); self.report_thumb_worker.start(); return
        self.generate_final_pdf(report_path, project)
    def on_report_thumb_ready(self, path, image):
        ba = QByteArray(); buf = QBuffer(ba); buf.open(QIODevice.OpenModeFlag.WriteOnly); image.save(buf, "PNG")
        self.report_thumbs[os.path.basename(path)] = ba.toBase64().data().decode()
    def generate_final_pdf(self, path, project):
        try:
            ReportGenerator.generate_pdf(path, self.copy_worker.transfer_data, project, getattr(self, 'report_thumbs', None))
            self.append_copy_log(f"📝 Report: {path}"); self.status_label.setText("✅ Ingest & Report Complete!")
        except: pass
    def on_all_transcodes_finished(self):
        SystemNotifier.notify("Job Complete", "Ingest and Transcoding finished."); self.import_btn.setEnabled(True); self.import_btn.setText("COMPLETE"); self.import_btn.setStyleSheet("background-color: #27AE60; color: white;")
        v = " and verified" if self.check_verify.isChecked() else ""
        JobReportDialog("Job Complete", f"Job Successful. All ingest{v} and transcode operations finished.", self).exec()
    def save_tab_settings(self):
        s = self.app.settings; s.setValue("last_source", self.source_input.text()); s.setValue("last_dest", self.dest_input.text()); s.setValue("sort_date", self.check_date.isChecked()); s.setValue("skip_dupe", self.check_dupe.isChecked()); s.setValue("videos_only", self.check_videos_only.isChecked()); s.setValue("transcode_dnx", self.check_transcode.isChecked()); s.setValue("verify_copy", self.check_verify.isChecked()); s.setValue("gen_report", self.check_report.isChecked()); s.setValue("gen_mhl", self.check_mhl.isChecked())
    def load_tab_settings(self):
        s = self.app.settings; self.source_input.setText(s.value("last_source", "")); self.dest_input.setText(s.value("last_dest", "")); self.check_date.setChecked(s.value("sort_date", True, type=bool)); self.check_dupe.setChecked(s.value("skip_dupe", True, type=bool)); self.check_videos_only.setChecked(s.value("videos_only", False, type=bool)); self.check_transcode.setChecked(s.value("transcode_dnx", False, type=bool)); self.check_verify.setChecked(s.value("verify_copy", False, type=bool)); self.check_report.setChecked(s.value("gen_report", True, type=bool)); self.check_mhl.setChecked(s.value("gen_mhl", False, type=bool))
        self.toggle_transcode_ui(self.check_transcode.isChecked())

class ConvertTab(QWidget):
    def __init__(self):
        super().__init__(); self.setAcceptDrops(True); self.is_processing = False; self.thumb_workers = []
        layout = QVBoxLayout(); layout.setSpacing(15); layout.setContentsMargins(20, 20, 20, 20); self.setLayout(layout)
        self.settings = TranscodeSettingsWidget("1. Conversion Settings", mode="general"); layout.addWidget(self.settings)
        input_group = QGroupBox("2. Input Media"); input_lay = QVBoxLayout(); self.btn_browse = QPushButton("Select Video Files..."); self.btn_browse.clicked.connect(self.browse_files); input_lay.addWidget(self.btn_browse)
        self.drop_area = QLabel("\n⬇️\n\nDRAG & DROP VIDEO FILES HERE\n\n"); self.drop_area.setAlignment(Qt.AlignmentFlag.AlignCenter); self.drop_area.setStyleSheet("QLabel { border: 3px dashed #666; border-radius: 10px; background-color: #2b2b2b; color: #aaa; font-weight: bold; } QLabel:hover { border-color: #3498DB; background-color: #333; color: white; }"); input_lay.addWidget(self.drop_area, 1); input_group.setLayout(input_lay); layout.addWidget(input_group, 1)
        out_group = QGroupBox("3. Destination (Optional)"); out_lay = QHBoxLayout(); self.out_input = QLineEdit(); self.btn_browse_out = QPushButton("Browse..."); self.btn_browse_out.clicked.connect(self.browse_dest)
        out_lay.addWidget(self.out_input); out_lay.addWidget(self.btn_browse_out); out_group.setLayout(out_lay); layout.addWidget(out_group)
        queue_group = QGroupBox("4. Batch Queue"); queue_lay = QVBoxLayout(); self.list = QListWidget(); self.list.setMaximumHeight(150); self.list.setIconSize(QSize(96, 54)); queue_lay.addWidget(self.list)
        dash_frame = QFrame(); dash_frame.setObjectName("DashFrame"); dash_layout = QVBoxLayout(dash_frame); dash_row = QHBoxLayout(); self.status_label = QLabel("Waiting..."); self.stats_row = QWidget(); self.stats_row.setVisible(False); sr_lay = QHBoxLayout(self.stats_row)
        self.cpu_load_lbl = QLabel("CPU: 0%"); self.cpu_temp_lbl = QLabel(""); self.gpu_load_lbl = QLabel(""); self.gpu_temp_lbl = QLabel(""); sr_lay.addWidget(self.cpu_load_lbl); sr_lay.addWidget(self.cpu_temp_lbl); sr_lay.addWidget(self.gpu_load_lbl); sr_lay.addWidget(self.gpu_temp_lbl); dash_row.addWidget(self.status_label); dash_row.addStretch(); dash_layout.addLayout(dash_row); dash_layout.addWidget(self.stats_row)
        self.pbar = QProgressBar(); dash_layout.addWidget(self.pbar); queue_lay.addWidget(dash_frame)
        h = QHBoxLayout(); b_clr = QPushButton("Clear Queue"); b_clr.clicked.connect(self.list.clear); self.btn_go = QPushButton("START BATCH"); self.btn_go.setObjectName("StartBtn"); self.btn_go.clicked.connect(self.on_btn_click)
        h.addWidget(b_clr); h.addWidget(self.btn_go); queue_lay.addLayout(h); queue_group.setLayout(queue_lay); layout.addWidget(queue_group); layout.addStretch()
    def update_load_display(self, stats):
        self.cpu_load_lbl.setText(f"CPU: {stats['cpu_load']}%"); self.cpu_temp_lbl.setText(f"({stats['cpu_temp']}°C)" if stats['cpu_temp'] > 0 else "")
        if stats['has_gpu']:
            v = stats.get('gpu_vendor', 'GPU'); self.gpu_load_lbl.setText(f"{v}: {stats['gpu_load']}% "); self.gpu_temp_lbl.setText(f"({stats['gpu_temp']}°C)" if stats['gpu_temp'] > 0 else "")
            self.gpu_load_lbl.setVisible(True); self.gpu_temp_lbl.setVisible(True)
        else: self.gpu_load_lbl.setVisible(False); self.gpu_temp_lbl.setVisible(False)
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
        self.is_processing = running; self.stats_row.setVisible(running)
        if running: self.btn_go.setText("STOP BATCH"); self.btn_go.setObjectName("StopBtn")
        else: self.btn_go.setText("START BATCH"); self.btn_go.setObjectName("StartBtn")
        self.btn_go.style().unpolish(self.btn_go); self.btn_go.style().polish(self.btn_go)
    def start(self):
        files = [self.list.item(i).text() for i in range(self.list.count())]
        if not files: return QMessageBox.warning(self, "Empty", "Queue is empty.")
        self.toggle_ui_state(True); self.worker = BatchTranscodeWorker(files, self.out_input.text().strip(), self.settings.get_settings(), mode="convert", use_gpu=self.settings.is_gpu_enabled())
        self.worker.progress_signal.connect(self.pbar.setValue); self.worker.status_signal.connect(self.status_label.setText); self.worker.finished_signal.connect(self.on_finished); self.worker.start()
    def start_thumb_process(self, files):
        worker = ThumbnailWorker(files); worker.thumb_ready.connect(self.update_thumbnail); worker.start(); self.thumb_workers.append(worker)
    def update_thumbnail(self, path, image):
        pix = QPixmap.fromImage(image); items = self.list.findItems(path, Qt.MatchFlag.MatchExactly)
        for i in items: i.setIcon(QIcon(pix))
    def stop(self):
        if hasattr(self, 'worker'): self.worker.stop(); self.status_label.setText("Stopping...")
    def on_finished(self):
        SystemNotifier.notify("Conversion Complete", "Batch transcode finished."); self.toggle_ui_state(False); self.status_label.setText("Batch Complete!")
        JobReportDialog("Conversion Complete", "Transcode Successful. Your media is ready for edit.", self).exec()
    def show_context_menu(self, pos):
        i = self.list.itemAt(pos)
        if i:
            m = QMenu(self); a = QAction("Inspect Media Info", self); a.triggered.connect(lambda: MediaInfoDialog(MediaInfoExtractor.get_info(i.text()), self).exec()); m.addAction(a); m.exec(self.list.mapToGlobal(pos))

class DeliveryTab(QWidget):
    def __init__(self):
        super().__init__(); self.setAcceptDrops(True); self.is_processing = False
        layout = QVBoxLayout(); layout.setSpacing(15); layout.setContentsMargins(20, 20, 20, 20); self.setLayout(layout)
        self.settings = TranscodeSettingsWidget("1. Delivery Settings", mode="delivery"); self.settings.preset_combo.setCurrentText("H.264 / AVC (Standard)"); layout.addWidget(self.settings)
        master_group = QGroupBox("2. Master File"); master_lay = QVBoxLayout(); self.inp_file = FileDropLineEdit()
        self.btn_sel_master = QPushButton("Select Master File..."); self.btn_sel_master.clicked.connect(lambda: self.inp_file.setText(QFileDialog.getOpenFileName(self, "Select Master File")[0]))
        self.drop_area = QLabel("\n⬇️\n\nDRAG MASTER FILE HERE\n\n"); self.drop_area.setAlignment(Qt.AlignmentFlag.AlignCenter); self.drop_area.setStyleSheet("QLabel { border: 3px dashed #666; border-radius: 10px; background-color: #2b2b2b; color: #aaa; font-weight: bold; } QLabel:hover { border-color: #3498DB; background-color: #333; color: white; }"); master_lay.addWidget(self.btn_sel_master); master_lay.addWidget(self.inp_file); master_lay.addWidget(self.drop_area, 1); master_group.setLayout(master_lay); layout.addWidget(master_group, 1)
        dest_group = QGroupBox("3. Destination (Optional)"); dest_lay = QHBoxLayout(); self.inp_dest = QLineEdit(); self.btn_b2 = QPushButton("Browse...")
        self.btn_b2.clicked.connect(lambda: self.inp_dest.setText(QFileDialog.getExistingDirectory(self, "Pick a Destination"))); dest_lay.addWidget(self.inp_dest); dest_lay.addWidget(self.btn_b2); dest_group.setLayout(dest_lay); layout.addWidget(dest_group)
        dash_frame = QFrame(); dash_frame.setObjectName("DashFrame"); dash_layout = QVBoxLayout(dash_frame)
        self.status_label = QLabel("Ready to Render"); dash_layout.addWidget(self.status_label); self.pbar = QProgressBar(); dash_layout.addWidget(self.pbar); layout.addWidget(dash_frame)
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
        self.is_processing = running
        if running: self.btn_go.setText("STOP RENDER"); self.btn_go.setObjectName("StopBtn")
        else: self.btn_go.setText("RENDER"); self.btn_go.setObjectName("StartBtn")
        self.btn_go.style().unpolish(self.btn_go); self.btn_go.style().polish(self.btn_go)
    def start(self):
        if not self.inp_file.text(): return QMessageBox.warning(self, "Missing", "Select master file.")
        self.toggle_ui_state(True); self.worker = BatchTranscodeWorker([self.inp_file.text()], self.inp_dest.text().strip(), self.settings.get_settings(), mode="delivery", use_gpu=self.settings.is_gpu_enabled())
        self.worker.progress_signal.connect(self.pbar.setValue); self.worker.status_signal.connect(self.status_label.setText); self.worker.finished_signal.connect(self.on_finished); self.worker.start()
    def stop(self):
        if hasattr(self, 'worker'): self.worker.stop(); self.status_label.setText("Stopping...")
    def on_finished(self):
        SystemNotifier.notify("Render Complete", "Delivery render finished."); self.toggle_ui_state(False); self.status_label.setText("Delivery Render Complete!")
        JobReportDialog("Render Complete", "Final Render Successful. Your master is ready for distribution.", self).exec()

class WatchTab(QWidget):
    def __init__(self):
        super().__init__(); layout = QVBoxLayout(); layout.setSpacing(15); layout.setContentsMargins(20, 20, 20, 20); self.setLayout(layout)
        self.is_active = False; self.processed_files = set(); self.timer = QTimer(); self.timer.timeout.connect(self.check_folder)
        self.monitored_files = {}; self.STABILITY_THRESHOLD = 3.0
        conf_group = QGroupBox("1. Service Configuration"); conf_lay = QVBoxLayout(); stab_lay = QHBoxLayout(); stab_lay.addWidget(QLabel("File Stability Check (Seconds):"))
        self.spin_stability = QSpinBox(); self.spin_stability.setRange(1, 60); self.spin_stability.setValue(3); self.spin_stability.valueChanged.connect(self.update_threshold); stab_lay.addWidget(self.spin_stability); stab_lay.addStretch(); conf_lay.addLayout(stab_lay)
        self.settings = TranscodeSettingsWidget(mode="general"); conf_lay.addWidget(self.settings); conf_group.setLayout(conf_lay); layout.addWidget(conf_group)
        fold_group = QGroupBox("2. Folder Selection"); fold_lay = QFormLayout(); self.inp_watch = QLineEdit(); self.btn_watch = QPushButton("Browse..."); self.btn_watch.clicked.connect(self.browse_watch)
        w_row = QHBoxLayout(); w_row.addWidget(self.inp_watch); w_row.addWidget(self.btn_watch); self.inp_dest = QLineEdit(); self.btn_dest = QPushButton("Browse..."); self.btn_dest.clicked.connect(self.browse_dest)
        d_row = QHBoxLayout(); d_row.addWidget(self.inp_dest); d_row.addWidget(self.btn_dest); fold_lay.addRow("Watch Folder:", w_row); fold_lay.addRow("Destination:", d_row); fold_group.setLayout(fold_lay); layout.addWidget(fold_group)
        dash_frame = QFrame(); dash_frame.setObjectName("DashFrame"); dash_layout = QVBoxLayout(dash_frame)
        self.status_label = QLabel("Watch Folder: INACTIVE"); dash_layout.addWidget(self.status_label); self.pbar = QProgressBar(); self.pbar.setVisible(False); dash_layout.addWidget(self.pbar); layout.addWidget(dash_frame)
        self.btn_toggle = QPushButton("ACTIVATE WATCH FOLDER"); self.btn_toggle.setObjectName("StartBtn"); self.btn_toggle.setMinimumHeight(50); self.btn_toggle.clicked.connect(self.toggle_watch); layout.addWidget(self.btn_toggle); layout.addStretch()
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
        self.worker.progress_signal.connect(self.pbar.setValue); self.worker.finished_signal.connect(self.on_batch_finished)
        self.pbar.setVisible(True); self.timer.stop()
        for f in files: self.processed_files.add(f)
        self.worker.start()
    def on_batch_finished(self):
        self.pbar.setVisible(False); self.timer.start(2000); self.status_label.setText("Watch Folder: ACTIVE")
        SystemNotifier.notify("Watch Folder", "New proxies processed.")