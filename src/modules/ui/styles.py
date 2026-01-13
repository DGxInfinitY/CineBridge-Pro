from PyQt6.QtGui import QPalette
from PyQt6.QtWidgets import QApplication

class ThemeManager:
    LIGHT_STYLE = """
        QMainWindow, QWidget { 
            background-color: #F0F2F5; 
            color: #333; 
            font-family: 'Segoe UI'; 
            font-size: 14px; 
        } 
        QGroupBox { 
            background: #FFF; 
            border: 1px solid #CCC; 
            border-radius: 5px; 
            margin-top: 20px; 
            font-weight: bold; 
        } 
        QGroupBox::title { 
            subcontrol-origin: margin; 
            left: 10px; 
            padding: 0 5px; 
            color: #2980B9; 
        } 
        QLineEdit, QComboBox, QTextEdit, QListWidget { 
            background: #FFF; 
            border: 1px solid #CCC; 
            color: #333; 
        } 
        QPushButton { 
            background: #E0E0E0; 
            border: 1px solid #CCC; 
            color: #333; 
            padding: 8px; 
        } 
        QPushButton:hover { 
            background: #D0D0D0; 
        } 
        QPushButton#StartBtn { 
            background: #3498DB; 
            color: white; 
            font-weight: bold; 
        } 
        QPushButton#StopBtn { 
            background: #E74C3C; 
            color: white; 
            font-weight: bold; 
        } 
        QTabWidget::pane { 
            border: 1px solid #CCC; 
        } 
        QTabBar::tab { 
            background: #E0E0E0; 
            color: #555; 
            border: 1px solid #CCC; 
        } 
        QTabBar::tab:selected { 
            background: #FFF; 
            color: #2980B9; 
            border-top: 2px solid #2980B9; 
        } 
        QFrame#ResultCard, QFrame#DashFrame { 
            background-color: #FFF; 
            border-radius: 8px; 
        }
    """

    DARK_STYLE = """
        QMainWindow, QWidget { 
            background-color: #2b2b2b; 
            color: #e0e0e0; 
            font-family: 'Segoe UI'; 
            font-size: 14px; 
        } 
        QGroupBox { 
            background: #333; 
            border: 1px solid #444; 
            border-radius: 5px; 
            margin-top: 20px; 
            font-weight: bold; 
        } 
        QGroupBox::title { 
            subcontrol-origin: margin; 
            left: 10px; 
            padding: 0 5px; 
            color: #3498DB; 
        } 
        QLineEdit, QComboBox, QTextEdit, QListWidget { 
            background: #1e1e1e; 
            border: 1px solid #555; 
            color: white; 
        } 
        QPushButton { 
            background: #444; 
            border: 1px solid #555; 
            color: white; 
            padding: 8px; 
        } 
        QPushButton:hover { 
            background: #555; 
        } 
        QPushButton#StartBtn { 
            background: #2980B9; 
            font-weight: bold; 
        } 
        QPushButton#StopBtn { 
            background: #C0392B; 
            font-weight: bold; 
        } 
        QTabWidget::pane { 
            border: 1px solid #444; 
        } 
        QTabBar::tab { 
            background: #222; 
            color: #888; 
            border: 1px solid #444; 
        } 
        QTabBar::tab:selected { 
            background: #333; 
            color: #3498DB; 
            border-top: 2px solid #3498DB; 
        } 
        QFrame#ResultCard, QFrame#DashFrame { 
            background-color: #1e1e1e; 
            border-radius: 8px; 
        }
    """

    @staticmethod
    def is_dark_mode():
        try:
            return QApplication.palette().color(QPalette.ColorRole.Window).lightness() < 128
        except:
            return False

    @staticmethod
    def get_style(mode):
        if mode == "dark":
            return ThemeManager.DARK_STYLE
        elif mode == "light":
            return ThemeManager.LIGHT_STYLE
        else: # system
            return ThemeManager.DARK_STYLE if ThemeManager.is_dark_mode() else ThemeManager.LIGHT_STYLE
