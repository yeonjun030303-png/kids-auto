import os, re, json, time, datetime, requests

BIBLE = open("story_bible.txt", encoding="utf8").read()
THEMES = ["나눔", "양치·손씻기", "정직하게 말하기", "기다림", "친구에게 사과하기", "정리정돈",
          "싫어하는 음식 도전", "무서움 이겨내기(안전한 수준)", "내 기분 말하기", "도움 요청하기",
          "안전(횡단보도·손잡기)", "계절과 자연", "색깔·숫자·모양 배우기", "가족 사랑", "친구 배려하기"]
BASE = "https://generativelanguage.googleapis.com/v1beta"
HDR = {"x-goog-api-key": os.environ.get("GEMINI_API_KEY", "")}
_model = None

def pick_model():
    global _model
    if _model:
        return _model
    if os.environ.get("GEMINI_MODEL"):
        _model = os.environ["GEMINI_MODEL"]
        return _model
    r = requests.get(BASE + "/models?pageSize=200", headers=HDR, timeout=60)
    if r.status_code != 200:
        print("ListModels failed:", r.status_code, r.text[:500], flush=True)
        r.raise_for_status()
    names = []
    for m in r.json().get("models", []):
        n = m["name"].split("/")[-1]
        if ("generateContent" in m.get("supportedGenerationMethods", [])
                and n.startswith("gemini") and "flash" in n
                and not re.search(r"lite|image|tts|live|audio|robotics|computer|embedding|exp|thinking|customtools", n)):
            names.append(n)
    print("candidates:", names, flush=True)
    if not names:
        _model = "gemini-flash-latest"
    else:
        _model = max(names, key=lambda n: ("preview" not in n, [int(x) for x in re.findall(r"\d+", n)]))
    print("using model:", _model, flush=True)
    return _model

def call(prompt):
    url = f"{BASE}/models/{pick_model()}:generateContent"
    for i in range(4):
        r = requests.post(url, headers=HDR, json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json"}}, timeout=180)
        if r.status_code in (429, 500, 503):
            print("retry", r.status_code, r.text[:200], flush=True)
            time.sleep(20 * (i + 1))
            continue
        if r.status_code != 200:
            print("GEMINI ERROR", r.status_code, r.text[:800], flush=True)
        r.raise_for_status()
        txt = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        txt = re.sub(r"^```(?:json)?\s*|\s*```$", "", txt.strip())
        return json.loads(txt)
    raise RuntimeError("gemini retries exhausted")

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