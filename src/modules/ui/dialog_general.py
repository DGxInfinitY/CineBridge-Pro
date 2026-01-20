import os
import sys
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QStyle
)
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt

class JobReportDialog(QDialog):
    def __init__(self, title, message, parent=None):
        super().__init__(parent); self.setWindowTitle(title); self.setFixedWidth(450); layout = QVBoxLayout()
        layout.setContentsMargins(30, 30, 30, 30); layout.setSpacing(20)
        header_lay = QHBoxLayout(); icon_label = QLabel(); icon_label.setPixmap(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton).pixmap(32, 32))
        header_lay.addWidget(icon_label); msg_label = QLabel(message); msg_label.setWordWrap(True); msg_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        header_lay.addWidget(msg_label, 1); layout.addLayout(header_lay)
        ok_btn = QPushButton("OK"); ok_btn.setMinimumHeight(40); ok_btn.setFixedWidth(100); ok_btn.clicked.connect(self.accept)
        btn_lay = QHBoxLayout(); btn_lay.addStretch(); btn_lay.addWidget(ok_btn); btn_lay.addStretch(); layout.addLayout(btn_lay); self.setLayout(layout)

class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent); self.setWindowTitle("About CineBridge Pro"); self.setFixedWidth(400); layout = QVBoxLayout(); layout.setSpacing(15); layout.setContentsMargins(30, 30, 30, 30); logo_label = QLabel(); logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if hasattr(sys, '_MEIPASS'): base_dir = sys._MEIPASS
        else: base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))) # src/
        logo_path = os.path.join(base_dir, "assets", "icon.svg")
        if os.path.exists(logo_path): pixmap = QPixmap(logo_path); logo_label.setPixmap(pixmap.scaled(80, 80, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        layout.addWidget(logo_label); title = QLabel("CineBridge Pro"); title.setStyleSheet("font-size: 22px; font-weight: bold; color: #3498DB;"); title.setAlignment(Qt.AlignmentFlag.AlignCenter);         version = QLabel("v4.17.3 (Dev)"); version.setStyleSheet("font-size: 14px; color: #888;"); version.setAlignment(Qt.AlignmentFlag.AlignCenter); layout.addWidget(version); desc = QLabel("The Linux DIT & Post-Production Suite.\nSolving the 'Resolve on Linux' problem."); desc.setWordWrap(True); desc.setStyleSheet("font-size: 13px;"); desc.setAlignment(Qt.AlignmentFlag.AlignCenter); layout.addWidget(desc); credits = QLabel("<b>Developed by:</b><br>Donovan Goodwin<br>(with Gemini AI)"); credits.setStyleSheet("font-size: 13px;"); credits.setAlignment(Qt.AlignmentFlag.AlignCenter); layout.addWidget(credits); links = QLabel('<a href="mailto:ddg2goodwin@gmail.com" style="color: #3498DB;">ddg2goodwin@gmail.com</a><br><br><a href="https://github.com/DGxInfinitY" style="color: #3498DB;">GitHub: DGxInfinitY</a>'); links.setOpenExternalLinks(True); links.setAlignment(Qt.AlignmentFlag.AlignCenter); layout.addWidget(links); layout.addStretch(); btn_box = QHBoxLayout(); ok_btn = QPushButton("Close"); ok_btn.setFixedWidth(100); ok_btn.clicked.connect(self.accept); btn_box.addStretch(); btn_box.addWidget(ok_btn); btn_box.addStretch(); layout.addLayout(btn_box); self.setLayout(layout)
