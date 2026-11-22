# 11/22: 유튜브 추천 칸 고르기용 — 재생목록 후보를 받아 data/yt_probe.json 에 저장 (Actions 에서 실행)
import json, urllib.request, urllib.parse
F = 'https://mhlhebopdivaeremwtpl.supabase.co/functions/v1/bgr-yt-search?'
Q = ['러닝 음악 플레이리스트', '운동할때 듣는 케이팝', 'virtual walking tour 4K', '걷기 풍경 4K 서울', 'virtual cycling scenic ride 4K', '자전거 라이딩 풍경', '한국 등산 브이로그', 'hiking virtual trail 4K', '홈트 음악 플레이리스트']
out = {}
for q in Q:
    try:
        with urllib.request.urlopen(F + urllib.parse.urlencode({'q': q, 'type': 'playlist'}), timeout=40) as r: out[q] = json.load(r)
    except Exception as e: out[q] = {'err': str(e)[:120]}
json.dump(out, open('data/yt_probe.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
