import sys
import os
import unittest
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from scripts.metadata_generator import generate_metadata

class TestMetadata(unittest.TestCase):
    def test_generate_metadata(self):
        res = generate_metadata("waterfall")
        self.assertEqual(res["status"], "SUCCESS")
        self.assertIn("title", res)
        self.assertLessEqual(len(res["title"]), 100)
        self.assertIn("description", res)
        self.assertIn("hashtags", res)

if __name__ == "__main__":
    unittest.main()
