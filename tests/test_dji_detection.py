import unittest
from unittest.mock import patch, MagicMock
import os
import sys

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from modules.utils import DeviceRegistry, MediaInfoExtractor

class TestDJIDetection(unittest.TestCase):
    
    @patch('modules.utils.DeviceRegistry.safe_list_dir')
    @patch('modules.utils.MediaInfoExtractor.get_device_metadata')
    def test_dji_model_identification(self, mock_metadata, mock_list_dir):
        # Setup common mock behavior for file system
        # Simulate DJI folder structure
        mock_list_dir.side_effect = lambda path: (
            ["DCIM"] if path == "/mnt/dji" else 
            ["100MEDIA"] if path == "/mnt/dji/DCIM" else 
            ["DJI_0001.MP4"] if path == "/mnt/dji/DCIM/100MEDIA" else []
        )

        # Test Case 1: DJI Avata 2
        mock_metadata.return_value = {"model": "FC8284"}
        name, root, exts = DeviceRegistry.identify("/mnt/dji")
        self.assertEqual(name, "DJI Avata 2")
        self.assertEqual(root, "/mnt/dji/DCIM/100MEDIA")

        # Test Case 2: DJI Action 2 (Osmo)
        mock_metadata.return_value = {"model": "OT-210"}
        name, root, exts = DeviceRegistry.identify("/mnt/dji")
        self.assertEqual(name, "DJI Action 2")

        # Test Case 3: Unknown DJI Model
        mock_metadata.return_value = {"model": "FutureDrone 9000"}
        name, root, exts = DeviceRegistry.identify("/mnt/dji")
        self.assertEqual(name, "DJI FutureDrone 9000")

    @patch('modules.utils.DeviceRegistry.safe_list_dir')
    def test_dji_fallback(self, mock_list_dir):
        # Test fallback if metadata extraction fails
        mock_list_dir.side_effect = lambda path: (
            ["DCIM"] if path == "/mnt/dji" else 
            ["100MEDIA"] if path == "/mnt/dji/DCIM" else 
            ["DJI_0001.MP4"] if path == "/mnt/dji/DCIM/100MEDIA" else []
        )
        
        # Mock get_device_metadata to raise exception or return empty
        with patch('modules.utils.MediaInfoExtractor.get_device_metadata', side_effect=Exception("Probe failed")):
            name, root, exts = DeviceRegistry.identify("/mnt/dji")
            self.assertEqual(name, "DJI Device") # Should fallback to generic profile name

if __name__ == '__main__':
    unittest.main()
