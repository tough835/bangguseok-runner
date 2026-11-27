#!/usr/bin/env python3
"""11/27 보스 "검증되고 확실한 것만 오픈" — 코스 노선 ↔ 오픈스트리트맵(그림 지도) 길 대조, 한 번에 전체.

route_osm_probe.py(Overpass)는 너무 느려 한 번에 10~40코스만 받혔음 → 한국 전체 지도 파일(Geofabrik
south-korea-latest.osm.pbf)을 받아 컴퓨터 안에서 바로 대조. 결과 형식은 같음 → data/route_osm_probe.json
(같은 id는 새 결과로 덮어씀, 'how': 'pbf').

입력 data/osm_probe_list.json [{id, name, kind, lab, file}]
쓰는 법(Actions osm-local): python tools/route_osm_local.py [지도파일.pbf]
잣대(index.html VERIFY_LAB 판정에 씀): 길 밖(30m 안에 길 없음) > 5% · 자전거 코스 산길 > 3% · 찻길 > 40% 이면 불합격
"""
import json, math, sys, os, urllib.request, time
import osmium

PBF = sys.argv[1] if len(sys.argv) > 1 else 'south-korea-latest.osm.pbf'
URL = 'https://download.geofabrik.de/asia/south-korea-latest.osm.pbf'
GX, GY = 0.0005, 0.0006   # 격자 한 칸 ≈ 55m


def hav(a, b):
    p = math.pi / 180; x = (b[1] - a[1]) * p * math.cos((a[0] + b[0]) / 2 * p); y = (b[0] - a[0]) * p
    return 6371000 * math.hypot(x, y)


def resample(p, step):
    out = [p[0]]; carry = 0
    for i in range(len(p) - 1):
        a, b = p[i], p[i + 1]; d = hav(a, b); t = step - carry
        while t <= d: out.append([a[0] + (b[0] - a[0]) * t / d, a[1] + (b[1] - a[1]) * t / d]); t += step
        carry = d - (t - step) if d else carry
    return out


def segd(q, a, b):   # 점 q ↔ 선분 a-b 거리(m)
    cl = math.cos(q[0] * math.pi / 180)
    ax, ay = (a[1] - q[1]) * 111320 * cl, (a[0] - q[0]) * 110540
    bx, by = (b[1] - q[1]) * 111320 * cl, (b[0] - q[0]) * 110540
    dx, dy = bx - ax, by - ay; L = dx * dx + dy * dy
    t = 0 if L == 0 else max(0, min(1, -(ax * dx + ay * dy) / L))
    return math.hypot(ax + dx * t, ay + dy * t)


cell = lambda la, lo: (int(la / GX), int(lo / GY))
TRAIL = {'path', 'track', 'bridleway', 'steps'}
CAR = {'motorway', 'trunk', 'primary', 'secondary', 'tertiary', 'motorway_link', 'trunk_link', 'primary_link', 'secondary_link'}

todo = json.load(open('data/osm_probe_list.json', encoding='utf-8'))
C = []
need = set()
for c in todo:
    try:
        p = [q[:2] for q in json.load(open(c['file'], encoding='utf-8'))['p']]
    except Exception as e:
        print('읽기 실패', c['id'], e); continue
    s = resample(p, 25)
    C.append((c, s))
    for q in s:
        gx, gy = cell(*q)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1): need.add((gx + dx, gy + dy))
print('코스', len(C), '격자', len(need), flush=True)

if not os.path.exists(PBF):
    t = time.time(); urllib.request.urlretrieve(URL, PBF); print('지도 파일 받음', os.path.getsize(PBF) // 2**20, 'MB', round(time.time() - t), '초', flush=True)

grid = {}


class H(osmium.SimpleHandler):
    def way(self, w):
        hw = w.tags.get('highway')
        if not hw: return
        try: g = [(n.lat, n.lon) for n in w.nodes]
        except osmium.InvalidLocationError: return
        tg = None
        for a, b in zip(g, g[1:]):
            n = max(1, int(hav(a, b) // 40))
            cs = {cell(a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n) for k in range(n + 1)}
            hit = [x for x in cs if x in need]
            if not hit: continue
            if tg is None: tg = {'highway': hw, 'tracktype': w.tags.get('tracktype'), 'bicycle': w.tags.get('bicycle'), 'name': w.tags.get('name')}
            for x in hit: grid.setdefault(x, []).append((a, b, tg))


t = time.time(); H().apply_file(PBF, locations=True, idx='flex_mem'); print('길 조각 정리', round(time.time() - t), '초', flush=True)

try: out = json.load(open('data/route_osm_probe.json', encoding='utf-8'))
except Exception: out = {}
for c, s in C:
    st = {'off': 0, 'trail': 0, 'steps': 0, 'car': 0, 'cycle': 0, 'foot': 0}; names = {}; offpts = []
    for q in s:
        gx, gy = cell(*q); best = None
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for a, b, t in grid.get((gx + dx, gy + dy), ()):
                    d = segd(q, a, b)
                    if best is None or d < best[0]: best = (d, t)
        if not best or best[0] > 30: st['off'] += 1; offpts.append([round(q[0], 5), round(q[1], 5), round(best[0]) if best else -1]); continue
        t = best[1]; hw = t['highway']
        if hw in TRAIL and not (hw == 'track' and t['tracktype'] == 'grade1') and not (hw == 'path' and t['bicycle'] in ('designated', 'yes')): st['trail'] += 1
        if hw == 'steps': st['steps'] += 25
        if hw in CAR: st['car'] += 1
        if hw == 'cycleway' or t['bicycle'] == 'designated': st['cycle'] += 1
        if hw in ('footway', 'pedestrian', 'path', 'living_street'): st['foot'] += 1
        nm = t['name'] or ('(' + hw + ')'); names[nm] = names.get(nm, 0) + 1
    n = max(1, len(s))
    out[c['id']] = {'name': c['name'], 'kind': c['kind'], 'lab': c['lab'], 'km': round(len(s) * 25 / 1000, 2),
        'off': round(100 * st['off'] / n, 1), 'trail': round(100 * st['trail'] / n, 1), 'steps_m': st['steps'], 'car': round(100 * st['car'] / n, 1),
        'cycle': round(100 * st['cycle'] / n, 1), 'foot': round(100 * st['foot'] / n, 1),
        'names': sorted(names.items(), key=lambda x: -x[1])[:6], 'rel': [], 'offpts': offpts[:12], 'how': 'pbf'}
    print(c['id'], {k: v for k, v in out[c['id']].items() if k in ('km', 'off', 'trail', 'car')})
json.dump(out, open('data/route_osm_probe.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
print('끝', len(C))
