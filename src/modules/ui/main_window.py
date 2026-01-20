import sys
import os
import platform
import subprocess
from PyQt6.QtWidgets import QApplication, QMainWindow, QTabWidget, QToolButton, QMessageBox
from PyQt6.QtGui import QIcon, QPalette
from PyQt6.QtCore import Qt, QSettings, QTimer, QThread, pyqtSignal

from ..config import DEBUG_MODE, AppLogger, AppConfig, debug_log
from ..utils import EnvUtils
from ..workers import SystemMonitor
from .styles import ThemeManager
from .dialog_settings import SettingsDialog, AdvancedFeaturesDialog
from .dialog_general import AboutDialog
from ..tabs import IngestTab, ConvertTab, DeliveryTab, WatchTab, ReportsTab

class ThemeWorker(QThread):
    result_signal = pyqtSignal(bool)
    def run(self):
        is_dark = False
        if platform.system() == "Linux":
            try:
                res = subprocess.run(["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"], capture_output=True, text=True, timeout=0.5, env=EnvUtils.get_clean_env())
                if "prefer-dark" in res.stdout: is_dark = True
                else:
                    res2 = subprocess.run(["gsettings", "get", "org.gnome.desktop.interface", "gtk-theme"], capture_output=True, text=True, timeout=0.5, env=EnvUtils.get_clean_env())
                    if "dark" in res2.stdout.lower(): is_dark = True
            except: pass
        else:
            # Fallback for non-Linux or manual
            pass 
        self.result_signal.emit(is_dark)

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
            # We are in src/modules/ui/main_window.py
            # Base dir should be src/../
            # os.path.abspath(__file__) is src/modules/ui/main_window.py
            # dirname -> src/modules/ui
            # dirname -> src/modules
            # dirname -> src
            # dirname -> root
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            if not os.path.exists(os.path.join(base_dir, "assets")):
                 # Fallback?
                 pass

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
        self.tab_reports = ReportsTab(self)
        self.tab_watch = WatchTab()
        
        self.tabs.addTab(self.tab_ingest, "📥 INGEST")
        self.tabs.addTab(self.tab_convert, "🛠️ CONVERT")
        self.tabs.addTab(self.tab_delivery, "🚀 DELIVERY")
        # Reports and Watch tabs are added dynamically via update_feature_visibility
        
        self.setCentralWidget(self.tabs)
        
        # Global Signal Connections
        self.tab_ingest.transcode_widget.chk_gpu.toggled.connect(self.sync_gpu_toggle)
        self.tab_convert.settings.chk_gpu.toggled.connect(self.sync_gpu_toggle)
        self.tab_delivery.settings.chk_gpu.toggled.connect(self.sync_gpu_toggle)
        self.tab_watch.settings.chk_gpu.toggled.connect(self.sync_gpu_toggle)
        
        # Global System Monitor
        self.sys_monitor = SystemMonitor()
        self.sys_monitor.stats_signal.connect(self.tab_ingest.update_load_display)
        self.sys_monitor.stats_signal.connect(self.tab_convert.update_load_display)
        self.sys_monitor.stats_signal.connect(self.tab_delivery.update_load_display)
        self.sys_monitor.stats_signal.connect(self.tab_watch.update_load_display)
        self.sys_monitor.start()

        # Startup Logic
        # We need to set DEBUG_MODE in config
        from .. import config
        config.DEBUG_MODE = self.settings.value("debug_mode", False, type=bool)
        
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
        
        if hasattr(self, 'sys_monitor'):
            self.sys_monitor.stop()
            self.sys_monitor.wait(1000)
            
        event.accept()

    def check_system_theme(self):
        if self.theme_mode != "system": return
        if platform.system() == "Linux":
            if not hasattr(self, 'theme_worker'):
                self.theme_worker = ThemeWorker()
                self.theme_worker.result_signal.connect(self.on_theme_result)
            if not self.theme_worker.isRunning():
                self.theme_worker.start()
        else:
            self.on_theme_result(ThemeManager.is_dark_mode())

    def on_theme_result(self, is_dark):
        current_app_is_dark = getattr(self, 'current_applied_is_dark', None)
        if current_app_is_dark is None or is_dark != current_app_is_dark: 
            self.set_theme("system", force_is_dark=is_dark)

    def is_system_dark(self):
        if platform.system() == "Linux":
            try:
                res = subprocess.run(["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"], capture_output=True, text=True, timeout=0.5, env=EnvUtils.get_clean_env())
                if "prefer-dark" in res.stdout: return True
                res2 = subprocess.run(["gsettings", "get", "org.gnome.desktop.interface", "gtk-theme"], capture_output=True, text=True, timeout=0.5, env=EnvUtils.get_clean_env())
                if "dark" in res2.stdout.lower(): return True
            except: pass
        return ThemeManager.is_dark_mode()

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

        # Reports Tab Visibility Logic
        show_pdf = self.settings.value("feature_pdf_report", False, type=bool)
        show_mhl = self.settings.value("feature_mhl", False, type=bool)
        show_reports = show_pdf or show_mhl
        
        reports_idx = -1
        for i in range(self.tabs.count()):
            if "REPORTS" in self.tabs.tabText(i).upper():
                reports_idx = i; break
        
        if show_reports:
            if reports_idx == -1: self.tabs.insertTab(3, self.tab_reports, "📊 REPORTS")
        else:
            if reports_idx != -1: self.tabs.removeTab(reports_idx)
        
        # Fix resize bug: Ensure window shrinks if possible after hiding widgets
        # But ensure we don't look 'skinny' by enforcing a minimum width
        self.setMinimumWidth(1000)
        QTimer.singleShot(100, lambda: self.adjustSize())

    def reset_to_defaults(self):
        reply = QMessageBox.question(self, "Confirm Reset", "Are you sure you want to reset all settings to default? This cannot be undone.", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.settings.clear()
            self.settings.sync()
            self.set_theme("light")
            self.tab_ingest.check_date.setChecked(True)
            self.tab_ingest.check_dupe.setChecked(True)
            self.tab_ingest.check_transcode.setChecked(False)
            self.tab_ingest.toggle_logs(True, False)
            self.sync_gpu_toggle(False)
            QMessageBox.information(self, "Reset", "Settings have been reset to defaults.")

    def sync_gpu_toggle(self, checked):
        for widget in [self.tab_ingest.transcode_widget, self.tab_convert.settings, self.tab_delivery.settings]: 
            widget.set_gpu_checked(checked)
        self.settings.setValue("use_gpu_accel", checked)

    def toggle_debug(self, checked): 
        from .. import config
        config.DEBUG_MODE = checked
        self.settings.setValue("debug_mode", checked)
        debug_log(f"Debug logging {'active' if checked else 'disabled'}.")

    def show_about(self): 
        dlg = AboutDialog(self)
        dlg.exec()

    def set_theme(self, mode, force_is_dark=None):
        self.theme_mode = mode
        self.settings.setValue("theme_mode", mode)
        
        is_dark = False
        if mode == "dark": is_dark = True
        elif mode == "light": is_dark = False
        else: # system
            if force_is_dark is not None: is_dark = force_is_dark
            else: is_dark = self.is_system_dark()
            
        self.current_applied_is_dark = is_dark
        self.setStyleSheet(ThemeManager.get_style("dark" if is_dark else "light"))
        
        if hasattr(self, 'tab_ingest') and self.tab_ingest.result_card.isVisible():
             if self.tab_ingest.current_detected_path:
                 info = {'path': self.tab_ingest.current_detected_path, 'type': self.tab_ingest.device_combo.currentText(), 'empty': False}
                 self.tab_ingest.update_result_ui(info, multi=self.tab_ingest.select_device_box.isVisible())
