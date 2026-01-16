import unittest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
import sys
import os

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from modules.ui.widgets import CheckableComboBox

# Create app instance for widgets
app = QApplication(sys.argv)

class TestUIWidgets(unittest.TestCase):
    def test_checkable_combo_logic(self):
        combo = CheckableComboBox()
        combo.add_check_item("Video", {"mp4", "mov"})
        combo.add_check_item("Audio", {"wav", "mp3"})
        
        # Test initial state (unchecked)
        self.assertEqual(combo.lineEdit().text(), "All Media")
        self.assertEqual(len(combo.get_checked_data()), 0)
        
        # Test checking an item
        # Simulate check by setting state directly on model (since handle_item_pressed needs view interaction)
        combo.p_model.item(0).setCheckState(Qt.CheckState.Checked)
        combo.update_text()
        
        self.assertEqual(combo.lineEdit().text(), "Video")
        self.assertEqual(len(combo.get_checked_data()), 1)
        self.assertEqual(combo.get_checked_data()[0], {"mp4", "mov"})
        
        # Test multiple check
        combo.p_model.item(1).setCheckState(Qt.CheckState.Checked)
        combo.update_text()
        
        self.assertIn("Video", combo.lineEdit().text())
        self.assertIn("Audio", combo.lineEdit().text())
        self.assertEqual(len(combo.get_checked_data()), 2)
        
        # Test unchecking all
        combo.p_model.item(0).setCheckState(Qt.CheckState.Unchecked)
        combo.p_model.item(1).setCheckState(Qt.CheckState.Unchecked)
        combo.update_text()
        
        self.assertEqual(combo.lineEdit().text(), "All Media")
        
    def test_set_checked_texts(self):
        combo = CheckableComboBox()
        combo.add_check_item("Video")
        combo.add_check_item("Audio")
        
        combo.set_checked_texts("Video, Audio")
        self.assertEqual(combo.p_model.item(0).checkState(), Qt.CheckState.Checked)
        self.assertEqual(combo.p_model.item(1).checkState(), Qt.CheckState.Checked)
        
        combo.set_checked_texts("All Media")
        self.assertEqual(combo.p_model.item(0).checkState(), Qt.CheckState.Unchecked)

if __name__ == '__main__':
    unittest.main()
