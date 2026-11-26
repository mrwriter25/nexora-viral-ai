from pathlib import Path
import re, subprocess, uuid, json, shutil, os, time
from typing import Optional, List
import feedparser
import requests
from fastapi import FastAPI, HTTPException, UploadFile, File
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

@app.post("/api/upload/{kind}")
async def upload_media(kind: str, file: UploadFile = File(...)):
    if kind not in ("video", "audio"):
        raise HTTPException(400, "Choose video or audio upload.")
    allowed = {"video": {".mp4", ".mov", ".m4v", ".webm"}, "audio": {".mp3", ".wav", ".m4a", ".aac", ".ogg"}}
    original = Path(file.filename or "upload.bin")
    ext = original.suffix.lower()
    if ext not in allowed[kind]:
        raise HTTPException(400, f"Unsupported {kind} format: {ext}")
    target = MEDIA / f"{uuid.uuid4().hex}{ext}"
    limit = 120 * 1024 * 1024
    total = 0
    try:
        with target.open("wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk: break
                total += len(chunk)
                if total > limit:
                    out.close()
                    target.unlink(missing_ok=True)
                    raise HTTPException(413, "File is over 120 MB. Choose a smaller clip.")
                out.write(chunk)
    finally:
        await file.close()
    return {"status": "uploaded", "path": str(target), "filename": original.name, "size_bytes": total}



from PIL import Image, ImageDraw, ImageFont
import random, math

def _font(size, bold=False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"
    ]
    for candidate in candidates:
        try: return ImageFont.truetype(candidate, size)
        except Exception: pass
    return ImageFont.load_default()

def _wrap(draw, text, font, max_width):
    words = str(text).split()
    lines, current = [], ""
    for word in words:
        test = (current + " " + word).strip()
        if draw.textbbox((0,0), test, font=font)[2] <= max_width:
            current = test
        else:
            if current: lines.append(current)
            current = word
    if current: lines.append(current)
    return lines

def _story_for(prompt, niche, lang, duration):
    idea = (prompt or "").strip()
    if not idea:
        ideas = {
            "Horror": ["En skugga syns i spegeln – men ingen står bakom huvudpersonen.",
                       "Ett övergivet hus skickar ett meddelande från framtiden.",
                       "Någon knackar tre gånger. Dörren har ingen utsida."],
            "Comedy": ["En person försöker imponera på sin granne och allt går fel.",
                       "En vanlig måndag blir en absurd tävling mot väckarklockan.",
                       "Huvudpersonen följer ett viralt tips som får motsatt effekt."],
            "Romance": ["Två främlingar missar nästan varandra på en regnig kväll.",
                        "Ett gammalt meddelande dyker upp precis när det behövs."],
            "Action & Adventure": ["En mystisk karta leder till en oväntad upptäckt.",
                                  "En sista sekunds räddning förändrar hela uppdraget."],
            "Sport & Fitness": ["En liten träningsutmaning blir dagens stora comeback.",
                               "Tre enkla steg gör träningen mer fokuserad."],
            "Beauty & Makeup": ["En snabb förvandling inför en oväntad kväll.",
                                "En enkel rutin ger en snygg före-och-efter-känsla."],
            "Fashion": ["Tre outfits, en enda detalj som förändrar hela looken.",
                        "En garderobsutmaning med oväntad vinnare."],
            "Nightlife & Parties": ["Kvällen börjar lugnt men får en komisk vändning.",
                                    "Vännen som alltid säger 'bara en stund' blir kvällens huvudperson."]
        }
        options=ideas.get(niche,["En oväntad händelse förvandlar en helt vanlig dag."])
        idea=random.choice(options)
    is_sv=lang.lower().startswith("sv")
    if is_sv:
        beats=[
            ("VÄNTA LITE…", "Allt började som en helt vanlig dag."),
            ("NÅGOT ÄR FEL", idea),
            ("DET BLIR VÄRRE", "Huvudpersonen försöker förstå vad som händer."),
            ("VÄNDNINGEN", "Precis när allt verkar avgjort dyker en oväntad ledtråd upp."),
            ("SLUTET", "Och det var först då den riktiga historien började.")
        ]
        narration=[f"Har du någonsin varit med om något så här? {idea}",
                  "Först verkade allt helt normalt.",
                  "Men snart började detaljerna inte stämma.",
                  "En oväntad vändning förändrade allting.",
                  "Vad hade du gjort? Skriv i kommentarerna."]
    else:
        beats=[
            ("WAIT FOR IT…","It started like an ordinary day."),
            ("SOMETHING IS OFF",idea),
            ("IT GETS WORSE","The main character tries to understand what is happening."),
            ("THE TWIST","Just when everything seems settled, a new clue appears."),
            ("THE END","And that was when the real story began.")
        ]
        narration=[f"Have you ever experienced something like this? {idea}",
                  "At first, everything seemed normal.",
                  "Then the details stopped making sense.",
                  "An unexpected twist changed everything.",
                  "What would you do? Tell us below."]
    return idea, beats, narration

# Free photographic scene assets from Wikimedia Commons; sources/licenses are saved with each export.
def _commons_photo(query, destination):
    try:
        terms = re.sub(r"[^\\w\\s-]", " ", query, flags=re.UNICODE)[:100].strip() or "cinematic photography"
        response = requests.get("https://commons.wikimedia.org/w/api.php", params={
            "action":"query","format":"json","generator":"search","gsrsearch":"filetype:bitmap "+terms,
            "gsrnamespace":6,"gsrlimit":8,"prop":"imageinfo","iiprop":"url|extmetadata","iiurlwidth":1000},
            headers={"User-Agent":"NexoraViralAI/1.2 (open-source video creator)"},timeout=18)
        response.raise_for_status()
        pages=list(response.json().get("query",{}).get("pages",{}).values()); random.shuffle(pages)
        for page in pages:
            info=(page.get("imageinfo") or [{}])[0]; url=info.get("thumburl") or info.get("url")
            if not url: continue
            image=requests.get(url,headers={"User-Agent":"NexoraViralAI/1.2"},timeout=25); image.raise_for_status()
            if len(image.content)<12000: continue
            destination.write_bytes(image.content); meta=info.get("extmetadata",{})
            return {"title":page.get("title",""),"source":info.get("descriptionurl",url),
                "license":meta.get("LicenseShortName",{}).get("value","License not identified"),
                "artist":meta.get("Artist",{}).get("value","Unknown")}
    except Exception: pass
    return None

def _make_scene(path, headline, body, idx, niche, photo=None):
    W,H=720,1280
    # cinematic vertical gradient
    palettes={"Horror":((8,8,28),(105,12,40)),"Comedy":((20,30,70),(220,70,90)),
              "Romance":((55,20,65),(220,90,130)),"Fashion":((20,20,28),(130,90,70)),
              "Beauty & Makeup":((35,15,40),(180,70,110)),"Sport & Fitness":((5,45,55),(20,130,130)),
              "Action & Adventure":((8,20,45),(150,55,25)),"Nightlife & Parties":((20,5,50),(80,20,120))}
    top,bottom=palettes.get(niche,((10,15,35),(90,20,60)))
    im=None
    if photo and photo.exists():
        try:
            from PIL import ImageOps, ImageEnhance
            im=ImageOps.fit(Image.open(photo).convert("RGB"),(W,H),method=Image.Resampling.LANCZOS)
            im=ImageEnhance.Brightness(ImageEnhance.Color(im).enhance(1.1)).enhance(0.55)
        except Exception: im=None
    if im is None:
        im=Image.new("RGB",(W,H)); pix=im.load()
    for y in range(H):
        t=y/(H-1)
        c=tuple(int(top[k]*(1-t)+bottom[k]*t) for k in range(3))
        for x in range(W): pix[x,y]=c
    d=ImageDraw.Draw(im,"RGBA")
    # soft luminous circles / abstract shapes
    for j in range(9):
        x=(j*137+idx*83)%W; y=(j*211+idx*149)%H; r=40+(j%4)*25
        d.ellipse((x-r,y-r,x+r,y+r),fill=(255,255,255,12),outline=(255,255,255,24),width=3)
    d.rounded_rectangle((44,60,W-44,H-60),radius=36,outline=(255,255,255,55),width=3)
    tag="NEXORA • ORIGINAL STORY"
    d.text((65,100),tag,font=_font(25,True),fill=(255,190,205,255))
    headfont=_font(62,True); bodyfont=_font(36,False)
    y=360
    for line in _wrap(d,headline,headfont,W-120)[:4]:
        d.text((60,y),line,font=headfont,fill="white",stroke_width=2,stroke_fill=(0,0,0,120)); y+=82
    y+=25
    for line in _wrap(d,body,bodyfont,W-120)[:7]:
        d.text((62,y),line,font=bodyfont,fill=(255,225,230,255)); y+=54
    d.text((62,H-145),f"SCENE {idx+1:02d}  /  SHORT FILM",font=_font(22,True),fill=(255,190,205,255))
    im.save(path,quality=92)

@app.post("/api/auto-create")
def auto_create(data: dict):
    prompt=str(data.get("prompt",""))[:700]
    niche=str(data.get("niche","Comedy"))[:80]
    lang=str(data.get("language","sv"))[:10]
    country=str(data.get("country","SE"))[:8]
    region=str(data.get("region",""))[:80]
    try: duration=max(10,min(60,int(data.get("duration",30))))
    except Exception: duration=30
    if not shutil.which("ffmpeg"): raise HTTPException(500,"FFmpeg saknas på servern.")
    project_id=uuid.uuid4().hex[:12]
    scene_dir=OUT/project_id
    scene_dir.mkdir(parents=True,exist_ok=True)
    idea,beats,narration=_story_for(prompt,niche,lang,duration)
    scenes=[]
    scenes_credits=[]
    for i,(head,body) in enumerate(beats):
        img=scene_dir/f"scene_{i:02d}.jpg"
        photo=scene_dir/f"photo_{i:02d}.jpg"
        credits=_commons_photo(" ".join((idea+" "+niche+" "+body).split()[:9]),photo)
        if credits: credits["scene"]=i+1; scenes_credits.append(credits)
        _make_scene(img,head,body,i,niche,photo if credits else None)
        scenes.append(img)
    # Compose each scene as a gentle zoom, then concatenate; no uploaded media required.
    segment=max(2,duration/len(scenes))
    pieces=[]
    for i,img in enumerate(scenes):
        part=scene_dir/f"part_{i:02d}.mp4"
        cmd=["ffmpeg","-y","-loop","1","-i",str(img),"-t",str(segment),
             "-vf",f"zoompan=z='min(zoom+0.0007,1.08)':d={int(segment*25)}:s=720x1280:fps=25,format=yuv420p",
             "-an","-c:v","libx264","-preset","ultrafast","-crf","26",str(part)]
        try: subprocess.run(cmd,check=True,capture_output=True,timeout=120)
        except subprocess.CalledProcessError as e: raise HTTPException(500,"Scene render failed: "+e.stderr.decode(errors="ignore")[-900:])
        pieces.append(part)
    concat=scene_dir/"concat.txt"
    concat.write_text("".join(f"file '{p.as_posix()}'\n" for p in pieces),encoding="utf-8")
    final=OUT/f"{project_id}.mp4"
    cmd=["ffmpeg","-y","-f","concat","-safe","0","-i",str(concat),"-t",str(duration),
         "-c:v","libx264","-preset","ultrafast","-crf","25","-pix_fmt","yuv420p","-movflags","+faststart",str(final)]
    try: subprocess.run(cmd,check=True,capture_output=True,timeout=240)
    except subprocess.CalledProcessError as e: raise HTTPException(500,"Video assembly failed: "+e.stderr.decode(errors="ignore")[-1200:])
    (scene_dir/"media_credits.json").write_text(json.dumps(scenes_credits,ensure_ascii=False,indent=2),encoding="utf-8")
    return {"status":"created","title":idea[:90],"idea":idea,"script":"\n".join(narration),
            "file":f"/outputs/{final.name}","format":"720x1280 MP4","duration":duration,
            "visual_mode":"Automatically generated animated storyboard scenes. Not photorealistic AI video yet.",
            "next":"Download and review your original generated storyboard short."}


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
        srt.write_text("1\n00:00:00,000 --> 00:00:08,000\n"+text[:450]+"\n",encoding="utf-8")
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
