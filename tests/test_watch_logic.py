import unittest
from unittest.mock import patch, MagicMock
import os
import sys
from PyQt6.QtWidgets import QApplication

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

# Create app
app = QApplication(sys.argv)

from modules.tabs.watch import WatchTab

class TestWatchLogic(unittest.TestCase):
    
    @patch('os.listdir')
    @patch('os.path.exists')
    @patch('os.path.isfile')
    @patch('os.path.getsize')
    def test_watch_detection(self, mock_getsize, mock_isfile, mock_exists, mock_listdir):
        tab = WatchTab()
        tab.inp_watch.setText("/watch")
        
        # Setup mocks
        mock_exists.return_value = True
        mock_listdir.return_value = ["file1.mp4", "image.jpg"] # Should ignore image based on logic?
        # Logic uses DeviceRegistry.VIDEO_EXTS. .jpg is not video.
        
        mock_isfile.return_value = True
        mock_getsize.return_value = 1000
        
        # Mock start_batch to verify trigger
        tab.start_batch = MagicMock()
        
        # Run check (pass 1: detect)
        tab.check_folder()
        
        # Check if file1.mp4 is monitored
        # Full path constructed in logic: os.path.join(path, f)
        target = "/watch/file1.mp4"
        self.assertIn(target, tab.monitored_files)
        
        # Check if image is ignored
        img_target = "/watch/image.jpg"
        self.assertNotIn(img_target, tab.monitored_files)
        
        tab.start_batch.assert_not_called()
        
        # Run check (pass 2: stabilize)
        # Manually age the timestamp
        tab.monitored_files[target]['stable_since'] -= 10 
        
        tab.check_folder()
        tab.start_batch.assert_called()
        
        # Verify it was passed correctly
        args = tab.start_batch.call_args[0][0]
        self.assertIn(target, args)

if __name__ == '__main__':
    unittest.main()
