import os, re, json, time, datetime, requests

BIBLE = open("story_bible.txt", encoding="utf8").read()
THEMES = ["나눔", "양치·손씻기", "정직하게 말하기", "기다림", "친구에게 사과하기", "정리정돈",
          "싫어하는 음식 도전", "무서움 이겨내기(안전한 수준)", "내 기분 말하기", "도움 요청하기",
          "안전(횡단보도·손잡기)", "계절과 자연", "색깔·숫자·모양 배우기", "가족 사랑", "친구 배려하기"]
BASE = "https://generativelanguage.googleapis.com/v1beta"
HDR = {"x-goog-api-key": os.environ.get("GEMINI_API_KEY", "")}
_models = None

def models():
    global _models
    if _models:
        return _models
    if os.environ.get("GEMINI_MODEL"):
        _models = [os.environ["GEMINI_MODEL"]]
        return _models
    names = []
    try:
        r = requests.get(BASE + "/models?pageSize=200", headers=HDR, timeout=60)
        if r.status_code != 200:
            print("ListModels failed:", r.status_code, r.text[:300], flush=True)
        for m in r.json().get("models", []):
            n = m["name"].split("/")[-1]
            if ("generateContent" in m.get("supportedGenerationMethods", [])
                    and n.startswith("gemini") and "flash" in n
                    and not re.search(r"lite|image|tts|live|audio|robotics|computer|embedding|exp|thinking|customtools|omni", n)):
                names.append(n)
    except Exception as e:
        print("ListModels error:", e, flush=True)
    pref = [m for m in ("gemini-2.5-flash", "gemini-flash-latest") if m in names]
    rest = sorted([n for n in names if n not in pref],
                  key=lambda n: ("preview" in n, [-int(x) for x in re.findall(r"\d+", n)]))
    _models = pref + rest
    if not _models:
        _models = ["gemini-2.5-flash", "gemini-flash-latest"]
    print("model order:", _models, flush=True)
    return _models

def call(prompt):
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json"}}
    for m in list(models()):
        url = f"{BASE}/models/{m}:generateContent"
        for i in range(2):
            try:
                r = requests.post(url, headers=HDR, json=body, timeout=180)
            except Exception as e:
                print("request error", m, e, flush=True)
                time.sleep(5)
                continue
            if r.status_code == 200:
                try:
                    parts = r.json()["candidates"][0]["content"]["parts"]
                    txt = "".join(p.get("text", "") for p in parts if not p.get("thought"))
                    txt = re.sub(r"^```(?:json)?\s*|\s*```$", "", txt.strip())
                    data = json.loads(txt)
                    if m in _models:
                        _models.remove(m)
                        _models.insert(0, m)
                    print("ok:", m, flush=True)
                    return data
                except Exception as e:
                    print("parse error", m, e, flush=True)
                    break
            print("gemini", m, r.status_code, r.text[:200].replace("\n", " "), flush=True)
            if r.status_code in (500, 503):
                time.sleep(8)
                continue
            break
    raise RuntimeError("all gemini models failed")

def gen_story(n, char):
    hist = json.load(open("history.json", encoding="utf8")) if os.path.exists("history.json") else []
    theme = THEMES[datetime.date.today().toordinal() % len(THEMES)]
    plot = call(f"""{BIBLE}
오늘의 교훈 주제: {theme}
최근 에피소드(절대 겹치지 말 것): {hist[-40:]}
위 세계관으로 새 에피소드 줄거리를 만들어. 신선하고 아이가 웃을 포인트 1개 포함.
JSON: {{"topic":"","hook":"첫 3초 장면","problem":"","attempts":["",""],"solution":"","lesson":"","refrain":""}}""")
    schema = '{"topic":"","title":"","description":"","tags":[""],"scenes":[{"narration":"","image_prompt":""}]}'
    draft = call(f"""{BIBLE}
줄거리: {json.dumps(plot, ensure_ascii=False)}
이 줄거리를 장면 {n}개 대본으로 써. 나레이션은 장면당 한국어 1~2문장, 후렴을 2~3번 넣고 마지막 장면에 교훈.
image_prompt는 영어로 배경·동작·표정만 묘사. 조연이 나오면 세계관 문서의 영어 외형 묘사를 그대로 포함하고, 주인공 보미의 외모는 쓰지 마(자동으로 붙음).
title은 아이 부모가 검색할 만한 한국어 제목, description은 2~3문장.
JSON: {schema}""")
    return call(f"""아래 대본을 검수·개선해. 폭력·공포·위험행동 요소 제거, 어려운 단어는 쉬운 말로, 후렴과 교훈 유지,
설교조 문장은 행동 묘사로 바꾸기, 장면 수 {n}개 유지. 같은 JSON 형식으로만 출력.
{json.dumps(draft, ensure_ascii=False)}""")