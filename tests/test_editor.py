import sys
import os
import tempfile
import unittest
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from scripts.editor import edit_video

class TestEditor(unittest.TestCase):
    def test_edit_video(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            input_file = os.path.join(tmp_dir, "raw.mp4")
            with open(input_file, "wb") as f:
                f.write(b"0" * (200 * 1024))
            output_file = os.path.join(tmp_dir, "short.mp4")
            
            res = edit_video(input_file, output_file, duration=15)
            self.assertEqual(res["status"], "SUCCESS")
            self.assertTrue(os.path.exists(output_file))

if __name__ == "__main__":
    unittest.main()
