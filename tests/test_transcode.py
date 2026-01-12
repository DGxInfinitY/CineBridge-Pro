import unittest
from unittest.mock import patch, MagicMock
import os
from src.modules.utils import TranscodeEngine

class TestTranscodeEngine(unittest.TestCase):
    
    @patch('src.modules.utils.DependencyManager.get_ffmpeg_path')
    @patch('src.modules.utils.DependencyManager.detect_hw_accel')
    def test_dnxhr_command(self, mock_hw, mock_ffmpeg):
        mock_ffmpeg.return_value = "/usr/bin/ffmpeg"
        mock_hw.return_value = None # Force software mode
        
        settings = {
            'v_codec': 'dnxhd',
            'v_profile': 'dnxhr_hq',
            'a_codec': 'pcm_s16le'
        }
        
        cmd = TranscodeEngine.build_command("input.mp4", "output.mov", settings, use_gpu=False)
        
        self.assertEqual(cmd[0], "/usr/bin/ffmpeg")
        self.assertIn("-c:v", cmd)
        self.assertIn("dnxhd", cmd)
        self.assertIn("-profile:v", cmd)
        self.assertIn("dnxhr_hq", cmd)
        self.assertIn("-c:a", cmd)
        self.assertIn("pcm_s16le", cmd)

    @patch('src.modules.utils.DependencyManager.get_ffmpeg_path')
    @patch('src.modules.utils.DependencyManager.detect_hw_accel')
    def test_prores_proxy_command(self, mock_hw, mock_ffmpeg):
        mock_ffmpeg.return_value = "/usr/bin/ffmpeg"
        mock_hw.return_value = None
        
        settings = {
            'v_codec': 'prores_ks',
            'v_profile': '0', # Proxy
            'a_codec': 'pcm_s16le'
        }
        
        cmd = TranscodeEngine.build_command("input.mp4", "output.mov", settings, use_gpu=False)
        
        self.assertIn("prores_ks", cmd)
        self.assertIn("-profile:v", cmd)
        self.assertIn("0", cmd)

    @patch('src.modules.utils.DependencyManager.get_ffmpeg_path')
    @patch('src.modules.utils.DependencyManager.detect_hw_accel')
    def test_gpu_nvenc(self, mock_hw, mock_ffmpeg):
        mock_ffmpeg.return_value = "/usr/bin/ffmpeg"
        mock_hw.return_value = "cuda"
        
        settings = {
            'v_codec': 'libx264',
            'v_profile': 'high',
            'a_codec': 'aac'
        }
        
        # Enable GPU
        cmd = TranscodeEngine.build_command("input.mp4", "output.mp4", settings, use_gpu=True)
        
        self.assertIn("-hwaccel", cmd)
        self.assertIn("cuda", cmd)
        self.assertIn("h264_nvenc", cmd) # Should switch codec
        
    @patch('src.modules.utils.DependencyManager.get_ffmpeg_path')
    def test_burn_in_filters(self, mock_ffmpeg):
        mock_ffmpeg.return_value = "/usr/bin/ffmpeg"
        settings = {
            'v_codec': 'dnxhd',
            'v_profile': 'dnxhr_lb',
            'burn_file': True,
            'burn_tc': True,
            'watermark': "DRAFT"
        }
        
        with patch('src.modules.utils.TranscodeEngine.get_font_path', return_value='/font.ttf'):
            cmd = TranscodeEngine.build_command("input.mp4", "output.mov", settings)
            
            # Check for filter complex
            self.assertTrue(any(x.startswith("-vf") or x == "-vf" for x in cmd))
            
            # Helper to find the filter string
            vf_string = ""
            if "-vf" in cmd:
                vf_string = cmd[cmd.index("-vf") + 1]
            
            self.assertIn("drawtext", vf_string)
            self.assertIn("text='%{filename}'", vf_string)
            self.assertIn("DRAFT", vf_string)

if __name__ == '__main__':
    unittest.main()
