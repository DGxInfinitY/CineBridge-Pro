import unittest
from PyQt6.QtWidgets import QApplication
import sys
import os

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

# Create app instance for widgets (required for UI tests)
app = QApplication(sys.argv)

from modules.tabs import IngestTab, ConvertTab, DeliveryTab, ReportsTab, WatchTab

class TestUIIntegration(unittest.TestCase):
    
    def test_ingest_tab_init(self):
        # Mock parent app with settings
        from PyQt6.QtCore import QSettings
        class MockApp:
            settings = QSettings("TestCineBridge", "Test")
        
        tab = IngestTab(MockApp())
        self.assertIsNotNone(tab)
        # Verify critical widgets exist
        self.assertTrue(hasattr(tab, 'btn_structure'))
        self.assertTrue(hasattr(tab, 'combo_filter'))

    def test_convert_tab_init(self):
        tab = ConvertTab()
        self.assertIsNotNone(tab)

    def test_delivery_tab_init(self):
        tab = DeliveryTab()
        self.assertIsNotNone(tab)

    def test_reports_tab_init(self):
        tab = ReportsTab()
        self.assertIsNotNone(tab)

    def test_watch_tab_init(self):
        tab = WatchTab()
        self.assertIsNotNone(tab)

if __name__ == '__main__':
    unittest.main()
