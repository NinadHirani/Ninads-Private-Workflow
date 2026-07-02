import sys
import os
import unittest
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from scripts.content_finder import search_pexels, rank_and_select_video

class TestContentFinder(unittest.TestCase):
    def test_search_pexels_fallback(self):
        videos = search_pexels("nature")
        self.assertIsInstance(videos, list)
        self.assertGreater(len(videos), 0)

    def test_rank_and_select_video(self):
        videos = search_pexels("nature")
        candidate = rank_and_select_video(videos)
        self.assertIsNotNone(candidate)
        self.assertIn("video_url", candidate)
        self.assertIn("width", candidate)
        self.assertIn("height", candidate)

if __name__ == "__main__":
    unittest.main()
