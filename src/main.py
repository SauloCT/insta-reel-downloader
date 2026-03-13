import os
import uuid
import logging
import asyncio
import yt_dlp
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks, Request, UploadFile, File
from fastapi.responses import FileResponse, HTMLResponse
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

@app.get("/", response_class=HTMLResponse)
async def root():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Instagram Reel Downloader</title>
        <style>
            :root {
                --bg-color: #1a1a2e;
                --card-bg: #16213e;
                --text-color: #e94560;
                --text-secondary: #0f3460;
                --light-text: #ffffff;
                --success: #28a745;
                --danger: #dc3545;
                --accent: #4ecca3;
            }
            body {
                font-family: system-ui, -apple-system, sans-serif;
                background-color: var(--bg-color);
                color: var(--light-text);
                margin: 0;
                padding: 20px;
                display: flex;
                flex-direction: column;
                align-items: center;
            }
            .container {
                max-width: 800px;
                width: 100%;
            }
            h1 { color: var(--accent); text-align: center; }
            section {
                background: var(--card-bg);
                padding: 20px;
                border-radius: 12px;
                margin-bottom: 20px;
                box-shadow: 0 4px 15px rgba(0,0,0,0.3);
            }
            h2 { margin-top: 0; font-size: 1.2rem; border-bottom: 1px solid #2d4059; padding-bottom: 10px; }
            .badge {
                padding: 5px 12px;
                border-radius: 20px;
                font-size: 0.85rem;
                font-weight: bold;
            }
            .badge-success { background-color: var(--success); }
            .badge-danger { background-color: var(--danger); }
            .status-info { margin-top: 10px; font-size: 0.9rem; color: #999; }
            ol { padding-left: 20px; }
            li { margin-bottom: 8px; }
            input[type="text"] {
                width: 100%;
                padding: 10px;
                border-radius: 6px;
                border: 1px solid #2d4059;
                background: #0f3460;
                color: white;
                box-sizing: border-box;
                margin: 10px 0;
            }
            .actions { display: flex; gap: 10px; }
            button {
                padding: 10px 20px;
                border: none;
                border-radius: 6px;
                cursor: pointer;
                font-weight: bold;
                transition: opacity 0.2s;
            }
            button:hover { opacity: 0.9; }
            .btn-save { background-color: var(--accent); color: var(--bg-color); }
            .btn-remove { background-color: var(--danger); color: white; }
            #feedback {
                margin-top: 15px;
                padding: 10px;
                border-radius: 6px;
                display: none;
            }
            table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 0.9rem; }
            th, td { text-align: left; padding: 10px; border-bottom: 1px solid #2d4059; }
            th { color: var(--accent); }
            code { background: #0f3460; padding: 2px 4px; border-radius: 4px; color: #e94560; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Instagram Reel Downloader</h1>
            
            <section>
                <h2>Cookie Status</h2>
                <div id="status-container">
                    <span class="badge" id="status-badge">Checking...</span>
                    <div class="status-info" id="status-details"></div>
                </div>
            </section>

            <section>
                <h2>Configurar Cookies</h2>
                <ol>
                    <li>Abra o <a href="https://www.instagram.com" target="_blank" style="color: var(--accent);">Instagram</a> no navegador e faça login.</li>
                    <li>Pressione <b>F12</b> → <b>Application</b> (Chrome) ou <b>Storage</b> (Firefox) → <b>Cookies</b> → <code>https://www.instagram.com</code></li>
                    <li>Localize o cookie <code>sessionid</code> e copie o valor:</li>
                </ol>
                <input type="text" id="sessionid" placeholder="Cole aqui o valor do sessionid (ex: 1234567890%3A...)">
                <p>4. Clique em Salvar:</p>
                <div class="actions">
                    <button class="btn-save" onclick="saveCookies()">Salvar Cookies</button>
                    <button class="btn-remove" onclick="removeCookies()">Remover Cookies</button>
                </div>
                <div id="feedback"></div>
            </section>

            <section>
                <h2>API Reference</h2>
                <table>
                    <thead>
                        <tr><th>Endpoint</th><th>Method</th><th>Description</th></tr>
                    </thead>
                    <tbody>
                        <tr><td><code>/download?url={url}</code></td><td>GET</td><td>Download direct MP4</td></tr>
                        <tr><td><code>/info?url={url}</code></td><td>GET</td><td>Get reel metadata</td></tr>
                        <tr><td><code>/reel?url={url}</code></td><td>GET</td><td>Metadata + Download link</td></tr>
                        <tr><td><code>/cookies/status</code></td><td>GET</td><td>Check if cookies are active</td></tr>
                    </tbody>
                </table>
            </section>
        </div>

        <script>
            async function updateStatus() {
                try {
                    const res = await fetch('/cookies/status');
                    const data = await res.json();
                    const badge = document.getElementById('status-badge');
                    const details = document.getElementById('status-details');
                    
                    if (data.exists) {
                        badge.textContent = 'Cookies ativos';
                        badge.className = 'badge badge-success';
                        const date = new Date(data.modified_at).toLocaleString();
                        details.textContent = `Tamanho: ${data.size_bytes} bytes | Modificado em: ${date}`;
                    } else {
                        badge.textContent = 'Sem cookies';
                        badge.className = 'badge badge-danger';
                        details.textContent = 'Faça login para baixar conteúdo privado.';
                    }
                } catch (e) {
                    console.error('Erro ao buscar status:', e);
                }
            }

            function showFeedback(msg, isError = false) {
                const fb = document.getElementById('feedback');
                fb.textContent = msg;
                fb.style.display = 'block';
                fb.style.backgroundColor = isError ? 'rgba(220, 53, 69, 0.2)' : 'rgba(40, 167, 69, 0.2)';
                fb.style.color = isError ? '#ff4d4d' : '#28a745';
                setTimeout(() => fb.style.display = 'none', 5000);
            }

            async function saveCookies() {
                const sessionid = document.getElementById('sessionid').value.trim();
                if (!sessionid) {
                    showFeedback('Por favor, insira o sessionid', true);
                    return;
                }

                // Generates Netscape format cookies.txt
                const content = '# Netscape HTTP Cookie File\\n.instagram.com\\tTRUE\\t/\\tTRUE\\t2147483647\\tsessionid\\t' + sessionid + '\\n';
                const blob = new Blob([content], { type: 'text/plain' });
                const formData = new FormData();
                formData.append('file', blob, 'cookies.txt');

                try {
                    const res = await fetch('/cookies', {
                        method: 'POST',
                        body: formData
                    });
                    const data = await res.json();
                    if (res.ok) {
                        showFeedback('Cookies salvos com sucesso!');
                        document.getElementById('sessionid').value = '';
                        updateStatus();
                    } else {
                        showFeedback(data.detail || 'Erro ao salvar cookies', true);
                    }
                } catch (e) {
                    showFeedback('Erro de conexão', true);
                }
            }

            async function removeCookies() {
                if (!confirm('Deseja realmente remover os cookies?')) return;
                try {
                    const res = await fetch('/cookies', { method: 'DELETE' });
                    if (res.ok) {
                        showFeedback('Cookies removidos');
                        updateStatus();
                    } else {
                        showFeedback('Erro ao remover cookies', true);
                    }
                } catch (e) {
                    showFeedback('Erro de conexão', true);
                }
            }

            // Initial load
            updateStatus();
        </script>
    </body>
    </html>
    """

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
