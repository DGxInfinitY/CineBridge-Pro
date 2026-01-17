import unittest
from unittest.mock import patch, MagicMock
import os
import sys

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from modules.utils import TranscodeEngine

class TestTranscodeEngine(unittest.TestCase):
    
    @patch('modules.utils.DependencyManager.get_ffmpeg_path')
    @patch('modules.utils.DependencyManager.detect_hw_accel')
    def test_build_command_dnxhr(self, mock_hw, mock_ffmpeg):
        mock_ffmpeg.return_value = "/usr/bin/ffmpeg"
        mock_hw.return_value = None
        
        settings = {
            'v_codec': 'dnxhd',
            'v_profile': 'dnxhr_hq',
            'a_codec': 'pcm_s16le'
        }
        
        cmd = TranscodeEngine.build_command("in.mp4", "out.mov", settings)
        self.assertIn("dnxhd", cmd)
        self.assertIn("dnxhr_hq", cmd)
        self.assertIn("pcm_s16le", cmd)

    @patch('modules.utils.DependencyManager.get_ffmpeg_path')
    @patch('modules.utils.DependencyManager.detect_hw_accel')
    def test_build_command_prores(self, mock_hw, mock_ffmpeg):
        mock_ffmpeg.return_value = "/usr/bin/ffmpeg"
        mock_hw.return_value = None
        
        settings = {
            'v_codec': 'prores_ks',
            'v_profile': '3', # HQ
            'a_codec': 'pcm_s16le'
        }
        
        cmd = TranscodeEngine.build_command("in.mp4", "out.mov", settings)
        self.assertIn("prores_ks", cmd)
        self.assertIn("-profile:v", cmd)
        self.assertIn("3", cmd)

    @patch('modules.utils.DependencyManager.get_ffmpeg_path')
    @patch('modules.utils.DependencyManager.detect_hw_accel')
    def test_gpu_normalization(self, mock_hw, mock_ffmpeg):
        mock_ffmpeg.return_value = "/usr/bin/ffmpeg"
        mock_hw.return_value = "cuda"
        
        settings = {'v_codec': 'libx264', 'v_profile': 'high', 'a_codec': 'aac'}
        cmd = TranscodeEngine.build_command("in.mp4", "out.mp4", settings, use_gpu=True)
        self.assertIn("h264_nvenc", cmd)

    @patch('modules.utils.DependencyManager.get_ffmpeg_path')
    @patch('modules.utils.TranscodeEngine.get_font_path')
    def test_lut_and_burnin(self, mock_font, mock_ffmpeg):
        mock_ffmpeg.return_value = "/usr/bin/ffmpeg"
        mock_font.return_value = "/font.ttf"
        
        settings = {
            'v_codec': 'dnxhd',
            'lut_path': '/path/to/lut.cube',
            'burn_file': True,
            'burn_tc': True,
            'watermark': 'DRAFT'
        }
        
        cmd = TranscodeEngine.build_command("in.mp4", "out.mov", settings)
        cmd_str = " ".join(cmd)
        
        self.assertIn("lut3d='/path/to/lut.cube'", cmd_str)
        self.assertIn("drawtext=text='%{filename}'", cmd_str) # Filename burn-in
        self.assertIn("drawtext=text='%{pts\:hms}'", cmd_str) # Timecode burn-in
        self.assertIn("drawtext=text='DRAFT'", cmd_str)       # Watermark

    def test_is_edit_friendly_logic(self):
        # Test normalization logic without real ffprobe calls
        with patch('modules.utils.MediaInfoExtractor.get_info') as mock_info:
            mock_info.return_value = {
                "video_streams": [{'codec': 'prores'}]
            }
            # Test prores_ks normalization
            res = TranscodeEngine.is_edit_friendly("test.mov", "prores_ks")
            self.assertTrue(res)
            
            mock_info.return_value = {
                "video_streams": [{'codec': 'h264'}]
            }
            res = TranscodeEngine.is_edit_friendly("test.mov", "prores_ks")
            self.assertFalse(res)

if __name__ == '__main__':
    unittest.main()
