#!/usr/bin/env python3
"""
Downloader Module - AI Shorts Factory
Downloads video files from source URL with retry mechanisms and validation.
Saves file to downloads/raw_YYYYMMDD_HHMMSS.mp4
"""

import os
import sys
import time
import json
import datetime
import argparse
import logging
import shutil
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("downloader")

DOWNLOAD_DIR = os.getenv("DOWNLOAD_PATH", "downloads")

def download_video(url: str, output_path: str = None, retries: int = 3, timeout: int = 30) -> dict:
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    
    if not output_path:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(DOWNLOAD_DIR, f"raw_{timestamp}.mp4")
        
    start_time = time.time()
    last_error = None
    
    for attempt in range(1, retries + 1):
        try:
            logger.info(f"Downloading video from {url} (Attempt {attempt}/{retries})...")
            if url.startswith("file://") or os.path.exists(url):
                local_src = url.replace("file://", "")
                shutil.copy2(local_src, output_path)
            else:
                import urllib.request
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    with open(output_path, "wb") as f:
                        while True:
                            chunk = response.read(8192)
                            if not chunk:
                                break
                            f.write(chunk)
                        
            download_time = time.time() - start_time
            file_size = os.path.getsize(output_path)
            
            if file_size == 0:
                raise ValueError("Downloaded file is empty (0 bytes).")
                
            logger.info(f"Successfully downloaded {file_size} bytes in {download_time:.2f}s -> {output_path}")
            return {
                "status": "SUCCESS",
                "file_path": output_path,
                "file_size_bytes": file_size,
                "download_duration_sec": round(download_time, 2),
                "source_url": url,
                "retry_count": attempt - 1
            }
        except Exception as e:
            last_error = str(e)
            logger.warning(f"Download attempt {attempt} error: {e}")
            
        if attempt < retries:
            sleep_time = attempt * 2
            logger.info(f"Retrying download in {sleep_time} seconds...")
            time.sleep(sleep_time)
            
    return {
        "status": "FAILED",
        "error": f"Failed after {retries} attempts. Last error: {last_error}",
        "source_url": url
    }

def main():
    parser = argparse.ArgumentParser(description="Download video file for AI Shorts Factory")
    parser.add_argument("--url", type=str, required=True, help="Video source URL")
    parser.add_argument("--output", type=str, default=None, help="Optional custom output path")
    args = parser.parse_args()
    
    result = download_video(args.url, args.output)
    print(json.dumps(result, indent=2))
    if result["status"] != "SUCCESS":
        sys.exit(1)

if __name__ == "__main__":
    main()
