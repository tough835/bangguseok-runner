#!/usr/bin/env python3
"""11/27 보스 "3D 지도와 코스가 조금이라도 안 맞으면 실험실로" — 3D 화면 맞춤 자동 점검.

앱의 3D(index.html v3dLoad)는 위성 사진과 코스 선을 모두 같은 지형 높이 자료
(AWS terrarium, 조각 크기 14단계 = 한 칸 약 8m, 실제 해상도 30~90m)에 '덮어' 그린다.
그래서 위성 사진 위 길과 선은 서로 맞지만, 지형 높이 자료가 실제 길보다 거칠면
  · 다리·둑·벼랑·해안 옆 길이 3D에선 계곡·물속으로 꺼지거나 언덕을 타 넘는 것처럼 보이고
  · 산길은 실제 능선·계곡과 3D 언덕이 어긋나 선이 비탈 옆구리를 지나는 것처럼 보인다.
이 도구는 앱과 똑같은 높이 조각을 받아 코스를 10m마다 짚어 보고, 아래 중 하나라도 있으면 '불합격'.

  sea   : 높이 < -0.5m 인 점이 하나라도 (3D에서 길이 바닷속·물속으로 꺼짐)
  bump  : 앞뒤 60m 평균보다 갑자기 솟거나 꺼진 정도(m) — 길 코스 > 6m, 산 > 15m 면 불합격
          (다리가 강바닥으로 꺼짐, 둑·벼랑 끝 길이 아래로 떨어짐, 길이 언덕 옆구리를 넘음)
  grade : 50m 구간 경사 — 길 코스(도보·자전거) > 20% 면 불합격 (평지 길이 3D에선 가파른 비탈 위)
  dz    : 산 — 노선 파일의 높이(Open-Meteo)와 3D 지형 높이 차이 > 40m 면 불합격 (선이 엉뚱한 비탈 위)

쓰는 법: python3 -m http.server 8765 & node tools/course_dump.js  (data/course_dump.json 최신으로)
        python3 tools/route_3d_audit.py            → data/route_3d_audit.json + 화면 요약
기준이 엄격한 이유: 보스 "정확히 맞는 것만 오픈, 애매하면 뺀다". 실험실로 간 코스는 index.html V3D_LAB 에서 빼면 바로 복귀.
"""
import json, math, os, sys, io, urllib.request, concurrent.futures as cf
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.environ.get('DEM_CACHE', '/tmp/dem_cache')
Z = 14
os.makedirs(CACHE, exist_ok=True)
TH = dict(sea=-0.5, bump_road=6.0, bump_mtn=15.0, grade_road=0.20, dz_mtn=40.0)


def tile_path(x, y):
    return os.path.join(CACHE, f'{Z}_{x}_{y}.png')


def fetch(xy):
    x, y = xy
    p = tile_path(x, y)
    if os.path.exists(p) and os.path.getsize(p) > 0:
        return True
    url = f'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{Z}/{x}/{y}.png'
    for _ in range(3):
        try:
            b = urllib.request.urlopen(url, timeout=30).read()
            open(p, 'wb').write(b)
            return True
        except Exception:
            pass
    return False


_T = {}


def tile(x, y):
    k = (x, y)
    if k not in _T:
        im = Image.open(tile_path(x, y)).convert('RGB')
        _T[k] = im.load()
        if len(_T) > 4000:
            _T.clear()
    return _T[k]


def px(lat, lon):
    n = 2 ** Z
    fx = (lon + 180) / 360 * n
    s = math.sin(math.radians(lat))
    fy = (0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * n
    return fx * 256, fy * 256


def elev(lat, lon):   # 이중선형 보간(지도 그리는 쪽과 같은 방식)
    X, Y = px(lat, lon)
    X -= 0.5; Y -= 0.5
    x0, y0 = math.floor(X), math.floor(Y)
    tx, ty = X - x0, Y - y0
    def h(gx, gy):
        t = tile(gx // 256, gy // 256)
        r, g, b = t[gx % 256, gy % 256]
        return r * 256 + g + b / 256 - 32768
    return (h(x0, y0) * (1 - tx) * (1 - ty) + h(x0 + 1, y0) * tx * (1 - ty)
            + h(x0, y0 + 1) * (1 - tx) * ty + h(x0 + 1, y0 + 1) * tx * ty)


def dist(a, b):
    la = math.radians((a[0] + b[0]) / 2)
    return math.hypot((b[0] - a[0]) * 110540, (b[1] - a[1]) * 111320 * math.cos(la))


def densify(p, step=10.0):
    out = [(p[0][0], p[0][1], p[0][2] if len(p[0]) > 2 else None, 0.0)]
    s = 0.0
    for a, b in zip(p, p[1:]):
        d = dist(a, b)
        n = max(1, int(d // step))
        for i in range(1, n + 1):
            t = i / n
            za = a[2] if len(a) > 2 else None
            zb = b[2] if len(b) > 2 else None
            z = za + (zb - za) * t if za is not None and zb is not None else None
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, z, s + d * t))
        s += d
    return out


def tiles_for(pts):
    s = set()
    for la, lo, *_ in pts:
        X, Y = px(la, lo)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                s.add(((int(X) + dx) // 256, (int(Y) + dy) // 256))
    return s


def audit(pts, mtn):
    e = [elev(q[0], q[1]) for q in pts]
    d = [q[3] for q in pts]
    r = dict(km=round(d[-1] / 1000, 2), minE=round(min(e), 1), sea=sum(1 for v in e if v < TH['sea']))
    k = 6
    bump, bat = 0.0, None
    for i in range(k, len(e) - k):
        v = abs(e[i] - (e[i - k] + e[i + k]) / 2)
        if v > bump:
            bump, bat = v, i
    r['bump'] = round(bump, 1)
    r['bumpAt'] = [round(pts[bat][0], 5), round(pts[bat][1], 5), round(d[bat])] if bat is not None else None
    g, gat = 0.0, None
    for i in range(5, len(e)):
        dd = d[i] - d[i - 5]
        if dd > 30:
            v = abs(e[i] - e[i - 5]) / dd
            if v > g:
                g, gat = v, i
    r['grade'] = round(g, 3)
    r['gradeAt'] = [round(pts[gat][0], 5), round(pts[gat][1], 5), round(d[gat])] if gat is not None else None
    if mtn:
        dz = [abs(q[2] - v) for q, v in zip(pts, e) if q[2] is not None]
        r['dz'] = round(max(dz), 1) if dz else None
    why = []
    if r['sea']:
        why.append(f"물속 꺼짐 {r['sea']}점(최저 {r['minE']}m)")
    if r['bump'] > (TH['bump_mtn'] if mtn else TH['bump_road']):
        why.append(f"솟음·꺼짐 {r['bump']}m @{r['bumpAt'][2]}m")
    if not mtn and r['grade'] > TH['grade_road']:
        why.append(f"경사 {round(r['grade']*100)}% @{r['gradeAt'][2]}m")
    if mtn and r.get('dz') is not None and r['dz'] > TH['dz_mtn']:
        why.append(f"높이 차 {r['dz']}m")
    r['ok'] = not why
    r['why'] = why
    return r


def main():
    dump = json.load(open(os.path.join(ROOT, 'data/course_dump.json')))
    jobs = []
    for c in dump['roads']:
        if c.get('official'):
            jobs.append(('road', c, c['official']))
    for m in dump['mtns']:
        if m.get('geo'):
            jobs.append(('mtn', m, m['geo']))
    paths = {}
    for kind, c, f in jobs:
        try:
            j = json.load(open(os.path.join(ROOT, f)))
            paths[(kind, c['id'])] = densify(j['p'])
        except Exception as ex:
            print('읽기 실패', c['id'], f, ex, file=sys.stderr)
    need = set()
    for p in paths.values():
        need |= tiles_for(p)
    print('높이 조각', len(need), file=sys.stderr)
    with cf.ThreadPoolExecutor(24) as ex:
        bad = [t for t, ok in zip(need, ex.map(fetch, need)) if not ok]
    if bad:
        print('못 받은 조각', len(bad), file=sys.stderr)
    out = []
    for kind, c, f in jobs:
        p = paths.get((kind, c['id']))
        if not p:
            continue
        try:
            r = audit(p, kind == 'mtn')
        except Exception as ex:
            r = dict(ok=False, why=[f'점검 실패 {ex}'])
        r.update(id=c['id'], kind=kind, name=c['name'], city=c.get('city'), lab=bool(c.get('lab')), file=f)
        out.append(r)
    json.dump(out, open(os.path.join(ROOT, 'data/route_3d_audit.json'), 'w'), ensure_ascii=False, indent=0)
    for kind in ('road', 'mtn'):
        a = [r for r in out if r['kind'] == kind and not r['lab']]
        print(kind, '오픈', len(a), '합격', sum(r['ok'] for r in a), '불합격', sum(not r['ok'] for r in a))


if __name__ == '__main__':
    main()
