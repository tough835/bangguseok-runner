# 11/25 보스 "엉뚱한 좌표 · 자전거 길에 산길 · 임의로 찍은 코스" 점검: 노선을 오픈스트리트맵 길 정보와 대조 (GitHub Actions에서 실행)
#   입력 data/osm_probe_list.json [{id, name, kind, file}] → 출력 data/route_osm_probe.json
#   노선을 25m마다 찍어 가장 가까운 길(highway)을 찾음:
#     off      = 30m 안에 길이 없는 점 비율 (바다·건물 위 = 엉뚱한 좌표)
#     trail    = 산길(path·track·bridleway, 계단 steps 포함) 비율 · steps = 계단 길이(m)
#     car      = 큰 찻길(trunk·primary·secondary·tertiary) 비율 · cycle = 자전거길 비율
#     names    = 노선이 지나는 길 이름 상위 · rel = 지나는 공식 노선 관계(자전거길·둘레길) 이름
import json, math, time, urllib.request, urllib.parse
UA = {'User-Agent': 'bangguseok-runner/1.0 (github.com/tough835/bangguseok-runner)'}
OVP = ['https://overpass-api.de/api/interpreter', 'https://overpass.private.coffee/api/interpreter', 'https://overpass.kumi.systems/api/interpreter']
def hav(a, b):
    p = math.pi / 180; x = (b[1] - a[1]) * p * math.cos((a[0] + b[0]) / 2 * p); y = (b[0] - a[0]) * p
    return 6371000 * math.hypot(x, y)
def segd(q, a, b):
    k = math.cos(a[0] * math.pi / 180); ax, ay, bx, by, px, py = a[1] * k, a[0], b[1] * k, b[0], q[1] * k, q[0]
    dd = (bx - ax) ** 2 + (by - ay) ** 2
    t = 0 if dd == 0 else max(0, min(1, ((px - ax) * (bx - ax) + (py - ay) * (by - ay)) / dd))
    return hav(q, [ay + (by - ay) * t, (ax + (bx - ax) * t) / k])
def resample(p, step):
    out = [p[0]]; carry = 0
    for i in range(len(p) - 1):
        a, b = p[i], p[i + 1]; d = hav(a, b); t = step - carry
        while t <= d: out.append([a[0] + (b[0] - a[0]) * t / d, a[1] + (b[1] - a[1]) * t / d]); t += step
        carry = d - (t - step) if d else carry
    return out
def ovp(ql):
    for k in range(6):
        host = OVP[k % len(OVP)]
        try:
            time.sleep(2 + 3 * k)
            r = urllib.request.urlopen(urllib.request.Request(host, ('data=' + urllib.parse.quote(ql)).encode(), UA), timeout=100)
            return json.load(r)
        except Exception as e: print('  overpass 실패', host[8:30], str(e)[:80])
    return None
TRAIL = {'path', 'track', 'bridleway', 'steps'}; CAR = {'motorway', 'trunk', 'primary', 'secondary', 'tertiary', 'motorway_link', 'trunk_link', 'primary_link', 'secondary_link'}
try: out = json.load(open('data/route_osm_probe.json', encoding='utf-8'))   # 이어 하기: 이미 받은 코스는 건너뜀
except Exception: out = {}
todo = sorted(json.load(open('data/osm_probe_list.json', encoding='utf-8')), key=lambda c: c['lab'])   # 일반 목록 코스 먼저
for c in todo:
    if c['id'] in out and 'err' not in out[c['id']]: continue
    p = [q[:2] for q in json.load(open(c['file'], encoding='utf-8'))['p']]
    s = resample(p, 25); line = resample(p, 150)
    coords = ','.join('%.5f,%.5f' % (q[0], q[1]) for q in line[:400])
    j = ovp('[out:json][timeout:90];way["highway"](around:60,%s)->.w;.w out geom;rel(bw.w)["route"~"bicycle|hiking|foot|mtb"];out tags;' % coords)
    if not j: out[c['id']] = {'err': 'overpass'}; continue
    ways = [e for e in j['elements'] if e['type'] == 'way']; rels = [e for e in j['elements'] if e['type'] == 'relation']
    segs = []
    for w in ways:
        g = w.get('geometry') or []
        for i in range(len(g) - 1): segs.append(([g[i]['lat'], g[i]['lon']], [g[i + 1]['lat'], g[i + 1]['lon']], w))
    grid = {}
    for sg in segs:
        for q in (sg[0], sg[1]): grid.setdefault((int(q[0] / 0.0005), int(q[1] / 0.0006)), []).append(sg)
    st = {'off': 0, 'trail': 0, 'steps': 0, 'car': 0, 'cycle': 0, 'foot': 0, 'n': len(s)}; names = {}; offpts = []
    for q in s:
        gx, gy = int(q[0] / 0.0005), int(q[1] / 0.0006); best = None
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for a, b, w in grid.get((gx + dx, gy + dy), ()):
                    d = segd(q, a, b)
                    if best is None or d < best[0]: best = (d, w)
        if not best or best[0] > 30: st['off'] += 1; offpts.append([round(q[0], 5), round(q[1], 5), round(best[0]) if best else -1]); continue
        t = best[1].get('tags', {}); hw = t.get('highway', '')
        if hw in TRAIL and not (hw == 'track' and t.get('tracktype') == 'grade1') and not (hw == 'path' and t.get('bicycle') in ('designated', 'yes')): st['trail'] += 1
        if hw == 'steps': st['steps'] += 25
        if hw in CAR: st['car'] += 1
        if hw == 'cycleway' or t.get('bicycle') == 'designated': st['cycle'] += 1
        if hw in ('footway', 'pedestrian', 'path', 'living_street'): st['foot'] += 1
        nm = t.get('name') or ('(' + hw + ')'); names[nm] = names.get(nm, 0) + 1
    n = max(1, len(s))
    out[c['id']] = {'name': c['name'], 'kind': c['kind'], 'lab': c['lab'], 'km': round(len(s) * 25 / 1000, 2),
        'off': round(100 * st['off'] / n, 1), 'trail': round(100 * st['trail'] / n, 1), 'steps_m': st['steps'], 'car': round(100 * st['car'] / n, 1),
        'cycle': round(100 * st['cycle'] / n, 1), 'foot': round(100 * st['foot'] / n, 1),
        'names': sorted(names.items(), key=lambda x: -x[1])[:6], 'rel': sorted({(r.get('tags') or {}).get('name', '') for r in rels} - {''})[:8], 'offpts': offpts[:12]}
    print(c['id'], {k: v for k, v in out[c['id']].items() if k not in ('names', 'rel', 'offpts')})
    json.dump(out, open('data/route_osm_probe.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
