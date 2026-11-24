# 11/24 보스 "갔던 길 되돌아오기·엉킴·중복 없는 코스만": 모든 코스 노선을 같은 잣대로 자동 점검
# 입력 data/course_dump.json (tools/course_dump.js) → 출력 data/route_audit.json + 표(화면)
# 잣대
#   되돌림 %  = 같은 길을 반대 방향으로 다시 지나는 길이 / 전체 (12m 안, 진행 방향 135° 이상 차이)
#   겹침 %    = 같은 길을 같은 방향으로 다시 지나는 길이 / 전체
#   교차      = 노선이 자기 자신을 가로지르는 곳 수 (겹치는 곳·순환 출발점 제외, 40m 안은 한 곳)
#   U턴       = 앞뒤 25m 진행 방향이 150° 넘게 꺾이는 곳 수
#   근거      = 공식 GPX(두루누비·산림청·지리산둘레길) / 보스 GPS / 지도 길찾기(지점 이어 붙임) / 손으로 찍은 점 / 없음
import json, math, sys, os
D = json.load(open(sys.argv[1] if len(sys.argv) > 1 else 'data/course_dump.json', encoding='utf-8'))
def hav(a, b):
    p = math.pi / 180; x = (b[1] - a[1]) * p * math.cos((a[0] + b[0]) / 2 * p); y = (b[0] - a[0]) * p
    return 6371000 * math.hypot(x, y)
def load(f):
    try:
        j = json.load(open(f, encoding='utf-8')); return [q[:2] for q in j['p']], j.get('src', '')
    except Exception: return None, ''
def resample(pts, step):
    lat0 = pts[0][0]; kx = 111320 * math.cos(lat0 * math.pi / 180); ky = 110540
    xy = [((q[1] - pts[0][1]) * kx, (q[0] - lat0) * ky) for q in pts]
    out = [xy[0]]; carry = 0.0; tot = 0.0
    for i in range(len(xy) - 1):
        a, b = xy[i], xy[i + 1]; d = math.hypot(b[0] - a[0], b[1] - a[1]); tot += d
        if d == 0: continue
        t = step - carry
        while t <= d:
            out.append((a[0] + (b[0] - a[0]) * t / d, a[1] + (b[1] - a[1]) * t / d)); t += step
        carry = d - (t - step)
    if math.hypot(out[-1][0] - xy[-1][0], out[-1][1] - xy[-1][1]) > step * 0.3: out.append(xy[-1])
    return out, tot
def head(s, i, w):
    a = s[max(0, i - w)]; b = s[min(len(s) - 1, i + w)]
    return math.atan2(b[1] - a[1], b[0] - a[0])
def angd(a, b):
    d = abs(a - b) % (2 * math.pi); return min(d, 2 * math.pi - d) * 180 / math.pi
def seg_x(p1, p2, p3, p4):
    d = (p2[0] - p1[0]) * (p4[1] - p3[1]) - (p2[1] - p1[1]) * (p4[0] - p3[0])
    if abs(d) < 1e-9: return False
    t = ((p3[0] - p1[0]) * (p4[1] - p3[1]) - (p3[1] - p1[1]) * (p4[0] - p3[0])) / d
    u = ((p3[0] - p1[0]) * (p2[1] - p1[1]) - (p3[1] - p1[1]) * (p2[0] - p1[0])) / d
    return 0 < t < 1 and 0 < u < 1
def audit(pts, loop):
    total = sum(hav(pts[i], pts[i + 1]) for i in range(len(pts) - 1))
    step = 5 if total < 30000 else (20 if total < 200000 else 100)
    s, tot = resample(pts, step); n = len(s); L = (n - 1) * step
    R = 12 if step <= 20 else 60; cell = R
    grid = {}
    for i, q in enumerate(s): grid.setdefault((int(q[0] // cell), int(q[1] // cell)), []).append(i)
    hw = max(1, int(15 / step))
    H = [head(s, i, hw) for i in range(n)]
    rev = [0] * n; same = [0] * n; gap = max(80, 4 * R)
    for i, q in enumerate(s):
        cx, cy = int(q[0] // cell), int(q[1] // cell)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for j in grid.get((cx + dx, cy + dy), ()):
                    ds = abs(i - j) * step
                    if loop: ds = min(ds, L - ds)
                    if ds < gap: continue
                    if math.hypot(s[j][0] - q[0], s[j][1] - q[1]) > R: continue
                    a = angd(H[i], H[j])
                    if a > 135: rev[i] = 1
                    elif a < 45: same[i] = 1
    # U턴
    w = max(1, int(25 / step)); ut = []
    for i in range(w, n - w):
        a = math.atan2(s[i][1] - s[i - w][1], s[i][0] - s[i - w][0]); b = math.atan2(s[i + w][1] - s[i][1], s[i + w][0] - s[i][0])
        if angd(a, b) > 150 and (not ut or (i - ut[-1]) * step > 60): ut.append(i)
    # 자기 교차 (5m 점이면 너무 많아 20m 간격으로)
    k = max(1, int(20 / step)); t = s[::k]
    if loop and t[-1] != s[-1]: t = t + [s[-1]]
    m = len(t); cs = 20 * k / k * 2; g2 = {}
    for i in range(m - 1):
        x0, x1 = sorted((t[i][0], t[i + 1][0])); y0, y1 = sorted((t[i][1], t[i + 1][1]))
        for gx in range(int(x0 // 40), int(x1 // 40) + 1):
            for gy in range(int(y0 // 40), int(y1 // 40) + 1): g2.setdefault((gx, gy), set()).add(i)
    xs = []; seen = set(); st = step * k
    for cellset in g2.values():
        cl = sorted(cellset)
        for ai in range(len(cl)):
            for bi in range(ai + 1, len(cl)):
                i, j = cl[ai], cl[bi]
                if (i, j) in seen: continue
                seen.add((i, j)); ds = (j - i) * st
                if loop: ds = min(ds, (m - 1) * st - ds)
                if ds < 60: continue
                if seg_x(t[i], t[i + 1], t[j], t[j + 1]):
                    ii, jj = min(n - 1, i * k), min(n - 1, j * k)
                    if rev[ii] or rev[jj] or same[ii] or same[jj]: continue   # 겹치는 길 위 교차는 되돌림으로 셈
                    xs.append(t[i])
    cx = []
    for p in xs:
        if all(math.hypot(p[0] - c[0], p[1] - c[1]) > 40 for c in cx): cx.append(p)
    close = hav(pts[0], pts[-1])
    return { 'km': round(total / 1000, 2), 'rev': round(100 * sum(rev) / n, 1), 'same': round(100 * sum(same) / n, 1),
             'cross': len(cx), 'uturn': len(ut), 'gap_m': round(close) }
def grade(r):
    rv, sm, cr, ut = r['rev'], r['same'], r['cross'], r['uturn']
    bad = rv + sm
    if bad <= 3 and cr <= 1 and ut <= 1: return '통과'
    if bad <= 10 and cr <= 3 and ut <= 3: return '경계'
    return '불량'
rows = []
for c in D['roads']:
    f = c['official']; pts = None; src = ''
    if f: pts, src = load(f)
    if not pts and c['path']: pts, src = c['path'], '손으로 찍은 점'
    if not pts: rows.append({ 'type': 'road', 'id': c['id'], 'city': c['city'], 'name': c['name'], 'kind': c['kind'], 'loop': c['loop'], 'lab': c['lab'], 'src': '없음', 'grade': '자료 없음' }); continue
    if c['loop'] and hav(pts[0], pts[-1]) > 30: pts = pts + [pts[0]]
    r = audit(pts, c['loop']); r.update({ 'type': 'road', 'id': c['id'], 'city': c['city'], 'name': c['name'], 'kind': c['kind'], 'loop': c['loop'], 'lab': c['lab'], 'src': src, 'L': c['L'] })
    r['grade'] = grade(r); rows.append(r)
for m in D['mtns']:
    if not m['geo']: rows.append({ 'type': 'mtn', 'id': m['id'], 'city': m['city'], 'name': m['name'], 'lab': m['lab'], 'src': '없음', 'grade': '자료 없음' }); continue
    pts, src = load(m['geo'])
    r = audit(pts, False); r.update({ 'type': 'mtn', 'id': m['id'], 'city': m['city'], 'name': m['name'], 'trail': m['trail'], 'lab': m['lab'], 'src': src })
    r['grade'] = grade(r); rows.append(r)
json.dump(rows, open('data/route_audit.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
for r in rows:
    if r.get('km') is None: print('%-22s %-6s %s' % (r['id'], r['grade'], r['name'])); continue
    print('%-22s %-5s 되돌림%5.1f 겹침%5.1f 교차%3d U턴%3d %6.2fkm %s %s | %s' % (r['id'], r['grade'], r['rev'], r['same'], r['cross'], r['uturn'], r['km'], 'LAB' if r['lab'] else '   ', r['name'], r['src'][:20]))
