import unittest
from unittest.mock import patch, MagicMock, mock_open
import sys
import os

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from modules.workers.system import SystemMonitor

class TestSystemMonitor(unittest.TestCase):

    def setUp(self):
        self.monitor = SystemMonitor()

    @patch('modules.workers.system.PSUTIL_AVAILABLE', True)
    @patch('psutil.cpu_percent')
    @patch('psutil.sensors_temperatures')
    def test_cpu_stats_psutil(self, mock_temps, mock_cpu):
        # Mock CPU Load
        mock_cpu.return_value = 15.5 # Should act like 15 or 16 int
        
        # Mock Temps (Linux style)
        mock_coretemp = MagicMock()
        mock_coretemp.current = 45.0
        mock_temps.return_value = {'coretemp': [mock_coretemp]}
        
        # We need to run the logic that is usually inside the loop.
        # Since run() is an infinite loop, we'll extract the logic or mock the loop.
        # But SystemMonitor.run() is a while loop. We can't easily call it.
        # However, looking at the code, it's a monolithic run() method. 
        # Refactoring would be best, but for now we can rely on integration or 
        # mock the `time.sleep` to raise an exception to break the loop after one iteration?
        # A cleaner way is to start the thread, let it run once, then stop it.
        pass

    # Better approach: Refactor SystemMonitor to have a `collect_stats()` method 
    # that returns the dict, making it testable. 
    # BUT I am not supposed to change code unless necessary.
    # I can mock `time.sleep` to throw a custom exception to break the loop.

    @patch('modules.workers.system.PSUTIL_AVAILABLE', True)
    @patch('psutil.cpu_percent')
    @patch('psutil.sensors_temperatures')
    @patch('time.sleep')
    def test_cpu_stats_collection(self, mock_sleep, mock_temps, mock_cpu):
        mock_cpu.return_value = 25.0
        
        mock_temp_entry = MagicMock()
        mock_temp_entry.current = 55.0
        mock_temps.return_value = {'coretemp': [mock_temp_entry]}
        
        # Break loop after first pass
        mock_sleep.side_effect = InterruptedError("Break Loop")
        
        # Capture signal
        stats_result = {}
        def capture_stats(s):
            stats_result.update(s)
        
        self.monitor.stats_signal.connect(capture_stats)
        
        try:
            self.monitor.run()
        except InterruptedError:
            pass
        
        self.assertEqual(stats_result.get('cpu_load'), 25)
        self.assertEqual(stats_result.get('cpu_temp'), 55)

    @patch('subprocess.run')
    @patch('time.sleep')
    def test_nvidia_gpu_stats(self, mock_sleep, mock_subprocess):
        mock_sleep.side_effect = InterruptedError("Break Loop")
        
        # Mock psutil missing or failing
        with patch('modules.workers.system.PSUTIL_AVAILABLE', False):
            # Mock nvidia-smi output: "40, 60" (Load, Temp)
            mock_res = MagicMock()
            mock_res.returncode = 0
            mock_res.stdout = "40, 60"
            mock_subprocess.return_value = mock_res
            
            stats_result = {}
            self.monitor.stats_signal.connect(lambda s: stats_result.update(s))
            
            try:
                self.monitor.run()
            except InterruptedError:
                pass
            
            self.assertTrue(stats_result.get('has_gpu'))
            self.assertEqual(stats_result.get('gpu_vendor'), 'NVIDIA')
            self.assertEqual(stats_result.get('gpu_load'), 40)
            self.assertEqual(stats_result.get('gpu_temp'), 60)

if __name__ == '__main__':
    unittest.main()
