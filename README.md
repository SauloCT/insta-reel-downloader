# insta-reel-downloader
[![CI](https://github.com/SauloCT/insta-reel-downloader/actions/workflows/build-push.yml/badge.svg)](https://github.com/SauloCT/insta-reel-downloader/actions/workflows/build-push.yml)

## Overview
Simple API for downloading Instagram Reels. It returns the MP4 file directly.

## Quick Start

### Standalone (Exposed Port)
```yaml
services:
  insta-downloader:
    image: ghcr.io/sauloct/insta-reel-downloader:latest
    container_name: insta-downloader
    restart: unless-stopped
    ports:
      - '8000:8000'
```

### Shared Network (e.g., n8n)
```yaml
services:
  insta-downloader:
    image: ghcr.io/sauloct/insta-reel-downloader:latest
    container_name: insta-downloader
    restart: unless-stopped
    networks:
      - your_network

networks:
  your_network:
    external: true
```

## API

| Endpoint | Method | Params / Body | Description |
| :--- | :--- | :--- | :--- |
| `/health` | `GET` | - | Health check. Returns `{"status": "ok"}` |
| `/info` | `GET` | `?url=<URL>` | Returns JSON metadata (id, title, description, uploader, etc.) |
| `/reel` | `GET` | `?url=<URL>` | Returns metadata plus a ready-to-use `download_url` |
| `/download` | `GET` | `?url=<URL>` | Returns MP4 file directly |
| `/download` | `POST` | `{"url": "<URL>", "quality": "best"}` | Returns MP4 file directly |

### Usage Examples

**Get Info:**
```bash
curl "http://localhost:8000/info?url=INSTAGRAM_URL"
```

**Get Reel Data:**
```bash
curl "http://localhost:8000/reel?url=INSTAGRAM_URL"
```

**Download via GET:**
```bash
curl "http://localhost:8000/download?url=INSTAGRAM_URL" --output video.mp4
```

**Download via POST:**
```bash
curl -X POST "http://localhost:8000/download" \
     -H "Content-Type: application/json" \
     -d '{"url": "INSTAGRAM_URL", "quality": "best"}' \
     --output video.mp4
```

## Multi-arch
Images are available for `linux/amd64` and `linux/arm64` (Oracle Cloud Ampere, Raspberry Pi, etc).

```bash
docker pull ghcr.io/sauloct/insta-reel-downloader:latest
```

## Stack
- Python 3.12 + FastAPI
- yt-dlp
- ffmpeg
