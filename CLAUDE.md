# insta-reel-downloader — Project Config

## Stack
- **API:** Python 3.12 + FastAPI + yt-dlp + ffmpeg
- **Container:** ghcr.io/sauloct/insta-reel-downloader
- **Runtime:** Oracle VM (ARM64) via Portainer stack `insta-reel-downloader` (id=17, endpointId=2)
- **Network:** `shared_network` (shared with n8n)

## Deployment Flow

```
src/ edit → git push → CI builds image → redeploy Portainer stack
```

### Steps

1. **Develop & test locally** (Hetzner VM)
   ```bash
   # Syntax check
   python3 -c "import ast; ast.parse(open('src/main.py').read())"
   ```

2. **Commit and push** (triggers CI automatically)
   ```bash
   git add src/main.py && git commit -m "feat: ..." && git push
   ```

3. **CI builds multi-arch image** (amd64 + arm64) and pushes to ghcr.io
   ```bash
   gh run list --repo SauloCT/insta-reel-downloader --limit 1
   gh run watch <id> --repo SauloCT/insta-reel-downloader
   ```

4. **Redeploy Portainer stack** (pulls latest image + restarts container)
   ```bash
   ./scripts/redeploy.sh
   ```

5. **Create release** (after significant changes)
   ```bash
   gh release create vX.Y.Z --repo SauloCT/insta-reel-downloader --title "vX.Y.Z" --notes "..."
   ```

## Credentials

Stored in `.env` (never commit):
- `PORTAINER_URL` — Portainer instance URL
- `PORTAINER_TOKEN` — Portainer access token (Account → Access tokens)
- `PORTAINER_STACK_NAME` — stack name on Portainer

## Key Files

| File | Purpose |
|---|---|
| `src/main.py` | FastAPI app — all endpoints |
| `docker-compose.yml` | Production compose (used by Portainer) |
| `scripts/redeploy.sh` | Portainer API redeploy script |
| `.env` | Local credentials (gitignored) |

## Portainer Stack Compose

```yaml
services:
  insta-downloader:
    image: ghcr.io/sauloct/insta-reel-downloader:latest
    container_name: insta-downloader
    restart: unless-stopped
    networks:
      - shared_network

networks:
  shared_network:
    external: true
```

## Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/` | Web UI (cookie management) |
| GET | `/health` | Health check |
| GET | `/info?url=` | Reel metadata (JSON) |
| GET | `/reel?url=` | Metadata + download_url (JSON) |
| GET | `/download?url=` | Download MP4 |
| POST | `/download` | Download MP4 (body: `{url, quality}`) |
| GET | `/cookies/status` | Check if cookies are loaded |
| POST | `/cookies` | Upload cookies file |
| DELETE | `/cookies` | Remove cookies file |
