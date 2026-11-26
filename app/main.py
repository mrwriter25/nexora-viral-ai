from pathlib import Path
import re, subprocess, uuid, json, shutil, os, time
from typing import Optional, List
import feedparser
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

BASE = Path(__file__).resolve().parent.parent
MEDIA = BASE / "media"
OUT = BASE / "outputs"
DATA = BASE / "data"
for p in (MEDIA, OUT, DATA): p.mkdir(exist_ok=True)
PROJECTS = DATA / "projects.json"
if not PROJECTS.exists(): PROJECTS.write_text("[]", encoding="utf-8")

app = FastAPI(title="NEXORA VIRAL AI", version="1.0.0")

class Profile(BaseModel):
    niche: str = "Comedy"
    country: str = "SE"
    language: str = "sv"
    region: str = "Stockholm"
    audience: str = "18+"
    tone: str = "realistic, engaging, cinematic"
    duration: int = Field(default=30, ge=10, le=180)

class VideoProject(Profile):
    id: Optional[str] = None
    title: str = "NEXORA Short"
    idea: str = ""
    script: str = ""
    caption: str = ""
    hashtags: str = ""
    source_video: Optional[str] = None
    source_audio: Optional[str] = None
    subtitles: bool = True
    status: str = "draft"
    created_at: Optional[int] = None
    rendered_file: Optional[str] = None

def read_projects():
    try: return json.loads(PROJECTS.read_text(encoding="utf-8"))
    except Exception: return []
def write_projects(items): PROJECTS.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
def safe_media_path(raw):
    p = Path(raw).expanduser().resolve()
    # Allow project media directory or explicit existing local files for single-user local installation.
    if not p.exists() or not p.is_file(): raise HTTPException(404, "Media file not found.")
    return p

@app.get("/api/status")
def status():
    return {"status":"ready","version":"1.0.0","ffmpeg":bool(shutil.which("ffmpeg")),
            "projects":len(read_projects()),"mode":"local-first"}

@app.get("/api/projects")
def list_projects(): return read_projects()

@app.post("/api/projects")
def create_project(project: VideoProject):
    items=read_projects()
    project.id=uuid.uuid4().hex[:12]; project.created_at=int(time.time())
    items.insert(0,project.model_dump()); write_projects(items)
    return project

@app.put("/api/projects/{project_id}")
def update_project(project_id: str, project: VideoProject):
    items=read_projects()
    for i,item in enumerate(items):
        if item.get("id")==project_id:
            data=project.model_dump(); data["id"]=project_id; data["created_at"]=item.get("created_at")
            items[i]=data; write_projects(items); return data
    raise HTTPException(404,"Project not found")

@app.delete("/api/projects/{project_id}")
def delete_project(project_id: str):
    items=read_projects(); new=[x for x in items if x.get("id")!=project_id]
    if len(new)==len(items): raise HTTPException(404,"Project not found")
    write_projects(new); return {"deleted":project_id}

@app.post("/api/discover")
def discover(profile: Profile):
    feeds={
      "SE":["https://www.svt.se/nyheter/rss.xml","https://feeds.bbci.co.uk/news/world/rss.xml"],
      "GB":["https://feeds.bbci.co.uk/news/uk/rss.xml"],
      "US":["https://feeds.bbci.co.uk/news/world/rss.xml"],
      "DE":["https://www.dw.com/en/top-stories/s-9097?maca=en-rss-en-top- stories- 1022-rdf"],
    }
    items=[]
    for url in feeds.get(profile.country.upper(),feeds["US"]):
        try:
            parsed=feedparser.parse(url)
            for entry in parsed.entries[:12]:
                items.append({"title":entry.get("title",""),"url":entry.get("link",""),
                 "summary":re.sub(r"<[^>]*>","",entry.get("summary",""))[:400],
                 "source":parsed.feed.get("title",url)})
        except Exception: pass
    return {"profile":profile.model_dump(),"items":items,
      "guidance":"Use these headlines as inspiration. Verify facts and create original scripts; do not copy articles or third-party clips."}

@app.post("/api/plan")
def plan(profile: Profile):
    # No paid inference API required: deterministic creative brief that can later be connected to Ollama.
    prompts={
      "Beauty & Makeup":"A quick transformation, product routine, or practical beauty tip",
      "Fashion":"A 3-look styling challenge or outfit idea for the local season",
      "Sport & Fitness":"A safe technique tip, training mini-challenge, or motivational story",
      "Nightlife & Parties":"A relatable night-out moment with a humorous or cinematic twist",
      "Comedy":"An original short sketch with a clear setup, escalation, and punchline",
      "Action & Adventure":"A fictional high-energy mini-story with a strong visual hook",
      "Horror":"An original suspense story with a reveal and atmospheric ending",
      "Romance":"A fictional emotional moment with a memorable final beat"
    }
    concept=prompts.get(profile.niche,"An original short story with a strong opening hook")
    lang=profile.language.lower()
    labels={"sv":"Svensk","en":"English","es":"Español","fr":"Français","de":"Deutsch"}
    language=labels.get(lang,profile.language)
    return {"language":language,"region":profile.region,"country":profile.country,
      "niche":profile.niche,"duration":profile.duration,
      "creative_brief":f"Create an original {profile.tone} vertical short for {profile.audience} in {profile.region}, {profile.country}. Language: {language}. Concept: {concept}.",
      "structure":[
        {"time":"0-3s","purpose":"Hook: surprising visual or question"},
        {"time":"3-10s","purpose":"Establish the situation"},
        {"time":"10-24s","purpose":"Build, reveal, or transformation"},
        {"time":"final 3-6s","purpose":"Payoff and natural follow prompt"}
      ],
      "production_notes":"Use original footage, licensed assets, or AI-generated visuals. Add captions and check regional context."}

@app.post("/api/render")
def render(project: VideoProject):
    if not shutil.which("ffmpeg"): raise HTTPException(500,"FFmpeg missing. Install FFmpeg and restart.")
    if not project.source_video: raise HTTPException(400,"Set source_video to a local file you own or are licensed to use.")
    src=safe_media_path(project.source_video)
    output=OUT/f"{uuid.uuid4().hex}.mp4"
    vf="scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"
    if project.subtitles and project.script.strip():
        # Render text as SRT then burn captions. Escaped path for FFmpeg filter.
        srt=OUT/(output.stem+".srt")
        text=project.script.strip().replace("--","—")
        srt.write_text("1\\n00:00:00,000 --> 00:00:08,000\\n"+text[:450]+"\\n",encoding="utf-8")
        sp=str(srt).replace("\\\\","/").replace(":","\\\\:")
        vf += f",subtitles='{sp}'"
    cmd=["ffmpeg","-y","-i",str(src)]
    if project.source_audio:
        audio=safe_media_path(project.source_audio)
        cmd += ["-i",str(audio),"-map","0:v:0","-map","1:a:0","-shortest"]
    cmd += ["-t",str(project.duration),"-vf",vf,"-c:v","libx264","-preset","veryfast","-crf","23","-c:a","aac","-pix_fmt","yuv420p","-movflags","+faststart",str(output)]
    try: subprocess.run(cmd,check=True,capture_output=True,timeout=900)
    except subprocess.CalledProcessError as e: raise HTTPException(500,e.stderr.decode(errors="ignore")[-1800:])
    project.status="rendered"; project.rendered_file=f"/outputs/{output.name}"
    if project.id:
        items=read_projects()
        for i,x in enumerate(items):
            if x.get("id")==project.id: items[i]=project.model_dump(); write_projects(items); break
    return {"status":"rendered","file":project.rendered_file,"title":project.title,
            "format":"1080x1920 MP4","next_step":"Review the export, then upload through the official platform tools."}

@app.get("/api/publishing/requirements")
def publishing_requirements():
    return {
      "youtube":{"method":"YouTube Data API videos.insert","needs":"Google OAuth client, consent, token storage, API quota and channel authorization","enabled":False},
      "tiktok":{"method":"TikTok Content Posting API","needs":"Registered developer app, approved scopes, OAuth and platform compliance; user confirmation may be required","enabled":False},
      "reason":"Publishing is not activated until the owner supplies their own approved OAuth credentials. Never expose secrets in frontend code."
    }

app.mount("/outputs",StaticFiles(directory=str(OUT)),name="outputs")
app.mount("/",StaticFiles(directory=str(BASE/"web"),html=True),name="web")
