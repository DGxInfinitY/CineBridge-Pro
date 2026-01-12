import sys
import os
import signal
import platform
import subprocess
from PyQt6.QtWidgets import QApplication, QMainWindow, QTabWidget, QToolButton, QMessageBox
from PyQt6.QtGui import QIcon, QPalette
from PyQt6.QtCore import Qt, QSettings, QTimer

# Import Modules
from modules.config import DEBUG_MODE, AppLogger, AppConfig, debug_log
from modules.utils import EnvUtils
from modules.workers import SystemMonitor
from modules.widgets import SettingsDialog, AboutDialog
from modules.tabs import IngestTab, ConvertTab, DeliveryTab, WatchTab

class CineBridgeApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CineBridge Pro: Open Source DIT Suite")
        self.setGeometry(100, 100, 1100, 850)
        self.settings = QSettings("CineBridgePro", "Config")
        
        # Icon Setup
        if hasattr(sys, '_MEIPASS'):
            base_dir = sys._MEIPASS
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__)) # src/
            if not os.path.exists(os.path.join(base_dir, "assets")):
                 # If running from src/cinebridge.py, assets are in ../assets
                 base_dir = os.path.dirname(base_dir)

        icon_svg = os.path.join(base_dir, "assets", "icon.svg")
        icon_png = os.path.join(base_dir, "assets", "icon.png")
        if os.path.exists(icon_svg): self.setWindowIcon(QIcon(icon_svg))
        elif os.path.exists(icon_png): self.setWindowIcon(QIcon(icon_png))

        # Main Tabs
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.TabPosition.North)
        self.tabs.setStyleSheet("QTabBar::tab { height: 40px; width: 150px; font-weight: bold; }")
        
        # Settings Button
        self.settings_btn = QToolButton()
        self.settings_btn.setText("⚙")
        self.settings_btn.setStyleSheet("QToolButton { font-size: 20px; border: none; background: transparent; padding: 5px; } QToolButton:hover { color: #3498DB; }")
        self.settings_btn.clicked.connect(self.open_settings)
        self.tabs.setCornerWidget(self.settings_btn, Qt.Corner.TopRightCorner)
        
        # Initialize Tabs
        self.tab_ingest = IngestTab(self)
        self.tab_convert = ConvertTab()
        self.tab_delivery = DeliveryTab()
        self.tab_watch = WatchTab()
        
        self.tabs.addTab(self.tab_ingest, "📥 INGEST")
        self.tabs.addTab(self.tab_convert, "🛠️ CONVERT")
        self.tabs.addTab(self.tab_delivery, "🚀 DELIVERY")
        # Watch tab is added dynamically via update_feature_visibility
        
        self.setCentralWidget(self.tabs)
        
        # Global Signal Connections
        self.tab_ingest.transcode_widget.chk_gpu.toggled.connect(self.sync_gpu_toggle)
        self.tab_convert.settings.chk_gpu.toggled.connect(self.sync_gpu_toggle)
        self.tab_delivery.settings.chk_gpu.toggled.connect(self.sync_gpu_toggle)
        self.tab_watch.settings.chk_gpu.toggled.connect(self.sync_gpu_toggle)
        
        # Global System Monitor
        self.sys_monitor = SystemMonitor()
        self.sys_monitor.cpu_signal.connect(self.tab_ingest.update_load_display)
        self.sys_monitor.cpu_signal.connect(self.tab_convert.update_load_display)
        self.sys_monitor.start()

        # Startup Logic
        self.update_feature_visibility()
        saved_gpu = self.settings.value("use_gpu_accel", False, type=bool)
        self.sync_gpu_toggle(saved_gpu)
        
        self.theme_mode = self.settings.value("theme_mode", "light")
        self.set_theme(self.theme_mode)
        
        self.theme_timer = QTimer(self)
        self.theme_timer.timeout.connect(self.check_system_theme)
        self.theme_timer.start(2000)
    
    def closeEvent(self, event):
        """Forces a save of all critical settings and ensures safe worker shutdown."""
        try:
            if hasattr(self, 'tab_convert'):
                for worker in self.tab_convert.thumb_workers:
                    worker.stop()
                    if not worker.wait(500): worker.terminate()
        except: pass
        
        self.tab_ingest.save_tab_settings()
        self.settings.setValue("show_copy_log", self.tab_ingest.copy_log.isVisible())
        self.settings.setValue("show_trans_log", self.tab_ingest.transcode_log.isVisible())
        self.settings.sync() 
        event.accept()

    def check_system_theme(self):
        if self.theme_mode != "system": return
        system_is_dark = self.is_system_dark()
        current_app_is_dark = getattr(self, 'current_applied_is_dark', None)
        if current_app_is_dark is None or system_is_dark != current_app_is_dark: 
            self.set_theme("system")

    def is_system_dark(self):
        if platform.system() == "Linux":
            try:
                res = subprocess.run(["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"], capture_output=True, text=True, timeout=0.5, env=EnvUtils.get_clean_env())
                if "prefer-dark" in res.stdout: return True
                res2 = subprocess.run(["gsettings", "get", "org.gnome.desktop.interface", "gtk-theme"], capture_output=True, text=True, timeout=0.5, env=EnvUtils.get_clean_env())
                if "dark" in res2.stdout.lower(): return True
            except: pass
        try: return QApplication.palette().color(QPalette.ColorRole.Window).lightness() < 128
        except: return False

    def open_settings(self): 
        dlg = SettingsDialog(self)
        dlg.exec()
    
    def update_feature_visibility(self):
        show_watch = self.settings.value("feature_watch_folder", False, type=bool)
        if hasattr(self, 'sender') and self.sender() and hasattr(self.sender(), 'text'):
            if "Watch Folder" in self.sender().text():
                show_watch = self.sender().isChecked()
                self.settings.setValue("feature_watch_folder", show_watch)
        
        watch_idx = -1
        for i in range(self.tabs.count()):
            if self.tabs.tabText(i) == "Watch Folder":
                watch_idx = i; break
        
        if show_watch:
            if watch_idx == -1: self.tabs.addTab(self.tab_watch, "Watch Folder")
        else:
            if watch_idx != -1: self.tabs.removeTab(watch_idx)

        show_burn = self.settings.value("feature_burn_in", False, type=bool)
        if hasattr(self, 'sender') and self.sender() and hasattr(self.sender(), 'text'):
            if "Burn-in" in self.sender().text():
                show_burn = self.sender().isChecked()
                self.settings.setValue("feature_burn_in", show_burn)

        for tab in [self.tab_ingest, self.tab_convert, self.tab_delivery, self.tab_watch]:
            if hasattr(tab, 'transcode_widget'): tab.transcode_widget.overlay_group.setVisible(show_burn)
            elif hasattr(tab, 'settings'): tab.settings.overlay_group.setVisible(show_burn)

        # Multi-Dest Logic
        show_multi = self.settings.value("feature_multi_dest", False, type=bool)
        if hasattr(self, 'sender') and self.sender() and hasattr(self.sender(), 'text'):
            if "Multi-Destination" in self.sender().text():
                show_multi = self.sender().isChecked()
                self.settings.setValue("feature_multi_dest", show_multi)
        
        # Visual Report Logic
        show_visual = self.settings.value("feature_visual_report", False, type=bool)
        if hasattr(self, 'sender') and self.sender() and hasattr(self.sender(), 'text'):
            if "Visual PDF" in self.sender().text():
                show_visual = self.sender().isChecked()
                self.settings.setValue("feature_visual_report", show_visual)
        
        # Notify IngestTab to refresh its UI layout
        if hasattr(self, 'tab_ingest'):
            self.tab_ingest.update_pro_features_ui(show_multi, show_visual)

    def reset_to_defaults(self):
        reply = QMessageBox.question(self, "Confirm Reset", "Are you sure you want to reset all settings to default? This cannot be undone.", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.settings.clear()
            self.settings.sync()
            self.set_theme("light")
            self.tab_ingest.check_date.setChecked(True)
            self.tab_ingest.check_dupe.setChecked(True)
            self.tab_ingest.check_videos_only.setChecked(False)
            self.tab_ingest.check_transcode.setChecked(False)
            self.tab_ingest.toggle_logs(True, False)
            self.sync_gpu_toggle(False)
            QMessageBox.information(self, "Reset", "Settings have been reset to defaults.")

    def sync_gpu_toggle(self, checked):
        for widget in [self.tab_ingest.transcode_widget, self.tab_convert.settings, self.tab_delivery.settings]: 
            widget.set_gpu_checked(checked)
        self.settings.setValue("use_gpu_accel", checked)

    def toggle_debug(self): 
        # Modifying global variable in config module
        import modules.config
        modules.config.DEBUG_MODE = not modules.config.DEBUG_MODE
        debug_log("Debug logging active.")

    def show_about(self): 
        dlg = AboutDialog(self)
        dlg.exec()

    def set_theme(self, mode):
        self.theme_mode = mode
        self.settings.setValue("theme_mode", mode)
        is_dark = False
        if mode == "dark": is_dark = True
        elif mode == "system": is_dark = self.is_system_dark()
        self.current_applied_is_dark = is_dark
        
        style = """QMainWindow, QWidget { background-color: #F0F2F5; color: #333; font-family: 'Segoe UI'; font-size: 14px; } QGroupBox { background: #FFF; border: 1px solid #CCC; border-radius: 5px; margin-top: 20px; font-weight: bold; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; color: #2980B9; } QLineEdit, QComboBox, QTextEdit, QListWidget { background: #FFF; border: 1px solid #CCC; color: #333; } QPushButton { background: #E0E0E0; border: 1px solid #CCC; color: #333; padding: 8px; } QPushButton:hover { background: #D0D0D0; } QPushButton#StartBtn { background: #3498DB; color: white; font-weight: bold; } QPushButton#StopBtn { background: #E74C3C; color: white; font-weight: bold; } QTabWidget::pane { border: 1px solid #CCC; } QTabBar::tab { background: #E0E0E0; color: #555; border: 1px solid #CCC; } QTabBar::tab:selected { background: #FFF; color: #2980B9; border-top: 2px solid #2980B9; } QFrame#ResultCard, QFrame#DashFrame { background-color: #FFF; border-radius: 8px; }"""
        
        if is_dark: 
            style = """QMainWindow, QWidget { background-color: #2b2b2b; color: #e0e0e0; font-family: 'Segoe UI'; font-size: 14px; } QGroupBox { background: #333; border: 1px solid #444; border-radius: 5px; margin-top: 20px; font-weight: bold; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; color: #3498DB; } QLineEdit, QComboBox, QTextEdit, QListWidget { background: #1e1e1e; border: 1px solid #555; color: white; } QPushButton { background: #444; border: 1px solid #555; color: white; padding: 8px; } QPushButton:hover { background: #555; } QPushButton#StartBtn { background: #2980B9; font-weight: bold; } QPushButton#StopBtn { background: #C0392B; font-weight: bold; } QTabWidget::pane { border: 1px solid #444; } QTabBar::tab { background: #222; color: #888; border: 1px solid #444; } QTabBar::tab:selected { background: #333; color: #3498DB; border-top: 2px solid #3498DB; } QFrame#ResultCard, QFrame#DashFrame { background-color: #1e1e1e; border-radius: 8px; }"""
        
        self.setStyleSheet(style)
        
        if hasattr(self, 'tab_ingest') and self.tab_ingest.result_card.isVisible():
             if self.tab_ingest.current_detected_path:
                 info = {'path': self.tab_ingest.current_detected_path, 'type': self.tab_ingest.device_combo.currentText(), 'empty': False}
                 self.tab_ingest.update_result_ui(info, multi=self.tab_ingest.select_device_box.isVisible())

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    AppLogger.init_log()
    app = QApplication(sys.argv)
    app.setDesktopFileName("CineBridgePro")
    
    # Dummy timer to allow Ctrl+C to work
    timer = QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None) 
    
    app.setStyle("Fusion")
    window = CineBridgeApp()
    window.show()
    sys.exit(app.exec())