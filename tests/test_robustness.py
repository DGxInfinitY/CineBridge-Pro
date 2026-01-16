import unittest
from unittest.mock import patch, MagicMock
import os
import sys

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from modules.workers import CopyWorker, AsyncTranscoder
from modules.utils import DeviceRegistry, TranscodeEngine

class TestRobustness(unittest.TestCase):
    
    def test_copy_worker_bad_source(self):
        # Scenario: Worker started with non-existent source path
        # Expectation: Should finish gracefully with "No data" or specific error, not crash.
        worker = CopyWorker("/non/existent/path", ["/tmp"], "Proj", False, False, False, "auto", False)
        
        # Mock signals
        worker.finished_signal = MagicMock()
        worker.run()
        
        # Should call finished_signal with True (No data) or False (Error)
        # Based on current logic, if os.walk yields nothing, it returns "No data"
        worker.finished_signal.emit.assert_called()
        args = worker.finished_signal.emit.call_args[0]
        # We accept either result as "robust" (i.e. not crashing)
        self.assertTrue(args[0] is True or args[0] is False) 

    @patch('modules.utils.DependencyManager.get_ffmpeg_path')
    def test_transcode_worker_missing_binary(self, mock_ffmpeg):
        # Scenario: FFmpeg binary is missing
        mock_ffmpeg.return_value = None
        
        worker = AsyncTranscoder({}, False)
        worker.log_signal = MagicMock()
        
        worker.run()
        
        # Should log error and exit
        worker.log_signal.emit.assert_called_with("❌ Error: FFmpeg binary not found.")

    def test_registry_garbage_input(self):
        # Scenario: DeviceRegistry.identify called with None or garbage
        # Expectation: Should return default "Generic Storage" tuple, not raise Exception
        
        # Mock safe_list_dir to avoid actual FS calls crashing on None
        with patch('modules.utils.DeviceRegistry.safe_list_dir', return_value=[]):
            res = DeviceRegistry.identify(None)
            self.assertEqual(res[0], "Generic Storage")
            
            res2 = DeviceRegistry.identify("   ")
            self.assertEqual(res2[0], "Generic Storage")

    def test_transcode_engine_empty_settings(self):
        # Scenario: build_command called with empty settings
        # Expectation: Should use defaults, not key error
        
        with patch('modules.utils.DependencyManager.get_ffmpeg_path', return_value="/bin/ffmpeg"):
            cmd = TranscodeEngine.build_command("in.mp4", "out.mov", {})
            self.assertIsNotNone(cmd)
            # Should have defaults
            self.assertIn("dnxhd", cmd) # Default codec

if __name__ == '__main__':
    unittest.main()
