import os, json, datetime, requests

BIBLE = open("story_bible.txt", encoding="utf8").read()
THEMES = ["나눔", "양치·손씻기", "정직하게 말하기", "기다림", "친구에게 사과하기", "정리정돈",
          "싫어하는 음식 도전", "무서움 이겨내기(안전한 수준)", "내 기분 말하기", "도움 요청하기",
          "안전(횡단보도·손잡기)", "계절과 자연", "색깔·숫자·모양 배우기", "가족 사랑", "친구 배려하기"]
URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

def call(prompt):
    r = requests.post(URL, headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"]},
                      json={"contents": [{"parts": [{"text": prompt}]}],
                            "generationConfig": {"responseMimeType": "application/json"}}, timeout=120)
    r.raise_for_status()
    return json.loads(r.json()["candidates"][0]["content"]["parts"][0]["text"])

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