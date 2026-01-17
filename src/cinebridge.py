import sys
import signal
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from modules.config import AppLogger
from modules.ui.main_window import CineBridgeApp

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
