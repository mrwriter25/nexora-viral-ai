# NEXORA VIRAL AI — Auto Creator v1.1

This build adds a **Create Video Automatically** workflow. A user enters a prompt (or leaves it blank), chooses a niche/language/duration, and the server creates an original short concept, a simple script, animated illustrated scene cards, and an MP4 without requiring user footage.

## Honest capability note
This is a generated animated storyboard/video prototype. It is **not yet photorealistic text-to-video AI**. Real generative video requires connecting a video-generation model/provider or deploying an open model on GPU infrastructure. The public free Render instance is not suitable for running a large video diffusion model.

## Deploy
Deploy the repository to Render as a Docker Web Service. Docker installs FFmpeg; Python dependencies include Pillow for scene artwork.

## Usage
Open the public URL, enter an idea or leave it blank, choose profile settings, then press **SKAPA VIDEO AUTOMATISKT**. When finished, open/download the MP4 link.

The app also retains its earlier planning, RSS discovery, upload/render, project library and platform publishing-requirements routes. TikTok/YouTube publishing is not activated without official OAuth setup.


## Real AI video (Agnes AI)

NEXORA now includes a server-side text-to-video integration for Agnes AI `agnes-video-2.5-flash` (720P, 4–12 seconds, selectable aspect ratio). The provider's Flash model has been listed as a limited-time $0 promotional tier; free availability, quota, and queue capacity can change. The app does not store provider credentials in Git.

Configure the Render web service environment variable `AGNES_API_KEY` with a freshly rotated Agnes key. Optional `AGNES_API_BASE` defaults to `https://apihub.agnes-ai.com`. After deploy, open the app and use **REAL AI VIDEO — AGNES FREE 720P**. The API key stays server-side.
