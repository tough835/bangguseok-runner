#!/usr/bin/env python3
"""11/27 보스 "사용자가 앱 보고 실제로 가니까 검증되고 확실한 것만 오픈, 애매하면 실험실" — 코스별 검증 판정.

오픈 조건 (전부 만족해야 오픈):
  ① 노선 근거 = 공식 GPX(두루누비 코리아둘레길 · 지리산둘레길 · 산림청 100대명산) 또는 보스 현장 GPS
     (지도 길찾기로 점을 이어 만든 노선은 '공식 아님' → 실험실)
  ② 되돌림·엉킴 점검(tools/route_audit.py) '통과'
  ③ 그림 지도(오픈스트리트맵) 대조(tools/route_osm_local.py → data/route_osm_probe.json):
     길 밖(30m 안에 길 없음) ≤ 5% · 자전거 코스 산길 ≤ 3% · 찻길 ≤ 40%(탑정호 찻길은 보스 지시 예외)
     대조 결과가 없으면 '미확인' → 실험실. 보스 현장 GPS는 현장 확인이라 ③ 생략
입력: data/course_dump.json · data/route_audit.json · data/route_osm_probe.json
출력: data/course_verify.json · 표(md, 인자로 경로) · index.html VERIFY_LAB 줄 교체(--apply)
"""
import json, sys, re

d = json.load(open('data/course_dump.json', encoding='utf-8'))
P = json.load(open('data/route_osm_probe.json', encoding='utf-8'))
A = {a['id']: a for a in json.load(open('data/route_audit.json', encoding='utf-8'))}


def basis(src):
    if '보스 GPS' in src: return 'gps', '보스 현장 GPS'
    for k in ('두루누비', '지리산둘레길 공식', '산림청 100대명산'):
        if k in src: return 'official', src
    return None, src


rows = []
for kind, lst, fk in (('길', d['roads'], 'official'), ('산', d['mtns'], 'geo')):
    for c in lst:
        if not c.get(fk): continue
        src = json.load(open(c[fk], encoding='utf-8')).get('src', '')
        b, bs = basis(src); a = A.get(c['id'], {}); p = P.get(c['id'])
        why = []
        if not b: why.append('공식 노선 아님(지도 길찾기로 이은 노선)')
        if a.get('grade') != '통과': why.append('되돌림·엉킴 ' + str(a.get('grade') or '점검 없음'))
        bike = '자전거' in (c.get('kind') or '')
        if b != 'gps':
            if not p or 'err' in p: why.append('그림 지도 대조 미확인')
            else:
                if p['off'] > 5: why.append(f"길 밖 {p['off']}%")
                if kind == '길' and bike and p['trail'] > 3: why.append(f"자전거 코스에 산길 {p['trail']}%")
                if kind == '길' and p['car'] > 40 and c['id'] != 'tapjeong-road': why.append(f"찻길 {p['car']}%")
        rows.append(dict(kind=kind, id=c['id'], name=c['name'], basis=bs, audit=a.get('grade'),
                         probe=None if not p or 'err' in p else {k: p[k] for k in ('off', 'trail', 'car')},
                         ok=not why, why=why, routeLab=bool(c['lab'])))

json.dump(rows, open('data/course_verify.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
# 판정 대상 = 기존 ROUTE_LAB 등으로 이미 실험실인 코스는 제외(그대로 실험실)
VER = [r for r in rows if not r['routeLab']]
lab = sorted(r['id'] for r in VER if not r['ok'])
for k in ('길', '산'):
    v = [r for r in VER if r['kind'] == k]
    print(k, '대상', len(v), '오픈', sum(r['ok'] for r in v), '실험실', sum(not r['ok'] for r in v))

if len(sys.argv) > 1 and sys.argv[1].endswith('.md'):
    L = ['# 코스 검증표 (2026-11-27)', '', '오픈 조건: ① 공식 GPX 또는 보스 현장 GPS ② 되돌림·엉킴 통과 ③ 그림 지도(오픈스트리트맵) 위 실제 길 — 길 밖 5% 이하 · 자전거 산길 3% 이하 · 찻길 40% 이하. 하나라도 애매·미확인이면 실험실.', '']
    for k in ('길', '산'):
        v = [r for r in VER if r['kind'] == k]
        L += [f'## {k} 코스 — 오픈 {sum(r["ok"] for r in v)} / 실험실 {sum(not r["ok"] for r in v)}', '', '| 판정 | 코스 | 노선 근거 | 길 밖·산길·찻길 % | 빠진 이유 |', '|---|---|---|---|---|']
        for r in sorted(v, key=lambda r: (not r['ok'], r['id'])):
            pr = r['probe']; ps = f"{pr['off']} · {pr['trail']} · {pr['car']}" if pr else '—'
            L.append(f"| {'✅ 오픈' if r['ok'] else '🧪 실험실'} | {r['name']} (`{r['id']}`) | {r['basis'][:40]} | {ps} | {' / '.join(r['why'])} |")
        L.append('')
    open(sys.argv[1], 'w', encoding='utf-8').write('\n'.join(L))

if '--apply' in sys.argv:
    s = open('index.html', encoding='utf-8').read()
    roads = sorted(r['id'] for r in VER if not r['ok'] and r['kind'] == '길')
    mtns = sorted(r['id'] for r in VER if not r['ok'] and r['kind'] == '산')
    new = 'const VERIFY_LAB = new Set(' + json.dumps(roads, ensure_ascii=False) + '); const VERIFY_LAB_MTN = new Set(' + json.dumps(mtns, ensure_ascii=False) + ');'
    s2, n = re.subn(r'const VERIFY_LAB = new Set\(.*?\); const VERIFY_LAB_MTN = new Set\(.*?\);', lambda m: new, s, count=1)
    assert n == 1, 'VERIFY_LAB 줄을 못 찾음'
    open('index.html', 'w', encoding='utf-8').write(s2)
    print('index.html VERIFY_LAB 갱신', len(roads), len(mtns))
