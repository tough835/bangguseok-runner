# 11/22: 추천 칸 재생목록이 실제로 영상을 돌려주는지 확인 → data/yt_lists.json
import json, urllib.request, urllib.parse
F = 'https://mhlhebopdivaeremwtpl.supabase.co/functions/v1/bgr-yt-search?'
P = {'러닝 음악': 'PLx1uUaAhAnmvPQYN48PWINQ7RKewq7cjJ', '가볍게 걷기 음악': 'PLz91Z_68dOj3Si3vqRyUJl3xpZG4u8SWi', '케이팝 운동': 'PL4fQaQrmnpKD8IEhkVNU3L6t6-a5NaV01',
     '한국 걷기': 'PL_uLYGDZi5I4-H0nfY0ae6s1XLfNJhl3L', '서울 걷기': 'PLnAxu-ique9fiejvmVYCVeEYTPI6deaJd', '세계 걷기': 'PL0eFt2-5YwurCWrdyEnzV6U1vSXP5T4BI',
     '자전거 풍경': 'PLYKRCrVXG2QCR6GmX4yMQW0sh1nyb5gOc', '국내 라이딩': 'PLmJZvsihZooOmkCLlSZsBW3d9bKy89ite', '산길 걷기': 'PLbWPytS1GWJKR7K-l8WRXtdhksrGzGz0m'}
out = {}
for k, pl in P.items():
    try:
        with urllib.request.urlopen(F + urllib.parse.urlencode({'pl': pl}), timeout=40) as r: j = json.load(r)
        out[k] = {'pl': pl, 'n': len(j.get('items', [])), 'err': j.get('err'), 'first': [x['t'][:50] for x in j.get('items', [])[:4]]}
    except Exception as e: out[k] = {'pl': pl, 'err': str(e)[:120]}
json.dump(out, open('data/yt_lists.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
