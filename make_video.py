import os, json, subprocess, asyncio, urllib.parse, time, pathlib, random
import requests, edge_tts, story

MODE = os.getenv("MODE", "short")
W, H = (720, 1280) if MODE == "short" else (1280, 720)
N = 5 if MODE == "short" else 12
VOICE = "ko-KR-SunHiNeural"
SEED = 777
CHAR = "cute 5-year-old girl named Bomi, big round eyes, short black hair, orange dress, always smiling"
STYLE = "bright cheerful 2D kids cartoon, clean outlines, flat pastel colors, simple background, no text, no watermark"
OUT = pathlib.Path("out"); OUT.mkdir(exist_ok=True)

def run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def gen_image(p, path):
    full = f"{CHAR}, {p}, {STYLE}"
    url = ("https://image.pollinations.ai/prompt/" + urllib.parse.quote(full)
           + f"?width={W}&height={H}&seed={SEED}&model=flux&nologo=true")
    for i in range(6):
        try:
            r = requests.get(url, timeout=180)
            if r.status_code == 200 and r.headers.get("content-type", "").startswith("image"):
                path.write_bytes(r.content); return
        except Exception:
            pass
        time.sleep(10 * (i + 1))
    raise RuntimeError("image generation failed")

async def tts(text, path):
    await edge_tts.Communicate(text, VOICE, rate="-10%").save(str(path))

def dur(path):
    out = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                   "-of", "csv=p=0", str(path)])
    return float(out.decode().strip())

def clip(img, aud, d, out):
    fr = int(d * 25) + 1
    vf = (f"scale={W*2}:{H*2},zoompan=z='min(zoom+0.0008,1.15)':d={fr}"
          f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps=25,format=yuv420p")
    run(["ffmpeg", "-y", "-loop", "1", "-i", str(img), "-i", str(aud), "-vf", vf, "-t", f"{d:.2f}",
         "-c:v", "libx264", "-preset", "veryfast", "-c:a", "aac", "-ar", "44100", "-ac", "2", str(out)])

def ts_fmt(t):
    h, m, s = int(t // 3600), int(t % 3600 // 60), t % 60
    return f"{h:02d}:{m:02d}:{int(s):02d},{int((s % 1) * 1000):03d}"

def wrap(text, n):
    return "\n".join(text[i:i + n] for i in range(0, len(text), n))

def upload(path, meta):
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    c = Credentials(None, refresh_token=os.environ["YT_REFRESH_TOKEN"],
                    client_id=os.environ["YT_CLIENT_ID"], client_secret=os.environ["YT_CLIENT_SECRET"],
                    token_uri="https://oauth2.googleapis.com/token")
    yt = build("youtube", "v3", credentials=c)
    tags_txt = "\n\n#키즈 #동요 #애니메이션" + (" #Shorts" if MODE == "short" else "")
    body = {"snippet": {"title": meta["title"][:95], "description": meta["description"] + tags_txt,
                        "tags": meta["tags"][:15], "categoryId": "27", "defaultLanguage": "ko"},
            "status": {"privacyStatus": "private", "selfDeclaredMadeForKids": True,
                       "containsSyntheticMedia": True}}
    req = yt.videos().insert(part="snippet,status", body=body,
                             media_body=MediaFileUpload(str(path), chunksize=-1, resumable=True))
    print("uploaded:", req.execute().get("id"))

def main():
    if not os.environ.get("GEMINI_API_KEY"):
        print("GEMINI_API_KEY 시크릿이 아직 없어서 건너뜁니다."); return
    meta = story.gen_story(N, CHAR)
    scenes = meta["scenes"]
    clips, srt, t = [], [], 0.0
    for i, sc in enumerate(scenes):
        img, aud, cl = OUT / f"{i}.jpg", OUT / f"{i}.mp3", OUT / f"{i}.mp4"
        gen_image(sc["image_prompt"], img)
        asyncio.run(tts(sc["narration"], aud))
        d = dur(aud) + 0.3
        clip(img, aud, d, cl)
        clips.append(cl)
        srt.append(f"{i+1}\n{ts_fmt(t)} --> {ts_fmt(t+d-0.1)}\n{wrap(sc['narration'], 12 if MODE=='short' else 24)}\n")
        t += d
    open("sub.srt", "w", encoding="utf8").write("\n".join(srt))
    open(OUT / "list.txt", "w").write("".join(f"file '{c.name}'\n" for c in clips))
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(OUT / "list.txt"), "-c", "copy", str(OUT / "raw.mp4")])

    size = 11 if MODE == "short" else 18
    style = f"FontName=NanumGothic,FontSize={size},Outline=2,Bold=1,MarginV=60"
    vf = f"subtitles=sub.srt:force_style='{style}'"
    tracks = sorted(pathlib.Path("music").glob("*.mp3"))
    final = OUT / "final.mp4"
    if tracks:
        run(["ffmpeg", "-y", "-i", str(OUT / "raw.mp4"), "-stream_loop", "-1", "-i", str(random.choice(tracks)),
             "-filter_complex", f"[0:v]{vf}[v];[1:a]volume=0.12[b];[0:a][b]amix=inputs=2:duration=first:normalize=0[a]",
             "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-c:a", "aac", str(final)])
    else:
        run(["ffmpeg", "-y", "-i", str(OUT / "raw.mp4"), "-vf", vf, "-c:v", "libx264", "-preset", "veryfast",
             "-c:a", "copy", str(final)])

    hist = json.load(open("history.json", encoding="utf8")) if os.path.exists("history.json") else []
    hist.append(meta["topic"])
    json.dump(hist, open("history.json", "w", encoding="utf8"), ensure_ascii=False)
    if not os.environ.get("YT_REFRESH_TOKEN"):
        print("YT_REFRESH_TOKEN 시크릿이 없어 업로드는 건너뜁니다. 영상은 Actions의 artifact에서 받을 수 있습니다."); return
    try:
        upload(final, meta)
    except Exception as e:
        print("upload failed (video is in artifacts):", e)

main()