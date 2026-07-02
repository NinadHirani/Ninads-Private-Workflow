import sys
import os
import tempfile
import unittest
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from scripts.uploader import upload_to_youtube

class TestUploader(unittest.TestCase):
    def test_upload_to_youtube_mock(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            video_file = os.path.join(tmp_dir, "short.mp4")
            with open(video_file, "wb") as f:
                f.write(b"0" * (100 * 1024))
            
            res = upload_to_youtube(video_file, title="Test Short", privacy_status="unlisted")
            self.assertEqual(res["status"], "SUCCESS")
            self.assertIn("video_id", res)
            self.assertIn("youtube_url", res)

if __name__ == "__main__":
    unittest.main()
