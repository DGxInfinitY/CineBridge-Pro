import unittest
from unittest.mock import patch, MagicMock
import os
import sys

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from modules.workers import AsyncTranscoder, CopyWorker

class TestWorkers(unittest.TestCase):
    
    def test_transcoder_queue_logic(self):
        settings = {'v_codec': 'dnxhd'}
        worker = AsyncTranscoder(settings, use_gpu=False)
        
        self.assertEqual(len(worker.queue), 0)
        worker.add_job("in.mp4", "out.mov", "file1")
        self.assertEqual(len(worker.queue), 1)
        
        job = worker.queue.popleft()
        self.assertEqual(job['name'], "file1")

    def test_transcoder_skip_reporting(self):
        worker = AsyncTranscoder({}, False)
        worker.set_total_jobs(5)
        
        # Mock signal emission
        worker.status_signal = MagicMock()
        
        worker.report_skipped("skipped_file.mp4")
        self.assertEqual(worker.completed_jobs, 1)
        worker.status_signal.emit.assert_called_with("Skipped 1/5: skipped_file.mp4")

    @patch('shutil.disk_usage')
    def test_copy_worker_storage_check_logic(self, mock_disk_usage):
        # Mock 10GB free space
        mock_disk_usage.return_value = MagicMock(free=10 * 1024**3)
        
        worker = CopyWorker("/src", ["/dest"], "Project", True, True, False, "auto", True)
        
        # Test get_free_space recursive parent check
        with patch('os.path.exists') as mock_exists:
            # Simulate /dest exists but subfolders don't
            mock_exists.side_effect = lambda p: p == "/dest"
            free = worker.get_free_space("/dest/new_folder/file")
            self.assertEqual(free, 10 * 1024**3)

if __name__ == '__main__':
    unittest.main()
