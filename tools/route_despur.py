# 11/24 노선 점검: 길 찾기가 지점(명소)에 닿으려고 들어갔다 같은 길로 나온 '곁가지'를 잘라냄
#   · 곁가지 = 반환점(U턴)을 사이에 두고 앞뒤 점이 12m 안에서 거울처럼 겹치는 구간
#   · 순환 코스는 출발점이 곁가지 끝에 있으면(처음·끝이 겹침) 그 부분도 잘라 출발점을 본 길 위로 옮김
#   · 결과 data/route/<id>-v2.json (이름을 바꿔야 폰이 새로 받음) · 원본 파일은 그대로 둠 (되돌리기 쉬움)
# 쓰는 법: python3 tools/route_despur.py id1 id2 ...
import json, math, sys
def hav(a, b):
    p = math.pi / 180; x = (b[1] - a[1]) * p * math.cos((a[0] + b[0]) / 2 * p); y = (b[0] - a[0]) * p
    return 6371000 * math.hypot(x, y)
def dense(p, step=5):
    out = [p[0]]
    for i in range(len(p) - 1):
        a, b = p[i], p[i + 1]; d = hav(a, b); n = max(1, int(d // step))
        for k in range(1, n + 1): out.append([a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n])
    return out
def despur(p, loop, tol=12, minlen=20):
    q = dense(p); cut = []
    changed = True
    while changed:
        changed = False; n = len(q)
        if loop:   # 출발점이 곁가지 위
            k = 0
            while k < n // 2 - 2 and hav(q[k], q[n - 1 - k]) < tol: k += 1
            k -= 1
            if k * 5 >= minlen:
                # q[k] 와 q[n-1-k] 가 같은 곳 → 그 사이만 남김
                cut.append(('출발 곁가지', round(k * 5)))
                q = q[k:n - k]; changed = True; continue
        best = None
        for u in range(2, n - 2):
            k = 1
            while u - k >= 0 and u + k < n and hav(q[u - k], q[u + k]) < tol: k += 1
            k -= 1
            if k * 5 >= minlen and (best is None or k > best[1]): best = (u, k)
        if best:
            u, k = best; cut.append(('곁가지', round(k * 5), round(u * 5)))
            q = q[:u - k] + q[u + k:]; changed = True
    return q, cut
def simplify(pts, tol=2.0):
    if len(pts) < 3: return pts
    def sd(p, a, b):
        k = math.cos(a[0] * math.pi / 180); ax, ay, bx, by, px, py = a[1] * k, a[0], b[1] * k, b[0], p[1] * k, p[0]
        dd = (bx - ax) ** 2 + (by - ay) ** 2
        t = 0 if dd == 0 else max(0, min(1, ((px - ax) * (bx - ax) + (py - ay) * (by - ay)) / dd))
        return hav(p, [ay + (by - ay) * t, (ax + (bx - ax) * t) / k])
    keep = [False] * len(pts); keep[0] = keep[-1] = True; st = [(0, len(pts) - 1)]
    while st:
        i, j = st.pop(); best, bi = 0, -1
        for k in range(i + 1, j):
            d = sd(pts[k], pts[i], pts[j])
            if d > best: best, bi = d, k
        if best > tol: keep[bi] = True; st += [(i, bi), (bi, j)]
    return [[round(a, 6), round(b, 6)] for (a, b), kk in zip(pts, keep) if kk]
D = {c['id']: c for c in json.load(open('data/course_dump.json', encoding='utf-8'))['roads']}
for cid in sys.argv[1:]:
    c = D[cid]; f = c['official']; d = json.load(open(f, encoding='utf-8')); p = [x[:2] for x in d['p']]
    if c['loop'] and hav(p[0], p[-1]) > 30: p = p + [p[0]]
    q, cut = despur(p, c['loop']); q = simplify(q)
    L0 = sum(hav(p[i], p[i + 1]) for i in range(len(p) - 1)); L1 = sum(hav(q[i], q[i + 1]) for i in range(len(q) - 1))
    out = { 'p': q, 'km': round(L1 / 1000, 2), 'how': d.get('how', ''), 'src': d.get('src', ''), 'fix': '11/24 곁가지 정리 %s (원래 %.2fkm)' % (cut, L0 / 1000) }
    if 'elev' in d: out['elev'] = d['elev']
    nf = f[:-5] + '-v2.json'; json.dump(out, open(nf, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print(cid, '%.2f → %.2f km' % (L0 / 1000, L1 / 1000), '코스 %.2f' % (c['L'] / 1000), cut, '→', nf)
