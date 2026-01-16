import unittest
import os
import sys
import shutil
import json
from unittest.mock import patch

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from modules.utils import PresetManager
from modules.config import AppConfig

class TestPresets(unittest.TestCase):
    
    def setUp(self):
        # Use a temporary directory for presets during tests
        self.test_dir = os.path.join(os.path.dirname(__file__), "temp_presets")
        os.makedirs(self.test_dir, exist_ok=True)
        self.original_get_preset_dir = AppConfig.get_preset_dir
        AppConfig.get_preset_dir = lambda: self.test_dir

    def tearDown(self):
        AppConfig.get_preset_dir = self.original_get_preset_dir
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_save_and_list_preset(self):
        settings = {"v_codec": "dnxhd", "audio_fix": True}
        success = PresetManager.save_preset("MyTest", settings)
        self.assertTrue(success)
        
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, "MyTest.json")))
        
        presets = PresetManager.list_presets()
        self.assertIn("MyTest", presets)
        self.assertEqual(presets["MyTest"]["v_codec"], "dnxhd")

    def test_delete_preset(self):
        settings = {"test": 1}
        PresetManager.save_preset("ToDelete", settings)
        
        # Verify it exists
        self.assertIn("ToDelete", PresetManager.list_presets())
        
        # Delete
        res = PresetManager.delete_preset("ToDelete")
        self.assertTrue(res)
        self.assertNotIn("ToDelete", PresetManager.list_presets())
        self.assertFalse(os.path.exists(os.path.join(self.test_dir, "ToDelete.json")))

    def test_save_handles_errors(self):
        # Mock open to raise exception
        with patch("builtins.open", side_effect=IOError("Permission denied")):
            success = PresetManager.save_preset("BadSave", {})
            self.assertFalse(success)

if __name__ == '__main__':
    unittest.main()
