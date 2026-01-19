import unittest
from unittest.mock import patch, MagicMock
import os
import sys
import time
from PyQt6.QtCore import QThread

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from modules.workers.transcode import BatchTranscodeWorker
from modules.utils import TranscodeEngine

class TestCompletionLogic(unittest.TestCase):

    def setUp(self):
        self.files = ["/tmp/file1.mp4", "/tmp/file2.mp4"]
        self.dest = "/tmp/out"
        self.settings = {'v_codec': 'dnxhd'}

    @patch('modules.workers.transcode.TranscodeEngine.build_command')
    @patch('modules.workers.transcode.TranscodeEngine.get_duration')
    @patch('subprocess.Popen')
    def test_batch_success(self, mock_popen, mock_duration, mock_build):
        # Setup mocks
        mock_build.return_value = ["ffmpeg", "-i", "..."]
        mock_duration.return_value = 10.0
        
        # Mock process
        process_mock = MagicMock()
        process_mock.stderr.readline.side_effect = ["frame=100 fps=25", ""] # Output then EOF
        process_mock.poll.return_value = 0
        process_mock.returncode = 0
        mock_popen.return_value = process_mock

        worker = BatchTranscodeWorker(self.files, self.dest, self.settings)
        
        # Mock signal
        worker.finished_signal = MagicMock()
        
        # Run synchronous part of logic (we can't easily start QThread in unit test without event loop, 
        # but we can call run() directly for logic verification)
        worker.run()
        
        # Verify
        self.assertEqual(mock_popen.call_count, 2)
        worker.finished_signal.emit.assert_called_with(True, "Complete")

    @patch('modules.workers.transcode.TranscodeEngine.build_command')
    @patch('subprocess.Popen')
    def test_batch_cancellation(self, mock_popen, mock_build):
        # Setup mocks
        mock_build.return_value = ["ffmpeg", "-i", "..."]
        
        process_mock = MagicMock()
        # Make readline wait a bit so we can stop it? 
        # Or simpler: Simulate first file success, then stop triggered during second.
        
        # We'll use a side effect to stop the worker during the first file
        def stop_worker(*args, **kwargs):
            worker.stop()
            return "" # EOF immediately to exit loop
            
        process_mock.stderr.readline.side_effect = stop_worker
        process_mock.poll.return_value = None # Process still running when we check
        mock_popen.return_value = process_mock

        worker = BatchTranscodeWorker(self.files, self.dest, self.settings)
        worker.finished_signal = MagicMock()
        
        worker.run()
        
        # Should NOT emit success signal because it was stopped
        worker.finished_signal.emit.assert_not_called()
        
        # Should kill process
        process_mock.kill.assert_called()

    @patch('modules.workers.transcode.TranscodeEngine.build_command')
    def test_invalid_command_skip(self, mock_build):
        # Setup mocks
        mock_build.return_value = None # Invalid command
        
        worker = BatchTranscodeWorker(self.files, self.dest, self.settings)
        worker.log_signal = MagicMock()
        worker.finished_signal = MagicMock()
        
        worker.run()
        
        # Should skip both files but still finish batch
        self.assertEqual(worker.log_signal.emit.call_count, 2) # 2 warnings
        worker.finished_signal.emit.assert_called_with(True, "Complete")

if __name__ == '__main__':
    unittest.main()
