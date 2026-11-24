# 11/24 노선 점검: 두루누비 GPX 중 같은 코스가 두 번 들어 있는 파일(트랙 2개) → 첫 트랙만 남김
#   · 코스 파일 data/kt/seg/<id>.json → data/kt/seg/<id>-v2.json (이름을 바꿔야 폰이 새로 받음)
#   · 장거리 파일 haeparang/nampa/seohae.json → *2.json (되돌아가 같은 길을 다시 그린 부분만 뺌)
import json, math, glob, os
def hav(a, b):
    p = math.pi / 180; x = (b[1] - a[1]) * p * math.cos((a[0] + b[0]) / 2 * p); y = (b[0] - a[0]) * p
    return 6371000 * math.hypot(x, y)
def segd(q, a, b):
    k = math.cos(a[0] * math.pi / 180); ax, ay, bx, by, px, py = a[1] * k, a[0], b[1] * k, b[0], q[1] * k, q[0]
    dd = (bx - ax) ** 2 + (by - ay) ** 2
    t = 0 if dd == 0 else max(0, min(1, ((px - ax) * (bx - ax) + (py - ay) * (by - ay)) / dd))
    return hav(q, [ay + (by - ay) * t, (ax + (bx - ax) * t) / k])
def dline(q, P): return min(segd(q, P[i], P[i + 1]) for i in range(len(P) - 1))
def L(p): return sum(hav(p[i], p[i + 1]) for i in range(len(p) - 1))
fixed = {}; DUP = {}
for f in sorted(glob.glob('data/kt/seg/*.json')):
    if f.endswith('-v2.json') or os.path.basename(f).startswith('_'): continue
    d = json.load(open(f)); p = d['p']
    jumps = [i for i in range(len(p) - 1) if hav(p[i], p[i + 1]) > 2000]
    if not jumps: continue
    js = [j for j in jumps if hav(p[j + 1], p[0]) < 300]      # 코스 처음으로 되돌아가는 점프만
    if not js: continue
    j = js[0]; A = p[:j + 1]; B = p[j + 1:]
    onA = sum(1 for q in B if dline(q, A) < 50) / len(B)
    if onA < 0.65: print('  건너뜀', f, round(onA, 2)); continue
    sid = os.path.basename(f)[:-5]; out = dict(d); out['p'] = A; out['km'] = round(L(A) / 1000, 2)
    out['fix'] = '11/24 같은 코스가 두 번 들어 있던 GPX → 첫 트랙만 (원래 %.1fkm)' % (L(p) / 1000)
    json.dump(out, open('data/kt/seg/%s-v2.json' % sid, 'w'), separators=(',', ':'), ensure_ascii=False)
    fixed[sid] = round(L(A)); DUP[sid] = (A[0], A[-1], L(B))
    print(sid, '%.1f → %.1f km' % (L(p) / 1000, L(A) / 1000), '겹침 %.0f%%' % (onA * 100))
for nm in ['haeparang', 'nampa', 'seohae']:   # 장거리 = 코스 파일을 이어 붙인 것 → 위에서 찾은 '두 번째 트랙'만 정확히 뺌
    d = json.load(open('data/kt/%s.json' % nm)); p = d['p']; keep = []; i = 0; cut = 0
    while i < len(p):
        keep.append(p[i])
        if i + 1 < len(p) and hav(p[i], p[i + 1]) > 2000:
            hit = None
            for sid, (a0, a1, lb) in DUP.items():
                if hav(p[i], a1) < 300 and hav(p[i + 1], a0) < 300: hit = lb; break
            if hit:
                k = i + 1; run = 0.0
                while k + 1 < len(p) and not (run > hit * 0.7 and hav(p[k], p[i]) < 200): run += hav(p[k], p[k + 1]); k += 1
                if run < hit * 1.4: cut += k - (i + 1); print("   뺌 %.1fkm (두번째 트랙 %.1fkm)" % (run / 1000, hit / 1000)); i = k; continue
        i += 1
    out = dict(d); out['p'] = keep
    json.dump(out, open('data/kt/%s2.json' % nm, 'w'), separators=(',', ':'), ensure_ascii=False)
    print(nm, '%.0f → %.0f km' % (L(p) / 1000, L(keep) / 1000), '뺀 점', cut)
json.dump(fixed, open('data/kt/seg/_fixed_1124.json', 'w'))
