import unittest
import os
import sys
import xml.etree.ElementTree as ET

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from modules.utils import MHLGenerator, ReportGenerator

class TestDeliverables(unittest.TestCase):
    
    def test_mhl_structure(self):
        transfer_data = [
            {'name': 'test.mp4', 'size': 1024, 'hash': 'abc123hash', 'status': 'OK'}
        ]
        dest_root = "/tmp"
        if not os.path.exists(dest_root): dest_root = "." # Fallback
        
        mhl_path = MHLGenerator.generate(dest_root, transfer_data, "TestProj")
        
        try:
            self.assertTrue(os.path.exists(mhl_path))
            # Verify XML
            tree = ET.parse(mhl_path)
            root = tree.getroot()
            self.assertEqual(root.tag, "hashlist")
            
            # Find file node
            file_node = root.find(".//file")
            self.assertEqual(file_node.text, "test.mp4")
        finally:
            if os.path.exists(mhl_path): os.remove(mhl_path)

    def test_report_generation(self):
        transfer_data = [
            {'name': 'test_video.mp4', 'size': 1024 * 1024 * 50, 'hash': 'abc', 'status': 'OK'}
        ]
        html = ReportGenerator.generate_html(transfer_data, "TestProject")
        
        self.assertIn("<h1>CineBridge Pro | Transfer Report</h1>", html)
        self.assertIn("TestProject", html)
        self.assertIn("test_video.mp4", html)
        self.assertIn("50.00", html) # Size check
        self.assertIn("abc", html)

if __name__ == '__main__':
    unittest.main()
