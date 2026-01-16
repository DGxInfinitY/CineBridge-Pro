import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QListWidget, QListWidgetItem, QPushButton, 
    QLabel, QHBoxLayout, QMessageBox, QAbstractItemView
)
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtCore import Qt, QSize
from ..config import AppConfig
from ..utils import EnvUtils

class GalleryTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        self.setLayout(layout)
        
        header = QHBoxLayout()
        header.addWidget(QLabel("<h2>Job Reports Gallery</h2>"))
        header.addStretch()
        
        self.btn_refresh = QPushButton("Refresh Gallery")
        self.btn_refresh.clicked.connect(self.load_reports)
        header.addWidget(self.btn_refresh)
        
        self.btn_open_folder = QPushButton("Open Folder")
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
            # Use a standard file icon or placeholder
            item.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_FileIcon))
            item.setToolTip(f)
            self.list_widget.addItem(item)

    def open_report(self, item):
        path = item.data(Qt.ItemDataRole.UserRole)
        EnvUtils.open_file(path)

    def open_history_folder(self):
        EnvUtils.open_file(AppConfig.get_history_dir())
