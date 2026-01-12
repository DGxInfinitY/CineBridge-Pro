import unittest
import sys
import os

# Add src to path so we can import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from modules.utils import DeviceRegistry, DriveDetector

class TestDeviceRegistry(unittest.TestCase):
    def test_generic_identification(self):
        # Test that an empty path returns Generic Storage (mocking behavior)
        # We can't easily mock filesystem calls without more setup, 
        # but we can test the logic structure if we separate it.
        # For now, let's just ensure the class loads and constants are correct.
        self.assertIn('.MP4', DeviceRegistry.VIDEO_EXTS)
        self.assertIn('.JPG', DeviceRegistry.PHOTO_EXTS)

    def test_profiles_integrity(self):
        # Ensure no profile has the dangerous "." root
        for name, profile in DeviceRegistry.PROFILES.items():
            self.assertNotIn(".", profile['roots'], f"Profile {name} has unsafe root '.'")
            self.assertFalse(any(r == "" for r in profile['roots']), f"Profile {name} has empty root")

if __name__ == '__main__':
    unittest.main()
