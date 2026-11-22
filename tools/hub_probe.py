# 거점 보강 후보 찾기 (2026-11-22 보스 "거점보강. 근처라도 거점이 있다면 안내")
#   거점 사이가 먼 코스의 실제 노선(data/route, data/jiri) 양옆 1.5km 안에서
#   오픈스트리트맵(Overpass)의 이름 있는 명소를 모아 data/hub_probe2.json 에 저장
#   각 후보: [이름, 노선 위치 m, 길에서 떨어진 거리 m, 종류, 위키 연결 여부, 위도, 경도]
#   앱에 넣는 것은 사람이(아미) 후보를 보고 고른 뒤 index.html 에 직접 — 이 도구는 앱을 바꾸지 않음
import json, math, time, urllib.parse, urllib.request

# 11/22 3판: 자전거 길(평지)에서 산 이름 거점을 빼고 대신 넣을 곳 — 마을·다리·보·쉼터·역 (길에서 600m 안) + 이름으로 찾기(Nominatim)
TARGETS = {
    'seomjin-bike': 'data/route/seomjin-bike.json', 'dalseong-bike': 'data/route/dalseong-bike.json',
    'daecheong-bike': 'data/route/daecheong-bike.json', 'tapjeong-gil': 'data/route/tapjeong-gil.json',
}
NAMES = {
    'seomjin-bike': ['김용택 시인 생가', '진메마을', '천담마을', '구담마을', '섬진강댐 물문화관', '장군목 현수교', '섬진강 마실휴양숙박시설', '덕치면사무소', '강진교 임실', '적성교 순창', '화탄 세월교', '어은정', '섬진강 향가터널'],
    'dalseong-bike': ['달성습지', '화원유원지', '사문진 나루터', '달성노을공원', '논공읍행정복지센터', '옥포읍행정복지센터', '위천삼거리', '성산대교', '고령교', '박석진교'],
    'daecheong-bike': ['대청공원', '대청댐 물문화관', '금강로하스대청공원', '로하스가족공원워터캠핑장', '신탄진대교', '현도교', '대덕테크노밸리', '갑천 불무교', '한빛대교', '갑천대교', '봉산동 구즉'],
    'tapjeong-gil': ['탑정호 출렁다리', '탑정호 음악분수', '논산 탑정리 석탑', '병암유원지', '계백장군유적지', '탑정호 소풍길', '가야곡면행정복지센터', '신풍리근린공원'],
}
R = 600
UA = {'User-Agent': 'bangguseok-runner hub probe (re2.jjay@gmail.com)'}
OVP = ('https://overpass-api.de/api/interpreter', 'https://overpass.private.coffee/api/interpreter',
       'https://overpass.kumi.systems/api/interpreter', 'https://maps.mail.ru/osm/tools/overpass/api/interpreter')
KEYS = [('place', 'village|hamlet|neighbourhood'), ('man_made', 'bridge'), ('bridge', 'yes'), ('waterway', 'dam|weir'), ('railway', 'station|halt'),
        ('tourism', 'attraction|viewpoint|museum|information|picnic_site|camp_site'), ('historic', '.'), ('leisure', 'park'), ('amenity', 'shelter|ferry_terminal|townhall'), ('highway', 'rest_area')]


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
    json.dump(out, open('data/hub_probe2.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=0)   # 하나 끝날 때마다 저장
    time.sleep(5)
json.dump(out, open('data/hub_probe2.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=0)

# 이름으로 찾기 (Nominatim, 1초에 한 번) — 노선에서 2km 안인 것만
for cid, names in NAMES.items():
    o = json.load(open(TARGETS[cid], encoding='utf-8')); co = o['p']
    cum = [0.0]
    for i in range(1, len(co)): cum.append(cum[-1] + hav(co[i - 1], co[i]))
    la0 = min(a for a, b in co) - 0.03; la1 = max(a for a, b in co) + 0.03; lo0 = min(b for a, b in co) - 0.04; lo1 = max(b for a, b in co) + 0.04
    res = []
    for nm in names:
        u = 'https://nominatim.openstreetmap.org/search?' + urllib.parse.urlencode({'q': nm, 'format': 'json', 'limit': 5, 'accept-language': 'ko', 'viewbox': '%f,%f,%f,%f' % (lo0, la1, lo1, la0), 'bounded': 1})
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=40) as r: js = json.load(r)
        except Exception as e: print('  nominatim 실패', nm, str(e)[:60], flush=True); js = []
        for it in js[:2]:
            la, lo = float(it['lat']), float(it['lon'])
            i = min(range(len(co)), key=lambda i: hav(co[i], [la, lo])); off = hav(co[i], [la, lo])
            if off <= 2000: res.append([nm, round(cum[i]), round(off), it.get('display_name', '')[:60], round(la, 6), round(lo, 6)])
        time.sleep(1.2)
    out.setdefault(cid, {})['named'] = res
    print(cid, '이름 찾기', len(res), flush=True)
json.dump(out, open('data/hub_probe2.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
