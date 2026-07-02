import sys
import os
import unittest
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from scripts.logger import log_execution, DB_PATH, CSV_PATH

class TestLogger(unittest.TestCase):
    def test_log_execution(self):
        res = log_execution(
            topic="nature",
            status="SUCCESS",
            video_name="short_test.mp4",
            youtube_video_id="mock_123",
            youtube_url="https://youtube.com/shorts/mock_123",
            execution_time_sec=12.5,
            retry_count=0
        )
        self.assertEqual(res["status"], "SUCCESS")
        self.assertTrue(os.path.exists(DB_PATH))
        self.assertTrue(os.path.exists(CSV_PATH))

if __name__ == "__main__":
    unittest.main()
