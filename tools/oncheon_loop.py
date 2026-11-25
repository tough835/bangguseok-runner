# 11/25 보스 "온천천은 하천 양쪽 길을 수영~부산대 순환으로 많이 씀, 교대·연산동에서 출발": 하천 양안 산책로 순환 노선 만들기 (GitHub Actions)
#   1) Overpass: 물길 '온천천' + 그 120m 안 걷는 길(footway·path·cycleway·pedestrian) + 물길 위 다리
#   2) 물길을 하류(수영강 합류)→상류로 잇고 250m마다 왼쪽·오른쪽 기슭 산책로 점을 고름
#   3) 왼쪽 기슭으로 올라가 다리로 건너 오른쪽 기슭으로 내려오는 순환 → OSRM 걷기 길 찾기 → 시계 반대로 맞춤
#   4) 검증: 노선 점 가운데 산책로(걷는 길) 위 비율 · 찻길 위 비율
# 결과 data/route/oncheon-loop-<이름>.json + data/oncheon_loop_log.json
import json, math, time, urllib.request, urllib.parse
UA = {'User-Agent': 'bangguseok-runner/1.0 (github.com/tough835/bangguseok-runner)'}
OVP = ['https://overpass-api.de/api/interpreter', 'https://overpass.private.coffee/api/interpreter', 'https://overpass.kumi.systems/api/interpreter']
LOG = {}
def get(u, data=None):
    with urllib.request.urlopen(urllib.request.Request(u, data, UA), timeout=150) as r: return json.load(r)
def ovp(ql):
    for k in range(9):
        try: time.sleep(2 + 2 * k); return get(OVP[k % 3], ('data=' + urllib.parse.quote(ql)).encode())
        except Exception as e: print('overpass 실패', OVP[k % 3][8:30], str(e)[:80])
    raise SystemExit('overpass 안 됨')
def hav(a, b):
    p = math.pi / 180; x = (b[1] - a[1]) * p * math.cos((a[0] + b[0]) / 2 * p); y = (b[0] - a[0]) * p
    return 6371000 * math.hypot(x, y)
def cum(p):
    c = [0.0]
    for i in range(len(p) - 1): c.append(c[-1] + hav(p[i], p[i + 1]))
    return c
K = math.cos(35.2 * math.pi / 180)
def xy(q): return (q[1] * K * 111320, q[0] * 110540)
WALK = 'footway|path|cycleway|pedestrian|living_street|track'
CAR = {'motorway', 'trunk', 'primary', 'secondary', 'tertiary', 'trunk_link', 'primary_link', 'secondary_link', 'tertiary_link'}
BB = '(35.15,129.03,35.32,129.13)'   # 부산 온천천만 (아산 온천천 제외)
j = ovp('[out:json][timeout:150];(way["waterway"~"^(river|stream|canal)$"]["name"="온천천"]%s;rel["waterway"]["name"="온천천"]%s;)->.a;(way.a;way(r.a)["waterway"~"^(river|stream|canal)$"];)->.r;(way(around.r:130)["highway"];)->.h;(.r;.h;);out geom;' % (BB, BB))
riv = [e for e in j['elements'] if e.get('tags', {}).get('waterway') in ('river', 'stream', 'canal')]
# 하류(교대~수영강): 이름 '온천천' 물길 조각이 없음 → 그 상자 안 물길(이름 없거나 '온천' 들어간 것)을 함께 이어 붙임 · 기록
DB_ = '(35.180,129.078,35.200,129.110)'
j2 = ovp('[out:json][timeout:120];(way["waterway"]%s;way["name"~"온천"]%s;)->.d;(.d;way(around.d:130)["highway"];);out geom;' % (DB_, DB_))
LOG['down_ways'] = []
for e in j2['elements']:
    t = e.get('tags', {}); g = e.get('geometry') or []
    if 'highway' in t or not g: continue
    LOG['down_ways'].append([t.get('name', ''), t.get('waterway', ''), t.get('natural', ''), t.get('tunnel', ''), len(g), [round(g[0]['lat'], 5), round(g[0]['lon'], 5)], [round(g[-1]['lat'], 5), round(g[-1]['lon'], 5)]])
    nm = t.get('name', '')
    if t.get('waterway') in ('river', 'stream', 'canal') and (nm == '' or '온천' in nm) and e['id'] not in [r_['id'] for r_ in riv]: riv.append(e)
ids = set(e['id'] for e in j['elements'])
j['elements'] += [e for e in j2['elements'] if 'highway' in e.get('tags', {}) and e['id'] not in ids]
hw = [e for e in j['elements'] if 'highway' in e.get('tags', {})]
print('물길 조각', len(riv), '길', len(hw))
# 물길 잇기 (끝점끼리)
segs = [[[g['lat'], g['lon']] for g in w['geometry']] for w in riv if w.get('geometry')]
# 하류(수영강 쪽) 끝에서 출발해, 꼬리에 가장 가까운 조각을 차례로 붙임 (보·복개로 끊긴 틈 800m까지)
SUYEONG = [35.1925, 129.1055]
pool = [w for w in segs if len(w) > 1]
LOG['pieces'] = [[round(cum(w)[-1]), [round(x, 5) for x in w[0]], [round(x, 5) for x in w[-1]]] for w in pool]
st = min(pool, key=lambda w: min(hav(w[0], SUYEONG), hav(w[-1], SUYEONG))); pool.remove(st)
r = st if hav(st[0], SUYEONG) <= hav(st[-1], SUYEONG) else st[::-1]
while pool:
    cands = [(min(hav(w[0], r[-1]), hav(w[-1], r[-1])), i) for i, w in enumerate(pool)]
    d, i = min(cands)
    if d > 800: break
    w = pool.pop(i); w = w if hav(w[0], r[-1]) <= hav(w[-1], r[-1]) else w[::-1]
    if hav(w[-1], SUYEONG) < hav(r[-1], SUYEONG) - 50: continue   # 거꾸로(하류 쪽으로) 가는 조각은 버림
    r = r + w
best = r
river = best
SUYEONG = [35.1925, 129.1055]   # 수영강 쪽(하류)을 앞으로
if hav(river[-1], SUYEONG) < hav(river[0], SUYEONG): river = river[::-1]
rc = cum(river); RL = rc[-1]
print('물길 길이 %.1fkm  하류 %s  상류 %s' % (RL / 1000, river[0], river[-1]))
def proj(q):   # 물길 위 거리(m)와 그 점까지 떨어진 거리
    bi, bd = 0, 1e18
    for i in range(len(river)):
        d = hav(q, river[i])
        if d < bd: bi, bd = i, d
    return rc[bi], bd, bi
def side(q, i):   # +1 왼쪽(하류→상류 진행 기준) / -1 오른쪽
    a = xy(river[max(0, i - 1)]); b = xy(river[min(len(river) - 1, i + 1)]); c = xy(q)
    return 1 if (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]) > 0 else -1
# 걷는 길 점(10m 간격)
walkpts = []; carsegs = []; walksegs = []; bridges = []
for w in hw:
    t = w['tags']; g = [[x['lat'], x['lon']] for x in w.get('geometry') or []]
    if len(g) < 2: continue
    h = t.get('highway', '')
    for i in range(len(g) - 1):
        (carsegs if h in CAR else walksegs if h in WALK.split('|') else []).append((g[i], g[i + 1]))
    if t.get('bridge') == 'yes':
        mid = g[len(g) // 2]; s, d, i = proj(mid)
        if d < 25: bridges.append({'s': s, 'p': mid, 'name': t.get('name', ''), 'hw': h})
    if h in WALK.split('|') and t.get('bridge') != 'yes':
        for i in range(len(g) - 1):
            n = max(1, int(hav(g[i], g[i + 1]) // 10))
            for k in range(n): walkpts.append([g[i][0] + (g[i + 1][0] - g[i][0]) * k / n, g[i][1] + (g[i + 1][1] - g[i][1]) * k / n])
print('걷는 길 점', len(walkpts), '다리', len(bridges))
# 250m마다 양쪽 기슭 점
bank = {1: [], -1: []}; cover = {1: 0, -1: 0}
for s0 in range(0, int(RL), 250):
    i0 = min(range(len(rc)), key=lambda i: abs(rc[i] - s0)); c0 = river[i0]
    for sd in (1, -1):
        cand = [q for q in walkpts if 12 < hav(q, c0) < 110 and side(q, i0) == sd and abs(proj(q)[0] - s0) < 60] if False else None
        bestq = None; bd = 1e9
        for q in walkpts:
            d = hav(q, c0)
            if 12 < d < 110 and d < bd and side(q, i0) == sd: bestq, bd = q, d
        if bestq: bank[sd].append((s0, bestq)); cover[sd] += 250
LOG['river_km'] = round(RL / 1000, 2); LOG['bank_km'] = {'left': cover[1] / 1000, 'right': cover[-1] / 1000}
LOG['bridges'] = [[round(b['s']), b['name'], b['hw']] for b in sorted(bridges, key=lambda b: b['s'])]
# 연속 산책로 구간 (양쪽 다 있는 곳)
both = sorted(set(s for s, _ in bank[1]) & set(s for s, _ in bank[-1]))
LOG['both_banks'] = [both[0], both[-1]] if both else None
print('양쪽 기슭 산책로', LOG['bank_km'], '양쪽 다 있는 구간', LOG['both_banks'])
def route(pts):
    u = 'https://routing.openstreetmap.de/routed-foot/route/v1/driving/' + ';'.join('%.6f,%.6f' % (q[1], q[0]) for q in pts) + '?overview=full&geometries=geojson'
    for k in range(4):
        try: time.sleep(2 + 3 * k); r = get(u)['routes'][0]; return [[round(c[1], 6), round(c[0], 6)] for c in r['geometry']['coordinates']]
        except Exception as e: print('OSRM 실패', str(e)[:80])
    return None
def segd(q, a, b):
    ax, ay = xy(a); bx, by = xy(b); px, py = xy(q); dd = (bx - ax) ** 2 + (by - ay) ** 2
    t = 0 if dd == 0 else max(0, min(1, ((px - ax) * (bx - ax) + (py - ay) * (by - ay)) / dd))
    return math.hypot(px - (ax + (bx - ax) * t), py - (ay + (by - ay) * t))
def share_old(p, sg):
    grid = {}
    for a, b in sg:
        for q in (a, b): grid.setdefault((int(q[0] / 0.0004), int(q[1] / 0.0005)), []).append((a, b))
    c = cum(p); n = 0; tot = 0; s = 0.0
    while s < c[-1]:
        i = max(0, min(len(p) - 2, next(k for k in range(len(c)) if c[k] >= s) - 1)); q = p[i]
        g = (int(q[0] / 0.0004), int(q[1] / 0.0005)); ok = any(segd(q, a, b) < 12 for dx in (-1, 0, 1) for dy in (-1, 0, 1) for a, b in grid.get((g[0] + dx, g[1] + dy), ()))
        n += ok; tot += 1; s += 20
    return round(100 * n / max(1, tot), 1)
def kinds(p):   # 노선 20m마다 가장 가까운 길 종류 → (걷는 길 %, 찻길 %)
    allseg = [(a, b, 'w') for a, b in walksegs] + [(a, b, 'c') for a, b in carsegs]
    grid = {}
    for a, b, k in allseg:
        for q in (a, b): grid.setdefault((int(q[0] / 0.0004), int(q[1] / 0.0005)), []).append((a, b, k))
    c = cum(p); n = {'w': 0, 'c': 0, 'x': 0}; s = 0.0; i = 0
    while s < c[-1]:
        while i < len(c) - 2 and c[i + 1] < s: i += 1
        q = p[i]; g = (int(q[0] / 0.0004), int(q[1] / 0.0005)); best = (1e9, 'x')
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for a, b, k in grid.get((g[0] + dx, g[1] + dy), ()):
                    d = segd(q, a, b)
                    if d < best[0]: best = (d, k)
        n[best[1] if best[0] < 15 else 'x'] += 1; s += 20
    t = max(1, sum(n.values())); return round(100 * n['w'] / t, 1), round(100 * n['c'] / t, 1)
def area(p): return sum(xy(p[i])[0] * xy(p[(i + 1) % len(p)])[1] - xy(p[(i + 1) % len(p)])[0] * xy(p[i])[1] for i in range(len(p))) / 2
def bridge_near(s, walk_first=True):
    bs = sorted(bridges, key=lambda b: (abs(b['s'] - s) + (0 if b['hw'] in WALK.split('|') else 150)))
    return bs[0] if bs else None
ST = {'교대역': [35.1958, 129.0797], '연산역': [35.1859, 129.0817], '동래역': [35.2054, 129.0786], '온천장역': [35.2203, 129.0865], '부산대역': [35.2297, 129.0889]}
LOG['stations'] = {k: [round(proj(v)[0]), round(proj(v)[1])] for k, v in ST.items()}
print('역 위치(물길 m, 떨어진 m)', LOG['stations'])
def loop(name, s1, s2, start_name):
    b1 = bridge_near(s1); b2 = bridge_near(s2)
    if not b1 or not b2: LOG[name] = '다리 못 찾음'; return
    s1, s2 = min(b1['s'], b2['s']), max(b1['s'], b2['s'])
    if s2 - s1 < 400: LOG[name] = '다리 사이가 너무 짧음 %d~%d' % (s1, s2); return
    lb = [q for s, q in bank[1] if s1 + 80 < s < s2 - 80]; rb = [q for s, q in bank[-1] if s1 + 80 < s < s2 - 80][::-1]
    step = max(1, len(lb) // 20)
    vias = [b1['p']] + lb[::step] + [b2['p']] + rb[::step] + [b1['p']]
    p = route(vias)
    if not p: LOG[name] = 'OSRM 실패'; return
    if area(p) < 0: p = p[::-1]   # 시계 반대
    # 출발점을 start_name 역에 가장 가까운 점으로 돌림
    st = ST[start_name]; k0 = min(range(len(p)), key=lambda i: hav(p[i], st)); p = p[k0:] + p[1:k0 + 1]
    c = cum(p); marks = []
    for nm, q in list(ST.items()) + [('하류 쪽 다리 ' + (b1['name'] or ''), b1['p']), ('상류 쪽 다리 ' + (b2['name'] or ''), b2['p'])]:
        i = min(range(len(p)), key=lambda i: hav(p[i], q)); off = hav(p[i], q)
        if off < 250: marks.append([nm.strip(), round(c[i]), round(q[0], 6), round(q[1], 6), round(off)])
    out = {'p': p, 'km': round(c[-1] / 1000, 2), 'how': 'OSRM', 'src': '오픈스트리트맵 걷기 길 찾기(OSRM) · 온천천 양쪽 기슭 산책로 점(Overpass)', 'marks': sorted(marks, key=lambda m: m[1]),
           'walk_pct': kinds(p)[0], 'car_pct': kinds(p)[1], 'bridges': [b1['name'], b2['name']], 'span': [round(s1), round(s2)]}
    json.dump(out, open('data/route/oncheon-loop-%s.json' % name, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    LOG[name] = {k: v for k, v in out.items() if k != 'p'}; print(name, LOG[name])
sy, gd, yn, bu = 0, LOG['stations']['교대역'][0], LOG['stations']['연산역'][0], LOG['stations']['부산대역'][0]
top = min(bu, both[-1]) if both else bu
loop('full', (both[0] if both else 0), top, '교대역')          # 수영강 쪽 ~ 부산대 쪽 (양쪽 산책로 있는 끝까지)
loop('short', min(yn, gd) - 150, max(yn, gd) + 150, '교대역')   # 연산동 ~ 교대
loop('mid', (both[0] if both else 0), gd + 150, '교대역')         # 수영강 쪽 ~ 교대
loop('upper', gd - 150, top, '교대역')                            # 교대 ~ 부산대 쪽
json.dump(LOG, open('data/oncheon_loop_log.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
