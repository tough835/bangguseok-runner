# 11/23 보스 "산 코스에 지도가 없다": 등산로 자료(GPX)가 없는 산 → 오픈스트리트맵 등산로로 출발점~정상 길 만들기
# 지점 이름(출발 주차장·중간 봉우리·정상)을 지도에서 찾고(Overpass → Nominatim) Valhalla 걷기 길(등산로 포함)로 이음
# 높이는 Open-Meteo. 결과 data/mtn/<id>.json, 점검 기록 data/mtn_fetch_log.json (거리 비율·정상까지 남은 거리)
import json, urllib.request, urllib.parse, time, math, os
UA = {'User-Agent': 'bangguseok-runner/1.0 (github.com/tough835/bangguseok-runner)'}
def get(u, data=None, ct=None):
    h = dict(UA)
    if ct: h['Content-Type'] = ct
    with urllib.request.urlopen(urllib.request.Request(u, data=data, headers=h), timeout=45) as r: return json.load(r)
def hav(a, b):
    p = math.pi / 180; x = (b[1] - a[1]) * p * math.cos((a[0] + b[0]) / 2 * p); y = (b[0] - a[0]) * p
    return 6371000 * math.hypot(x, y)
def poly6(s):
    i = la = lo = 0; out = []
    while i < len(s):
        for k in range(2):
            sh = res = 0
            while True:
                b = ord(s[i]) - 63; i += 1; res |= (b & 0x1f) << sh; sh += 5
                if b < 0x20: break
            d = ~(res >> 1) if res & 1 else res >> 1
            if k == 0: la += d
            else: lo += d
        out.append([la / 1e6, lo / 1e6])
    return out

HY = (35.35, 127.45, 35.80, 127.95); JJ = (33.10, 126.10, 33.60, 127.00); FJ = (35.30, 138.60, 35.45, 138.80)
M = [  # id, 산 이름(정상), 지점들(출발→…→정상), 상자, 공식 거리 km
 ('gamtu', '감투산', ['빼빼재', '감투산'], HY, 1.0),
 ('sambong', '삼봉산', ['오도재', '오도봉', '삼봉산'], HY, 3.7),
 ('daebong', '계관봉', ['빼빼재', '감투산', '대봉산', '계관봉'], HY, 4.6),
 ('baegun', '백운산', ['빼빼재', '서래봉', '백운산'], HY, 5.1),
 ('yeongchwi', '영취산', ['부전마을', '덕운봉', '영취산'], HY, 4.7),
 ('dosung', '도숭산', ['주암마을', '도숭산'], HY, 5.3),
 ('wolbong', '월봉산', ['노상', '큰목재', '월봉산'], HY, 5.0),
 ('wabul', '와불산', ['벽송사', '와불산'], HY, 4.8),
 ('geomang', '거망산', ['용추사', '거망산'], HY, 4.7),
 ('samjeong', '삼정산', ['도마', '삼불사', '삼정산'], HY, 5.0),
 ('abu', '아부오름', ['아부오름'], JJ, 1.5),
 ('yongnuni', '용눈이오름', ['용눈이오름'], JJ, 1.0),
 ('geumoreum', '금오름', ['금오름'], JJ, 1.2),
 ('darangswi', '다랑쉬오름', ['다랑쉬오름'], JJ, 1.3),
 ('saebyeol', '새별오름', ['새별오름'], JJ, 1.0),
 ('seongsan', '성산일출봉', ['성산일출봉'], JJ, 1.0),
 ('fuji-yoshida', '富士山', ['富士スバルライン五合目', '剣ヶ峰'], FJ, 6.8),
]
OVP = ['https://overpass-api.de/api/interpreter', 'https://overpass.kumi.systems/api/interpreter']
def ovp(q):
    last = None
    for u in OVP:
        try: return get(u, urllib.parse.urlencode({'data': q}).encode(), 'application/x-www-form-urlencoded')
        except Exception as e: last = e; print('  ovp fail', u, str(e)[:80], flush=True); time.sleep(3)
    raise last
def find(name, box, peak=False):
    s, w, n, e = box
    q = '[out:json][timeout:25];(node["name"~"^%s"](%f,%f,%f,%f);way["name"~"^%s"](%f,%f,%f,%f););out center 20;' % (name, s, w, n, e, name, s, w, n, e)
    try:
        els = ovp(q).get('elements', [])
        def sc(x):
            t = x.get('tags', {}); k = 0
            if t.get('natural') in ('peak', 'saddle', 'volcano', 'hill'): k -= 3 if peak else 1
            if t.get('amenity') == 'parking' or t.get('place'): k -= 0 if peak else 2
            if t.get('name') == name: k -= 1
            return k
        els.sort(key=sc)
        for x in els:
            c = (x['lat'], x['lon']) if 'lat' in x else (x['center']['lat'], x['center']['lon']) if 'center' in x else None
            if c: return [c[0], c[1], x.get('tags', {}).get('name'), x.get('tags', {}).get('natural') or x.get('tags', {}).get('amenity') or x.get('tags', {}).get('place') or '']
    except Exception as ex: print('ovp', name, ex)
    time.sleep(1)
    try:
        r = get('https://nominatim.openstreetmap.org/search?' + urllib.parse.urlencode({'q': name, 'format': 'json', 'limit': 1, 'viewbox': '%f,%f,%f,%f' % (w, n, e, s), 'bounded': 1}))
        if r: return [float(r[0]['lat']), float(r[0]['lon']), r[0].get('display_name', '')[:40], 'nominatim']
    except Exception as ex: print('nom', name, ex)
    return None
def route(pts):
    body = {'locations': [{'lat': p[0], 'lon': p[1]} for p in pts], 'costing': 'pedestrian', 'costing_options': {'pedestrian': {'max_hiking_difficulty': 6, 'use_hills': 1}}}
    j = get('https://valhalla1.openstreetmap.de/route?json=' + urllib.parse.quote(json.dumps(body)))
    co = []
    for lg in j['trip']['legs']: co += poly6(lg['shape'])
    return co
def thin(co, step=12):
    out = [co[0]]
    for c in co[1:]:
        if hav(out[-1], c) >= step: out.append(c)
    if out[-1] != co[-1]: out.append(co[-1])
    return out
def elev(co):
    es = []
    for i in range(0, len(co), 100):
        ch = co[i:i + 100]
        j = get('https://api.open-meteo.com/v1/elevation?' + urllib.parse.urlencode({'latitude': ','.join('%.5f' % c[0] for c in ch), 'longitude': ','.join('%.5f' % c[1] for c in ch)}))
        es += j['elevation']; time.sleep(1)
    return es

os.makedirs('data/mtn', exist_ok=True)
try: log = json.load(open('data/mtn_fetch_log.json', encoding='utf-8'))
except Exception: log = {}
for mid, peak, via, box, km in M:
    if mid in log and 'km' in log[mid]: continue
    rec = {'via': []}
    try:
        pts = []
        for i, nm in enumerate(via):
            f = find(nm, box, peak=(i == len(via) - 1) or i > 0); rec['via'].append([nm, f]); time.sleep(3)
            if f: pts.append(f[:2])
        if len(via) == 1 and pts:   # 오름: 정상만 알면 → 가장 가까운 주차장에서 출발
            s0 = pts[0]; q = '[out:json][timeout:60];node["amenity"="parking"](around:1500,%f,%f);out 10;' % (s0[0], s0[1])
            ps = sorted(ovp(q).get('elements', []), key=lambda x: hav(s0, (x['lat'], x['lon'])))
            if ps: pts = [[ps[0]['lat'], ps[0]['lon']]] + pts; rec['start'] = 'parking %dm' % hav(s0, pts[0])
        if len(pts) < 2: rec['err'] = 'points'; log[mid] = rec; continue
        co = thin(route(pts)); L = sum(hav(co[i], co[i + 1]) for i in range(len(co) - 1))
        es = elev(co)
        rec.update({'km': round(L / 1000, 2), 'ratio': round(L / 1000 / km, 2), 'n': len(co), 'end_to_peak_m': round(hav(co[-1], pts[-1])), 'e0': es[0], 'e1': es[-1], 'emax': max(es)})
        json.dump({'src': '오픈스트리트맵 등산로(Valhalla) · 높이 Open-Meteo · 11/23 자동 생성', 'p': [[round(c[0], 5), round(c[1], 5), round(e)] for c, e in zip(co, es)]}, open('data/mtn/%s.json' % mid, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    except Exception as ex: rec['err'] = str(ex)[:200]
    log[mid] = rec; print(mid, rec, flush=True); time.sleep(2)
    json.dump(log, open('data/mtn_fetch_log.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
json.dump(log, open('data/mtn_fetch_log.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
