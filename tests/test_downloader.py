import sys
import os
import tempfile
import unittest
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from scripts.downloader import download_video

class TestDownloader(unittest.TestCase):
    def test_download_video(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_file = os.path.join(tmp_dir, "test_raw.mp4")
            sample_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "sample.mp4"))
            url = f"file://{sample_path}"
            res = download_video(url, output_file, retries=2, timeout=10)
            
            self.assertEqual(res["status"], "SUCCESS")
            self.assertTrue(os.path.exists(output_file))
            self.assertGreater(os.path.getsize(output_file), 0)

    def test_download_video_failure(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_file = os.path.join(tmp_dir, "fail.mp4")
            invalid_url = "https://invalid-domain-name-12345.com/video.mp4"
            res = download_video(invalid_url, output_file, retries=1, timeout=2)
            self.assertEqual(res["status"], "FAILED")

if __name__ == "__main__":
    unittest.main()
