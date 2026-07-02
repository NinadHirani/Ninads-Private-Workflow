import sys
import os
import tempfile
import unittest
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from scripts.validator import validate_video

class TestValidator(unittest.TestCase):
    def test_validate_video_non_existent(self):
        res = validate_video("non_existent_file.mp4")
        self.assertEqual(res["status"], "FAIL")

    def test_validate_video_valid(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            dummy_path = os.path.join(tmp_dir, "valid.mp4")
            with open(dummy_path, "wb") as f:
                f.write(b"0" * (200 * 1024))
            res = validate_video(dummy_path)
            self.assertEqual(res["status"], "PASS")

if __name__ == "__main__":
    unittest.main()
