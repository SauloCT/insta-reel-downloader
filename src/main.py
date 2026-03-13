import os
import uuid
import logging
import asyncio
import yt_dlp
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks, Request, UploadFile, File
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
COOKIES_FILE = "/app/cookies/instagram.txt"
os.makedirs(os.path.dirname(COOKIES_FILE), exist_ok=True)

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

async def extract_metadata(url: str):
    """Extracts metadata for a given URL using yt-dlp."""
    ydl_opts = {"quiet": True, "no_warnings": True, "skip_download": True}
    if os.path.exists(COOKIES_FILE):
        ydl_opts["cookiefile"] = COOKIES_FILE

    def get_info():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=False)

    loop = asyncio.get_event_loop()
    try:
        info = await asyncio.wait_for(loop.run_in_executor(None, get_info), timeout=30.0)
        return {
            "id": info.get("id"),
            "title": info.get("title"),
            "description": info.get("description"),
            "uploader": info.get("uploader"),
            "uploader_url": info.get("uploader_url"),
            "upload_date": info.get("upload_date"),
            "duration": info.get("duration"),
            "view_count": info.get("view_count"),
            "like_count": info.get("like_count"),
            "comment_count": info.get("comment_count"),
            "thumbnail": info.get("thumbnail"),
            "webpage_url": info.get("webpage_url"),
            "tags": info.get("tags"),
        }
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Metadata extraction timed out (30s limit)")
    except Exception as e:
        logger.error(f"yt-dlp metadata extraction error: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to extract metadata: {str(e)}")

async def run_yt_dlp(url: str, output_path: str):
    """Runs yt-dlp in a separate thread to avoid blocking."""
    ydl_opts = {
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "outtmpl": output_path,
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
    }
    if os.path.exists(COOKIES_FILE):
        ydl_opts["cookiefile"] = COOKIES_FILE

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

@app.get("/info")
async def info_get(url: str = Query(...)):
    return await extract_metadata(url)

@app.get("/reel")
async def reel_get(request: Request, url: str = Query(...)):
    metadata = await extract_metadata(url)
    metadata['download_url'] = f'{str(request.base_url)}download?url={url}'
    return metadata

@app.post("/cookies")
async def upload_cookies(file: UploadFile = File(...)):
    content = await file.read()
    if b"instagram.com" not in content:
        raise HTTPException(status_code=400, detail="Invalid cookies: must contain 'instagram.com'")
    
    with open(COOKIES_FILE, "wb") as f:
        f.write(content)
    
    return {"status": "ok", "message": "Cookies updated successfully"}

@app.delete("/cookies")
async def delete_cookies():
    if os.path.exists(COOKIES_FILE):
        os.remove(COOKIES_FILE)
        return {"status": "ok", "message": "Cookies removed"}
    raise HTTPException(status_code=404, detail="Cookies file not found")

@app.get("/cookies/status")
async def get_cookies_status():
    path = Path(COOKIES_FILE)
    if path.exists():
        stats = path.stat()
        return {
            "exists": True,
            "size_bytes": stats.st_size,
            "modified_at": datetime.fromtimestamp(stats.st_mtime).isoformat()
        }
    return {
        "exists": False,
        "size_bytes": 0,
        "modified_at": None
    }
