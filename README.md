# insta-reel-downloader
[![CI](https://github.com/SauloCT/insta-reel-downloader/actions/workflows/build-push.yml/badge.svg)](https://github.com/SauloCT/insta-reel-downloader/actions/workflows/build-push.yml)

## Overview
A lightweight API for downloading Instagram Reels with a built-in Web UI to manage authentication via cookies, helping bypass rate-limiting and access private content.

## Quick Start (docker-compose)
```yaml
services:
  insta-downloader:
    image: ghcr.io/sauloct/insta-reel-downloader:latest
    container_name: insta-downloader
    restart: unless-stopped
    ports:
      - "8000:8000" # Optional: add for direct host access
```

## Web UI
Accessible at `/`, the Web UI provides a simple interface to manage Instagram cookies. It allows you to upload or paste your `sessionid` to maintain authenticated sessions, which is essential for avoiding rate-limits and downloading content from private accounts. Step-by-step instructions are included directly in the interface.

## API Endpoints

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/` | `GET` | Web UI / Dashboard |
| `/health` | `GET` | Health check |
| `/info?url=` | `GET` | Metadata JSON (title, uploader, duration, likes, etc.) |
| `/reel?url=` | `GET` | Metadata + `download_url` field |
| `/download?url=` | `GET` | Returns the MP4 file directly |
| `/download` | `POST` | Returns MP4 file. Body: `{"url": "...", "quality": "best"}` |
| `/cookies/status`| `GET` | Check if Instagram cookies are loaded |
| `/cookies` | `POST` | Upload a cookies file |
| `/cookies` | `DELETE`| Remove active cookies |

### Examples

**Get Info:**
```bash
curl "http://localhost:8000/info?url=https://www.instagram.com/reels/XXXXX/"
```

**Get Metadata with Download Link:**
```bash
curl "http://localhost:8000/reel?url=https://www.instagram.com/reels/XXXXX/"
```

**Download Video:**
```bash
curl "http://localhost:8000/download?url=https://www.instagram.com/reels/XXXXX/" --output video.mp4
```

## Authentication (Cookies)
Instagram strictly rate-limits anonymous requests. To ensure reliable downloads, you can export your `sessionid` via Browser DevTools (Application -> Cookies) and upload it through the Web UI at `/`. Cookies persist as long as the container volume is maintained or while it remains running.

## Multi-arch
Native support for:
- `linux/amd64`
- `linux/arm64` (optimized for Oracle Cloud Ampere and Raspberry Pi)

## Stack
Python 3.12 · FastAPI · yt-dlp · ffmpeg
