# 거점 보강 후보 찾기 (2026-11-22 보스 "거점보강. 근처라도 거점이 있다면 안내")
#   거점 사이가 먼 코스의 실제 노선(data/route, data/jiri) 양옆 1.5km 안에서
#   오픈스트리트맵(Overpass)의 이름 있는 명소를 모아 data/hub_probe.json 에 저장
#   각 후보: [이름, 노선 위치 m, 길에서 떨어진 거리 m, 종류, 위키 연결 여부, 위도, 경도]
#   앱에 넣는 것은 사람이(아미) 후보를 보고 고른 뒤 index.html 에 직접 — 이 도구는 앱을 바꾸지 않음
import json, math, time, urllib.parse, urllib.request

TARGETS = {
    'seomjin-bike': 'data/route/seomjin-bike.json', 'tapjeong-gil': 'data/route/tapjeong-gil.json',
    'dalseong-bike': 'data/route/dalseong-bike.json', 'gyeongchun-bike-24k': 'data/route/gyeongchun-bike-24k.json',
    'tangeum-bike': 'data/route/tangeum-bike.json', 'daecheong-bike': 'data/route/daecheong-bike.json',
    'geumgang-bike': 'data/route/geumgang-bike.json', 'namhangang-bike': 'data/route/namhangang-bike.json',
    'yeongsan-bike': 'data/route/yeongsan-bike.json', 'nakdong-bike-18k': 'data/route/nakdong-bike-18k.json',
    'woljeongsa-gil': 'data/route/woljeongsa-gil.json', 'giheung-gil': 'data/route/giheung-gil.json',
    'sorigil-gil': 'data/route/sorigil-gil.json', 'dulle-all-44k': 'data/jiri/c345.json',
    'olle7-18k': 'data/route/olle7-18k.json',
}
R = 1500
UA = {'User-Agent': 'bangguseok-runner hub probe (re2.jjay@gmail.com)'}
OVP = ('https://overpass-api.de/api/interpreter', 'https://overpass.private.coffee/api/interpreter',
       'https://overpass.kumi.systems/api/interpreter', 'https://maps.mail.ru/osm/tools/overpass/api/interpreter')
KEYS = [('tourism', 'attraction|viewpoint|museum|gallery|theme_park|zoo|aquarium'), ('historic', '.'),
        ('leisure', 'park|nature_reserve'), ('natural', 'peak|waterfall|beach|cape'), ('railway', 'station'),
        ('amenity', 'place_of_worship'), ('man_made', 'bridge|lighthouse|tower|dam'), ('waterway', 'dam|weir'),
        ('boundary', 'national_park')]


def hav(a, b):
    p = math.pi / 180; dl = (b[0] - a[0]) * p; dn = (b[1] - a[1]) * p
    h = math.sin(dl / 2) ** 2 + math.cos(a[0] * p) * math.cos(b[0] * p) * math.sin(dn / 2) ** 2
    return 6371000 * 2 * math.asin(math.sqrt(h))


def overpass(ql):   # 11/22 2판: 서버마다 한 번씩 · 60초 (첫 판은 실패 때 재시도가 길어 35분 넘게 걸림)
    for k in range(2):
        for host in OVP:
            try:
                req = urllib.request.Request(host, data=urllib.parse.urlencode({'data': ql}).encode(), headers=UA)
                with urllib.request.urlopen(req, timeout=75) as r: return json.load(r)
            except Exception as e: print('  overpass 실패', host[8:30], str(e)[:80], flush=True)
            time.sleep(2)
        time.sleep(8)
    return None


out = {}
for cid, f in TARGETS.items():
    o = json.load(open(f, encoding='utf-8')); co = o['p']
    cum = [0.0]
    for i in range(1, len(co)): cum.append(cum[-1] + hav(co[i - 1], co[i]))
    # 300m 마다 한 점 → around 선(폴리라인)
    line = [co[0]]; last = 0
    for i in range(1, len(co)):
        if cum[i] - last >= 300: line.append(co[i]); last = cum[i]
    line.append(co[-1])
    # 2판: 긴 선(around) 대신 노선을 감싼 네모(bbox)로 가볍게 받고, 1.5km 안인지는 여기서 거름
    la0 = min(a for a, b in co) - 0.015; la1 = max(a for a, b in co) + 0.015
    lo0 = min(b for a, b in co) - 0.018; lo1 = max(b for a, b in co) + 0.018
    bb = '%.4f,%.4f,%.4f,%.4f' % (la0, lo0, la1, lo1)
    q = '[out:json][timeout:60];(' + ''.join('nwr(%s)["name"]["%s"~"^(%s)$"];' % (bb, k, v) for k, v in KEYS) + ');out center tags;'
    j = overpass(q); res = []
    if j is None: out[cid] = {'err': 'overpass 실패'}; print(cid, '실패', flush=True); continue
    seen = set()
    for el in j.get('elements', []):
        t = el.get('tags') or {}; nm = t.get('name:ko') or t.get('name')
        if not nm or nm in seen: continue
        la = el.get('lat') or (el.get('center') or {}).get('lat'); lo = el.get('lon') or (el.get('center') or {}).get('lon')
        if la is None: continue
        i = min(range(len(co)), key=lambda i: hav(co[i], [la, lo])); off = hav(co[i], [la, lo])
        if off > R: continue
        kind = next(('%s=%s' % (k, t[k]) for k, _ in KEYS if k in t), '')
        wiki = 1 if ('wikidata' in t or 'wikipedia' in t) else 0
        seen.add(nm); res.append([nm, round(cum[i]), round(off), kind, wiki, round(la, 6), round(lo, 6)])
    res.sort(key=lambda r: r[1])
    out[cid] = {'len': round(cum[-1]), 'n': len(res), 'c': res}
    print(cid, round(cum[-1]), '후보', len(res), flush=True)
    json.dump(out, open('data/hub_probe.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=0)   # 하나 끝날 때마다 저장
    time.sleep(5)
json.dump(out, open('data/hub_probe.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
