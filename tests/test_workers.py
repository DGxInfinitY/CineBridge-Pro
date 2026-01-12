import unittest
from unittest.mock import patch, MagicMock
import os
import sys

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from modules.workers import AsyncTranscoder

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

if __name__ == '__main__':
    unittest.main()
