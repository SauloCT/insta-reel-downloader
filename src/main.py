import os
import uuid
import logging
import asyncio
import yt_dlp
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("insta-downloader")

app = FastAPI(title="Instagram Reel Downloader")

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DOWNLOAD_DIR = "/tmp/insta-downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

class DownloadRequest(BaseModel):
    url: str
    quality: Optional[str] = "best"

def cleanup_file(file_path: str):
    """Deletes the file after response is sent."""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Cleaned up temporary file: {file_path}")
    except Exception as e:
        logger.error(f"Error cleaning up file {file_path}: {e}")

async def run_yt_dlp(url: str, output_path: str):
    """Runs yt-dlp in a separate thread to avoid blocking."""
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': output_path,
        'merge_output_format': 'mp4',
        'quiet': True,
        'no_warnings': True,
    }
    
    def download():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return ydl.prepare_filename(info)

    loop = asyncio.get_event_loop()
    try:
        # Using wait_for for the 60s timeout
        return await asyncio.wait_for(loop.run_in_executor(None, download), timeout=60.0)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Download timed out (60s limit)")
    except Exception as e:
        logger.error(f"yt-dlp error: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to download video: {str(e)}")

@app.get("/health")
def health_check():
    return {"status": "ok"}

async def handle_download(url: str, background_tasks: BackgroundTasks):
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")
    
    # Generate a unique filename to avoid collisions
    file_id = str(uuid.uuid4())
    output_template = os.path.join(DOWNLOAD_DIR, f"{file_id}.%(ext)s")
    
    logger.info(f"Starting download for URL: {url}")
    
    # yt-dlp might change the extension during merge, but we requested mp4
    # The actual path will be returned by our helper
    try:
        actual_path = await run_yt_dlp(url, output_template)
        
        if not os.path.exists(actual_path):
            raise HTTPException(status_code=404, detail="Downloaded file not found")

        background_tasks.add_task(cleanup_file, actual_path)
        
        return FileResponse(
            path=actual_path,
            filename="instagram_reel.mp4",
            media_type="video/mp4"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/download")
async def download_get(background_tasks: BackgroundTasks, url: str = Query(...)):
    return await handle_download(url, background_tasks)

@app.post("/download")
async def download_post(request: DownloadRequest, background_tasks: BackgroundTasks):
    return await handle_download(request.url, background_tasks)
