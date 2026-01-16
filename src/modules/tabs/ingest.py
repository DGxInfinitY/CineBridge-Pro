import os
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
    QFileDialog, QProgressBar, QTextEdit, QMessageBox, QCheckBox, QGroupBox, 
    QComboBox, QTabWidget, QFrame, QSplitter, QTreeWidget, QTreeWidgetItem, 
    QGridLayout, QAbstractItemView
)
from PyQt6.QtGui import QAction, QIcon, QPixmap, QImage
from PyQt6.QtCore import Qt, QTimer, QSize, QBuffer, QByteArray, QIODevice

from ..config import DEBUG_MODE, GUI_LOG_QUEUE, debug_log, info_log, error_log
from ..utils import DeviceRegistry, ReportGenerator, MHLGenerator, SystemNotifier, MediaInfoExtractor, TranscodeEngine
from ..workers import ScanWorker, IngestScanner, AsyncTranscoder, CopyWorker, ThumbnailWorker
from ..ui import TranscodeSettingsWidget, JobReportDialog, TranscodeConfigDialog, VideoPreviewDialog, CheckableComboBox, StructureConfigDialog

class IngestTab(QWidget):
    def __init__(self, parent_app):
        super().__init__(); self.app = parent_app; self.layout = QVBoxLayout(); self.layout.setSpacing(10); self.layout.setContentsMargins(20, 20, 20, 20); self.setLayout(self.layout)
        self.copy_worker = None; self.transcode_worker = None; self.scan_worker = None; self.found_devices = []; self.current_detected_path = None
        self.ingest_mode = "scan"; self.last_scan_results = None; self.preview_dlg = None
        self.setup_ui(); self.load_tab_settings()
        self.scan_watchdog = QTimer(); self.scan_watchdog.setSingleShot(True); self.scan_watchdog.timeout.connect(self.on_scan_timeout)
        self.reset_timer = QTimer(); self.reset_timer.setSingleShot(True); self.reset_timer.timeout.connect(self.reset_ingest_mode)
        QTimer.singleShot(500, self.run_auto_scan)

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
        self.check_videos_only = QCheckBox("Video Only"); self.check_videos_only.setToolTip("Only scan video formats."); self.check_videos_only.toggled.connect(self.refresh_tree_view)
        self.check_verify = QCheckBox("Verify Copy"); self.check_verify.setStyleSheet("color: #27AE60; font-weight: bold;"); self.check_verify.setToolTip("Perform checksum verification.")
        self.check_report = QCheckBox("Gen Report"); self.check_mhl = QCheckBox("Gen MHL")
        self.btn_structure = QToolButton(); self.btn_structure.setText("📂 Folder Structure..."); self.btn_structure.clicked.connect(self.open_structure_config)
        self.structure_template = "{Date}/{Camera}/{Category}" # Default
        
        self.check_transcode = QCheckBox("Enable Transcode"); self.check_transcode.setStyleSheet("color: #E67E22; font-weight: bold;"); self.check_transcode.toggled.connect(self.toggle_transcode_ui)
        
        rules_grid.addWidget(self.check_date, 0, 0); rules_grid.addWidget(self.check_dupe, 0, 1); rules_grid.addWidget(self.combo_filter, 0, 2)
        rules_grid.addWidget(self.check_verify, 1, 0); rules_grid.addWidget(self.check_transcode, 1, 1); rules_grid.addWidget(self.check_report, 1, 2)
        rules_grid.addWidget(self.check_mhl, 2, 0); rules_grid.addWidget(self.btn_structure, 2, 1); settings_layout.addLayout(rules_grid)
        
        config_btns = QHBoxLayout()
        self.btn_config_trans = QPushButton("Configure Transcode..."); self.btn_config_trans.setVisible(False); self.btn_config_trans.clicked.connect(self.open_transcode_config)
        self.btn_config_reports = QPushButton("Reports Settings..."); self.btn_config_reports.setVisible(False); self.btn_config_reports.clicked.connect(self.open_report_config)
        config_btns.addWidget(self.btn_config_trans); config_btns.addWidget(self.btn_config_reports); settings_layout.addLayout(config_btns)
        
        self.transcode_widget = TranscodeSettingsWidget(mode="general"); self.report_custom_path = ""
        settings_layout.addStretch(); settings_group.setLayout(settings_layout)
        
        # 4. Review Group
        self.review_group = QGroupBox("4. Select Media"); review_lay = QVBoxLayout()
        self.tree = QTreeWidget(); self.tree.setHeaderLabel("Media Review")
        self.tree.itemChanged.connect(self.on_tree_changed)
        self.tree.itemDoubleClicked.connect(self.open_video_preview)
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
        
        self.transcode_metrics_label = QLabel(""); self.transcode_metrics_label.setVisible(False); self.transcode_metrics_label.setStyleSheet("color: #3498DB; font-family: Consolas; font-size: 11px;"); dash_layout.addWidget(self.transcode_metrics_label)
        self.transcode_status_label = QLabel(""); self.transcode_status_label.setVisible(False); self.transcode_status_label.setStyleSheet("color: #E67E22; font-weight: bold;"); dash_layout.addWidget(self.transcode_status_label)
        
        self.stats_row = QWidget(); self.stats_row.setVisible(False); sr_lay = QHBoxLayout(self.stats_row); sr_lay.setContentsMargins(0,0,0,0); sr_lay.setSpacing(10)
        self.cpu_load_lbl = QLabel("CPU: 0%"); self.cpu_load_lbl.setStyleSheet("color: #E74C3C; font-weight: bold; font-size: 11px;")
        self.cpu_temp_lbl = QLabel(""); self.cpu_temp_lbl.setStyleSheet("color: #E74C3C; font-size: 11px;")
        self.gpu_load_lbl = QLabel(""); self.gpu_load_lbl.setStyleSheet("color: #3498DB; font-weight: bold; font-size: 11px;")
        self.gpu_temp_lbl = QLabel(""); self.gpu_temp_lbl.setStyleSheet("color: #3498DB; font-size: 11px;")
        sr_lay.addStretch(); sr_lay.addWidget(self.cpu_load_lbl); sr_lay.addWidget(self.cpu_temp_lbl); sr_lay.addWidget(self.gpu_load_lbl); sr_lay.addWidget(self.gpu_temp_lbl); sr_lay.addStretch()
        dash_layout.addWidget(self.stats_row); self.layout.addWidget(dash_frame)

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

    def clear_logs(self): self.copy_log.clear(); self.transcode_log.clear()
    def toggle_logs(self, show_copy, show_transcode): self.copy_log.setVisible(show_copy); self.transcode_log.setVisible(show_transcode); self.splitter.setVisible(show_copy or show_transcode)
    def toggle_transcode_ui(self, checked): self.btn_config_trans.setVisible(checked); self.transcode_status_label.setVisible(checked); self.update_transfer_button_text()
    def open_transcode_config(self): TranscodeConfigDialog(self.transcode_widget, self).exec()
    def open_structure_config(self):
        dlg = StructureConfigDialog(self.structure_template, self)
        if dlg.exec():
            self.structure_template = dlg.get_template()
            self.save_tab_settings()
    def open_report_config(self):
        d = QFileDialog.getExistingDirectory(self, "Select Report Folder", self.report_custom_path or self.dest_input.text())
        if d: self.report_custom_path = d
    def update_load_display(self, stats):
        self.cpu_load_lbl.setText(f"CPU: {stats['cpu_load']}%")
        self.cpu_temp_lbl.setText(f"({stats['cpu_temp']}°C)" if stats['cpu_temp'] > 0 else "")
        if stats['has_gpu']:
            v = stats.get('gpu_vendor', 'GPU'); self.gpu_load_lbl.setText(f"{v}: {stats['gpu_load']}%"); self.gpu_temp_lbl.setText(f"({stats['gpu_temp']}°C)" if stats['gpu_temp'] > 0 else "")
            self.gpu_load_lbl.setVisible(True); self.gpu_temp_lbl.setVisible(True)
        else: self.gpu_load_lbl.setVisible(False); self.gpu_temp_lbl.setVisible(False)
    def set_transcode_active(self, active):
        self.stats_row.setVisible(active); self.transcode_status_label.setVisible(active)
        self.transcode_metrics_label.setVisible(active)
        if not active: self.transcode_metrics_label.setText("")
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
        show_pdf = self.app.settings.value("feature_pdf_report", False, type=bool)
        show_mhl = self.app.settings.value("feature_mhl", False, type=bool)
        self.check_report.setVisible(show_pdf); self.check_report.setText("Gen Visual Report" if show_visual else "Gen Report")
        self.check_mhl.setVisible(show_mhl); self.btn_config_reports.setVisible((show_pdf or show_mhl) and self.app.settings.value("report_dest_mode") == "custom")
    def append_copy_log(self, text): self.copy_log.append(text); sb = self.copy_log.verticalScrollBar(); sb.setValue(sb.maximum())
    def append_transcode_log(self, text): self.transcode_log.append(text); sb = self.transcode_log.verticalScrollBar(); sb.setValue(sb.maximum())
    def run_auto_scan(self):
        if self.import_btn.text() == "COMPLETE": self.reset_ingest_mode()
        self.auto_info_label.setText("Scanning..."); self.scan_btn.setEnabled(False); self.scan_watchdog.start(30000); self.scan_worker = ScanWorker(); self.scan_worker.finished_signal.connect(self.on_scan_finished); self.scan_worker.start()
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
        name = dev.get('display_name', 'Generic Storage'); path_short = dev['path']
        msg = f"✅ {name}" if not dev['empty'] else f"⚠️ {name} (Empty)"
        if len(path_short) > 35: path_short = path_short[:15] + "..." + path_short[-15:]
        self.result_label.setText(f"<h3 style='color:{'#27AE60' if not dev['empty'] else '#F39C12'}'>{msg}</h3><span style='color:white;'>{path_short}</span>")
        self.result_card.setStyleSheet(f"background-color: {'#2e3b33' if not dev['empty'] else '#4d3d2a'}; border: 2px solid {'#27AE60' if not dev['empty'] else '#F39C12'}; border-radius: 8px;")
        self.result_card.setVisible(True)
        idx = self.device_combo.findText(name)
        if idx >= 0: self.device_combo.setCurrentIndex(idx)
        elif name == "Generic Storage":
            idx_gen = self.device_combo.findData("Generic_Device")
            if idx_gen >= 0: self.device_combo.setCurrentIndex(idx_gen)
        if multi:
            self.select_device_box.blockSignals(True); self.select_device_box.setVisible(True); self.select_device_box.clear()
            for d in self.found_devices:
                d_name = d.get('display_name', 'Generic Storage')
                self.select_device_box.addItem(f"{d_name} ({'Empty' if d['empty'] else 'Data'})")
            try: d_idx = self.found_devices.index(dev)
            except:
                d_idx = -1
                for i, fd in enumerate(self.found_devices):
                    if fd['path'] == dev.get('path'): d_idx = i; break
            if d_idx >= 0: self.select_device_box.setCurrentIndex(d_idx)
            self.select_device_box.blockSignals(False); self.select_device_box.setStyleSheet(f"background-color: #1e1e1e; color: white; border: 1px solid {'#27AE60' if not dev['empty'] else '#F39C12'};")
    def on_import_click(self):
        debug_log(f"Ingest: Import button clicked. Mode={self.ingest_mode}")
        if self.ingest_mode == "scan": self.start_scan()
        else: self.start_transfer()
    def start_scan(self):
        src = self.current_detected_path if self.source_tabs.currentIndex() == 0 else self.source_input.text()
        if not src or not os.path.exists(src): return QMessageBox.warning(self, "Error", "Invalid Source")
        self.import_btn.setEnabled(False); self.status_label.setText("SCANNING SOURCE..."); self.tree.clear()
        allowed_exts = None
        if self.source_tabs.currentIndex() == 0 and self.found_devices:
             idx = self.select_device_box.currentIndex()
             if idx >= 0 and idx < len(self.found_devices): allowed_exts = self.found_devices[idx].get('exts')
        self.scanner = IngestScanner(src, self.check_videos_only.isChecked(), allowed_exts)
        self.scanner.finished_signal.connect(self.on_scan_complete); self.scanner.start()
    def on_scan_complete(self, grouped_files): self.last_scan_results = grouped_files; self.refresh_tree_view()
    def open_video_preview(self, item, column):
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if path and os.path.exists(path) and os.path.splitext(path)[1].upper() in DeviceRegistry.VIDEO_EXTS:
            if not self.preview_dlg: self.preview_dlg = VideoPreviewDialog(path, self)
            self.preview_dlg.load_video(path); self.preview_dlg.show()
    def refresh_tree_view(self):
        self.tree.clear(); total = 0
        if not self.last_scan_results:
            p = QTreeWidgetItem(self.tree); p.setText(0, "Select a source and click 'SCAN SOURCE' to view media."); p.setFlags(p.flags() & ~Qt.ItemFlag.ItemIsUserCheckable); return
        
        v_exts = DeviceRegistry.VIDEO_EXTS
        for date, files in sorted(self.last_scan_results.items(), reverse=True):
            # Filter files if Video Only is checked
            if self.check_videos_only.isChecked():
                files = [f for f in files if os.path.splitext(f)[1].upper() in v_exts]
            
            if not files: continue
            
            d_item = QTreeWidgetItem(self.tree); d_item.setText(0, f"{date} ({len(files)} files)")
            d_item.setFlags(d_item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsAutoTristate); d_item.setCheckState(0, Qt.CheckState.Checked)
            for f in files:
                f_item = QTreeWidgetItem(d_item); f_item.setText(0, os.path.basename(f)); f_item.setData(0, Qt.ItemDataRole.UserRole, f)
                f_item.setFlags(f_item.flags() | Qt.ItemFlag.ItemIsUserCheckable); f_item.setCheckState(0, Qt.CheckState.Checked); total += 1
        
        if total == 0:
            p = QTreeWidgetItem(self.tree); p.setText(0, "No matching media found."); p.setFlags(p.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
        self.tree.expandAll(); self.ingest_mode = "transfer"; self.update_transfer_button_text(); self.status_label.setText(f"Found {total} files.")

    def on_tree_changed(self, item, column):
        self.tree.blockSignals(True)
        if item.childCount() > 0: # Date node
            for i in range(item.childCount()):
                item.child(i).setCheckState(0, item.checkState(0))
        elif item.parent(): # File node
            p = item.parent(); all_checked = True; none_checked = True
            for i in range(p.childCount()):
                if p.child(i).checkState(0) == Qt.CheckState.Checked: none_checked = False
                else: all_checked = False
            if all_checked: p.setCheckState(0, Qt.CheckState.Checked)
            elif none_checked: p.setCheckState(0, Qt.CheckState.Unchecked)
            else: p.setCheckState(0, Qt.CheckState.PartiallyChecked)
        self.tree.blockSignals(False)
        self.update_transfer_button_text()

    def update_transfer_button_text(self):
        if self.ingest_mode == "scan":
            self.import_btn.setText("SCAN SOURCE"); self.import_btn.setEnabled(True); return
        count = 0; root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            d_item = root.child(i)
            for j in range(d_item.childCount()):
                if d_item.child(j).checkState(0) == Qt.CheckState.Checked: count += 1
        if count == 0: self.import_btn.setText("START (SELECT FILES FIRST)"); self.import_btn.setEnabled(False); return
        self.import_btn.setEnabled(True)
        action = "TRANSFER/TRANSCODE" if self.check_transcode.isChecked() else "TRANSFER"
        self.import_btn.setText(f"START {action} ({count} FILES)")

    def start_transfer(self):
        try:
            debug_log("Ingest: Start Transfer sequence beginning")
            selected = []
            root = self.tree.invisibleRootItem()
            for i in range(root.childCount()):
                d_item = root.child(i)
                for j in range(d_item.childCount()):
                    f_item = d_item.child(j)
                    if f_item.checkState(0) == Qt.CheckState.Checked: selected.append(f_item.data(0, Qt.ItemDataRole.UserRole))
            debug_log(f"Ingest: {len(selected)} files selected for offload")
            if not selected: return QMessageBox.warning(self, "Error", "No files selected.")
            src = self.current_detected_path if self.source_tabs.currentIndex() == 0 else self.source_input.text()
            dests = [self.dest_input.text()]
            if self.dest_input_2.text().strip(): dests.append(self.dest_input_2.text().strip())
            if self.dest_input_3.text().strip(): dests.append(self.dest_input_3.text().strip())
            debug_log(f"Ingest: Source Path: {src}"); debug_log(f"Ingest: Primary Dest: {dests[0]}")
            if not src or not dests[0]: return QMessageBox.warning(self, "Error", "Set Source/Main Dest")
            self.save_tab_settings(); self.import_btn.setEnabled(False); self.cancel_btn.setEnabled(True); 
            self.import_btn.setText("INGESTING..."); self.import_btn.setStyleSheet("background-color: #E67E22; color: white;"); 
            self.storage_bar.setVisible(False); self.progress_bar.setValue(0); self.clear_logs()
            cam_name = self.device_combo.currentText()
            if self.device_combo.currentData() == "auto":
                if self.found_devices and self.select_device_box.currentIndex() >= 0: cam_name = self.found_devices[self.select_device_box.currentIndex()].get('display_name', "Generic_Device")
                else: cam_name = "Generic_Device"
            elif self.device_combo.currentData() == "Generic_Device": cam_name = "Generic_Device"
            debug_log(f"Ingest: Resolved Camera Profile: {cam_name}"); tc_enabled = self.check_transcode.isChecked(); tc_settings = self.transcode_widget.get_settings()
            if tc_enabled:
                debug_log("Ingest: Transcoding is active - initializing engine"); self.transcode_worker = AsyncTranscoder(tc_settings, self.transcode_widget.is_gpu_enabled())
                self.transcode_worker.log_signal.connect(self.append_transcode_log)
                self.transcode_worker.metrics_signal.connect(self.transcode_metrics_label.setText)
                self.transcode_worker.all_finished_signal.connect(self.on_all_transcodes_finished); self.transcode_worker.start(); self.set_transcode_active(True)
            debug_log("Ingest: Initializing CopyWorker threads"); self.copy_worker = CopyWorker(src, dests, self.project_name_input.text(), self.check_date.isChecked(), self.check_dupe.isChecked(), self.check_videos_only.isChecked(), cam_name, self.check_verify.isChecked(), selected, tc_settings if tc_enabled else None)
            self.copy_worker.log_signal.connect(self.append_copy_log); self.copy_worker.progress_signal.connect(self.progress_bar.setValue); self.copy_worker.status_signal.connect(self.status_label.setText); self.copy_worker.speed_signal.connect(self.speed_label.setText); self.copy_worker.finished_signal.connect(self.on_copy_finished); self.copy_worker.storage_check_signal.connect(self.update_storage_display_bar)
            if tc_enabled: self.copy_worker.file_ready_signal.connect(self.queue_for_transcode); self.copy_worker.transcode_count_signal.connect(self.transcode_worker.set_total_jobs)
            self.copy_worker.start(); debug_log("Ingest: CopyWorker successfully started")
        except Exception as e:
            error_log(f"Ingest Critical Failure: {e}"); QMessageBox.critical(self, "Critical Error", f"Failed to start ingest: {e}"); self.import_btn.setEnabled(True); self.cancel_btn.setEnabled(False)

    def update_storage_display_bar(self, needed, free, is_enough):
        self.storage_bar.setVisible(True); needed_gb = needed / (1024**3); free_gb = free / (1024**3)
        if is_enough:
            percent_usage = int((needed / free) * 100) if free > 0 else 100
            self.storage_bar.setValue(percent_usage); self.storage_bar.setFormat(f"Storage: Will use {needed_gb:.2f} GB of {free_gb:.2f} GB Free"); self.storage_bar.setStyleSheet("QProgressBar::chunk { background-color: #27AE60; }")
        else:
            self.storage_bar.setValue(100); self.storage_bar.setFormat(f"⚠️ INSUFFICIENT SPACE! Need {needed_gb:.2f} GB, Have {free_gb:.2f} GB"); self.storage_bar.setStyleSheet("QProgressBar::chunk { background-color: #C0392B; }")
        if not is_enough: SystemNotifier.notify("Ingest Failed", "Insufficient storage space on destination drive.", "dialog-error")

    def queue_for_transcode(self, src, dest, name):
        if self.transcode_worker:
            if TranscodeEngine.is_edit_friendly(dest, self.transcode_widget.get_settings().get('v_codec')): self.transcode_worker.report_skipped(name); return
            out = os.path.join(os.path.dirname(dest), "Edit_Ready", f"{os.path.splitext(name)[0]}_EDIT.mov"); os.makedirs(os.path.dirname(out), exist_ok=True); self.transcode_worker.add_job(dest, out, name)

    def cancel_import(self):
        if self.copy_worker: self.copy_worker.stop()
        if self.transcode_worker: self.transcode_worker.stop()
        self.import_btn.setEnabled(True); self.cancel_btn.setEnabled(False); self.set_transcode_active(False)

    def on_copy_finished(self, success, msg):
        if not success:
            self.append_copy_log(f"❌ INGEST FAILED: {msg}")
            SystemNotifier.notify("Ingest Failed", msg, "dialog-error")
            QMessageBox.critical(self, "Ingest Error", f"Ingest failed: {msg}")
            self.cancel_import(); self.import_btn.setText("FAILED"); self.import_btn.setStyleSheet("background-color: #C0392B; color: white;")
            return

        mode = self.app.settings.value("report_dest_mode", "project")
        if mode == "fixed": r_path = self.app.settings.value("report_fixed_path", self.dest_input.text())
        elif mode == "custom" and self.report_custom_path: r_path = self.report_custom_path
        else: r_path = self.dest_input.text()
        if self.check_report.isVisible() and self.check_report.isChecked(): self.finalize_report(r_path)
        if self.check_mhl.isVisible() and self.check_mhl.isChecked():
            try: MHLGenerator.generate(r_path, self.copy_worker.transfer_data, self.project_name_input.text() or "CineBridge")
            except: pass

        if self.check_transcode.isChecked() and self.transcode_worker: 
            self.transcode_worker.set_producer_finished(); self.import_btn.setText("TRANSCODING...")
        else:
            v = " and verified" if self.check_verify.isChecked() else ""
            SystemNotifier.notify("Ingest Complete", f"All files offloaded{v}."); JobReportDialog("Ingest Complete", f"<h3>Ingest Successful</h3><p>All selected media has been offloaded{v}.</p>", self).exec()
            self.import_btn.setEnabled(True); self.import_btn.setText("COMPLETE"); self.import_btn.setStyleSheet("background-color: #27AE60; color: white;"); self.set_transcode_active(False); self.reset_timer.start(5000)

    def finalize_report(self, deliverables_path):
        project = self.project_name_input.text() or "Unnamed"; report_path = os.path.join(deliverables_path, f"Transfer_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
        if self.app.settings.value("feature_visual_report", False, type=bool):
            video_files = [f['path'] for f in self.copy_worker.transfer_data if os.path.splitext(f['name'])[1].upper() in DeviceRegistry.VIDEO_EXTS]
            if video_files:
                self.report_thumbs = {}; self.report_thumb_worker = ThumbnailWorker(video_files); self.report_thumb_worker.status_signal.connect(self.status_label.setText); self.report_thumb_worker.thumb_ready.connect(self.on_report_thumb_ready)
                self.report_thumb_worker.finished.connect(lambda: self.generate_final_pdf(report_path, project)); self.report_thumb_worker.start(); return
        self.generate_final_pdf(report_path, project)

    def on_report_thumb_ready(self, path, image):
        ba = QByteArray(); buf = QBuffer(ba); buf.open(QIODevice.OpenModeFlag.WriteOnly); image.save(buf, "PNG")
        self.report_thumbs[os.path.basename(path)] = ba.toBase64().data().decode()

    def generate_final_pdf(self, path, project):
        try: ReportGenerator.generate_pdf(path, self.copy_worker.transfer_data, project, getattr(self, 'report_thumbs', None)); self.append_copy_log(f"📝 Report: {path}"); self.status_label.setText("✅ Ingest & Report Complete!")
        except: pass

    def on_all_transcodes_finished(self):
        SystemNotifier.notify("Job Complete", "Ingest and Transcoding finished."); self.import_btn.setEnabled(True); self.import_btn.setText("COMPLETE"); self.import_btn.setStyleSheet("background-color: #27AE60; color: white;")
        v = " and verified" if self.check_verify.isChecked() else ""; JobReportDialog("Job Complete", f"<h3>Job Successful</h3><p>All ingest{v} and transcode operations finished successfully.<br>Your media is ready for edit.</p>", self).exec(); self.reset_timer.start(30000)

    def save_tab_settings(self):
        s = self.app.settings; s.setValue("last_source", self.source_input.text()); s.setValue("last_dest", self.dest_input.text()); s.setValue("sort_date", self.check_date.isChecked()); s.setValue("skip_dupe", self.check_dupe.isChecked()); s.setValue("filter_mode", self.combo_filter.currentText()); s.setValue("transcode_dnx", self.check_transcode.isChecked()); s.setValue("verify_copy", self.check_verify.isChecked()); s.setValue("gen_report", self.check_report.isChecked()); s.setValue("gen_mhl", self.check_mhl.isChecked()); s.setValue("struct_template", self.structure_template)

    def load_tab_settings(self):
        s = self.app.settings; self.source_input.setText(s.value("last_source", "")); self.dest_input.setText(s.value("last_dest", "")); self.check_date.setChecked(s.value("sort_date", True, type=bool)); self.check_dupe.setChecked(s.value("skip_dupe", True, type=bool)); 
        self.combo_filter.set_checked_texts(s.value("filter_mode", "All Media"))
        self.check_transcode.setChecked(s.value("transcode_dnx", False, type=bool)); self.check_verify.setChecked(s.value("verify_copy", False, type=bool)); self.check_report.setChecked(s.value("gen_report", True, type=bool)); self.check_mhl.setChecked(s.value("gen_mhl", False, type=bool))
        self.structure_template = s.value("struct_template", "{Date}/{Camera}/{Category}")
        self.toggle_transcode_ui(self.check_transcode.isChecked())