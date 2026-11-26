# NEXORA VIRAL AI v1.0 — local-first creator studio

## Start
Prerequisites: Python 3.11+, FFmpeg.
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000
```
Open http://127.0.0.1:8000

## Docker
```bash
docker build -t nexora-viral-ai .
docker run --rm -p 8000:8000 -v "$(pwd)/outputs:/app/outputs" -v "$(pwd)/media:/app/media" nexora-viral-ai
```

## Current working features
- Web dashboard
- Profile settings: niche, country, language, region, audience and style
- Public RSS headline discovery for selected country profiles
- Creative brief and short-form story structure
- Save/load projects
- FFmpeg vertical MP4 rendering from local owned/licensed video
- Optional external audio and subtitle burn-in
- Publishing requirements endpoint

## Publishing and public deployment
Direct TikTok and YouTube publishing is not switched on: platform developer app registration, OAuth authorization, review/permissions and secrets are account-specific. Set up those credentials server-side before enabling publishing. The app intentionally does not scrape or repost copyrighted creator videos.

A publicly hosted multi-user service needs authentication, per-user file isolation, rate limiting, task queue, storage lifecycle, secure OAuth token encryption, moderation and abuse controls. The starter is suitable for local use and private deployment, not an unrestricted public SaaS as-is.

## AI video generation
This package has a working editor/rendering pipeline, but not a bundled video-generation model. Truly free generation can be run locally through a compatible open model and ComfyUI, but requires suitable hardware and model downloads. No model or cloud GPU is promised as free/unlimited.
