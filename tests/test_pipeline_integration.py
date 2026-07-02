import sys
import os
import tempfile
import unittest
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from scripts.content_finder import search_pexels, rank_and_select_video
from scripts.downloader import download_video
from scripts.validator import validate_video
from scripts.editor import edit_video
from scripts.metadata_generator import generate_metadata
from scripts.uploader import upload_to_youtube
from scripts.logger import log_execution
from scripts.archive import archive_processed_media

class TestPipelineIntegration(unittest.TestCase):
    def test_full_pipeline_end_to_end(self):
        topic = "ocean"
        
        with tempfile.TemporaryDirectory() as tmp_dir:
            # 1. Content Finder
            videos = search_pexels(topic)
            candidate = rank_and_select_video(videos)
            self.assertIsNotNone(candidate)
            
            # 2. Downloader
            raw_path = os.path.join(tmp_dir, "raw_test.mp4")
            download_res = download_video(candidate["video_url"], raw_path, retries=2, timeout=10)
            self.assertEqual(download_res["status"], "SUCCESS")
            
            # 3. Validator
            val_res = validate_video(raw_path)
            self.assertEqual(val_res["status"], "PASS")
            
            # 4. Editor
            edited_path = os.path.join(tmp_dir, "edited_test.mp4")
            edit_res = edit_video(raw_path, edited_path, duration=15)
            self.assertEqual(edit_res["status"], "SUCCESS")
            
            # 5. Metadata Generator
            meta = generate_metadata(topic)
            self.assertEqual(meta["status"], "SUCCESS")
            
            # 6. Uploader
            upload_res = upload_to_youtube(edited_path, title=meta["title"], description=meta["description"])
            self.assertEqual(upload_res["status"], "SUCCESS")
            
            # 7. Logger
            log_res = log_execution(topic, upload_res["status"], os.path.basename(edited_path), upload_res["video_id"], upload_res["youtube_url"])
            self.assertEqual(log_res["status"], "SUCCESS")
            
            # 8. Archive
            arch_res = archive_processed_media(raw_path, edited_path)
            self.assertEqual(arch_res["status"], "SUCCESS")

if __name__ == "__main__":
    unittest.main()
