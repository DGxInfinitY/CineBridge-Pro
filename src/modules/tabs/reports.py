import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QListWidget, QListWidgetItem, QPushButton, 
    QLabel, QHBoxLayout, QMessageBox, QAbstractItemView, QGroupBox, 
    QComboBox, QLineEdit, QFileDialog
)
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtCore import Qt, QSize
from ..config import AppConfig
from ..utils import EnvUtils

class ReportsTab(QWidget):
    def __init__(self, parent_app=None):
        super().__init__()
        self.app = parent_app
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        self.setLayout(layout)
        
        # --- Configuration Section ---
        config_group = QGroupBox("Report Settings"); config_lay = QVBoxLayout()
        dest_lay = QHBoxLayout()
        dest_lay.addWidget(QLabel("Destination Strategy:"))
        self.combo_dest = QComboBox()
        self.combo_dest.addItem("Follow project folder (Default)", "project")
        self.combo_dest.addItem("Fixed global destination", "fixed")
        self.combo_dest.addItem("Ask / change per job", "custom")
        
        # Load initial setting
        current_mode = "project"
        if self.app: current_mode = self.app.settings.value("report_dest_mode", "project")
        idx = self.combo_dest.findData(current_mode)
        if idx >= 0: self.combo_dest.setCurrentIndex(idx)
        
        dest_lay.addWidget(self.combo_dest, 1)
        config_lay.addLayout(dest_lay)
        
        # Fixed Path UI
        self.fixed_wrap = QWidget(); fixed_lay = QHBoxLayout(self.fixed_wrap); fixed_lay.setContentsMargins(0,0,0,0)
        self.inp_fixed = QLineEdit()
        if self.app: self.inp_fixed.setText(self.app.settings.value("report_fixed_path", ""))
        self.btn_browse_fixed = QPushButton("Browse...")
        self.btn_browse_fixed.clicked.connect(self.browse_fixed)
        fixed_lay.addWidget(QLabel("Global Folder:")); fixed_lay.addWidget(self.inp_fixed); fixed_lay.addWidget(self.btn_browse_fixed)
        config_lay.addWidget(self.fixed_wrap)
        
        # Save Button
        btn_save = QPushButton("Save Report Configuration")
        btn_save.clicked.connect(self.save_settings)
        config_lay.addWidget(btn_save)
        
        config_group.setLayout(config_lay)
        layout.addWidget(config_group)
        
        # Connect logic
        self.combo_dest.currentIndexChanged.connect(self.update_ui_state)
        self.update_ui_state()

        # --- Gallery Section ---
        header = QHBoxLayout()
        header.addWidget(QLabel("<h2>History & Gallery</h2>"))
        header.addStretch()
        
        self.btn_refresh = QPushButton("Refresh List")
        self.btn_refresh.clicked.connect(self.load_reports)
        header.addWidget(self.btn_refresh)
        
        self.btn_open_folder = QPushButton("Open History Folder")
        self.btn_open_folder.clicked.connect(self.open_history_folder)
        header.addWidget(self.btn_open_folder)
        
        layout.addLayout(header)
        
        self.list_widget = QListWidget()
        self.list_widget.setIconSize(QSize(64, 64))
        self.list_widget.setViewMode(QListWidget.ViewMode.IconMode)
        self.list_widget.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.list_widget.setGridSize(QSize(100, 120))
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list_widget.itemDoubleClicked.connect(self.open_report)
        
        layout.addWidget(self.list_widget)
        
        self.load_reports()

    def update_ui_state(self):
        self.fixed_wrap.setVisible(self.combo_dest.currentData() == "fixed")

    def browse_fixed(self):
        d = QFileDialog.getExistingDirectory(self, "Select global report folder", self.inp_fixed.text())
        if d: self.inp_fixed.setText(d)

    def save_settings(self):
        if self.app:
            self.app.settings.setValue("report_dest_mode", self.combo_dest.currentData())
            self.app.settings.setValue("report_fixed_path", self.inp_fixed.text())
            self.app.settings.sync()
            QMessageBox.information(self, "Saved", "Report settings saved.")

    def load_reports(self):
        self.list_widget.clear()
        hist_dir = AppConfig.get_history_dir()
        if not os.path.exists(hist_dir):
            os.makedirs(hist_dir, exist_ok=True)
            return

        files = sorted(
            [f for f in os.listdir(hist_dir) if f.lower().endswith('.pdf')],
            key=lambda x: os.path.getmtime(os.path.join(hist_dir, x)),
            reverse=True
        )
        
        for f in files:
            item = QListWidgetItem(f)
            item.setData(Qt.ItemDataRole.UserRole, os.path.join(hist_dir, f))
            # Use a standard file icon
            item.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_FileIcon))
            item.setToolTip(f)
            self.list_widget.addItem(item)

    def open_report(self, item):
        path = item.data(Qt.ItemDataRole.UserRole)
        EnvUtils.open_file(path)

    def open_history_folder(self):
        EnvUtils.open_file(AppConfig.get_history_dir())
