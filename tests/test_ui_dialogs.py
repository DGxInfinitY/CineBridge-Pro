import unittest
from PyQt6.QtWidgets import QApplication
import sys
import os

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from modules.ui.dialog_media import VideoPreviewDialog, MediaInfoDialog

# Create a global app instance for UI tests
app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)

class TestUIDialogs(unittest.TestCase):
    def test_video_preview_init(self):
        """Test that VideoPreviewDialog can be initialized without errors."""
        try:
            dialog = VideoPreviewDialog("/tmp/test_video.mp4")
            self.assertIsNotNone(dialog)
        except NameError as e:
            self.fail(f"VideoPreviewDialog raised NameError: {e}")
        except Exception as e:
            self.fail(f"VideoPreviewDialog raised an unexpected exception: {e}")

    def test_media_info_init(self):
        """Test that MediaInfoDialog can be initialized."""
        info = {
            "filename": "test.mp4",
            "container": "mov",
            "duration": 10.0,
            "size_mb": 100.0,
            "video_streams": [],
            "audio_streams": []
        }
        try:
            dialog = MediaInfoDialog(info)
            self.assertIsNotNone(dialog)
        except Exception as e:
            self.fail(f"MediaInfoDialog raised an exception: {e}")

if __name__ == '__main__':
    unittest.main()
