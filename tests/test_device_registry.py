import unittest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from modules.utils import DeviceRegistry

class TestDeviceRegistry(unittest.TestCase):
    def test_constants(self):
        # Ensure core extensions are present
        self.assertIn('.MP4', DeviceRegistry.VIDEO_EXTS)
        self.assertIn('.MOV', DeviceRegistry.VIDEO_EXTS)
        self.assertIn('.BRAW', DeviceRegistry.VIDEO_EXTS)
        self.assertIn('.CRM', DeviceRegistry.VIDEO_EXTS)
        self.assertIn('.ARW', DeviceRegistry.PHOTO_EXTS)

    def test_profiles_integrity(self):
        # Ensure no profile has dangerous or empty roots
        for name, profile in DeviceRegistry.PROFILES.items():
            self.assertIn('signatures', profile)
            self.assertIn('roots', profile)
            self.assertIn('exts', profile)
            self.assertNotIn(".", profile['roots'], f"Profile {name} has unsafe root '.'")
            self.assertFalse(any(r == "" for r in profile['roots']), f"Profile {name} has empty root")
            
            # Verify extensions are known
            all_valid = DeviceRegistry.get_all_valid_exts()
            for ext in profile['exts']:
                self.assertIn(ext, all_valid, f"Profile {name} has unknown extension {ext}")

    def test_dji_neo_support(self):
        # Specific check for our recent fix
        profile = DeviceRegistry.PROFILES.get("DJI Device")
        self.assertIsNotNone(profile)
        self.assertIn("DCIM/DJI_001", profile['roots'])
        self.assertIn("DJI_001", profile['signatures'])

    def test_all_exts_aggregation(self):
        all_exts = DeviceRegistry.get_all_valid_exts()
        self.assertTrue(DeviceRegistry.VIDEO_EXTS.issubset(all_exts))
        self.assertTrue(DeviceRegistry.PHOTO_EXTS.issubset(all_exts))

if __name__ == '__main__':
    unittest.main()
