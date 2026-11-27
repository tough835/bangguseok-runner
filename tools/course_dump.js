// 11/24 코스 노선 점검용: 앱(index.html)을 띄워 모든 길·산 코스의 노선 출처를 뽑음 → data/course_dump.json
// 쓰는 법: (저장소 폴더에서) python3 -m http.server 8765 & node tools/course_dump.js
const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch(); const p = await b.newPage({ locale: 'ko-KR' });
  await p.goto('http://localhost:8765/index.html'); await p.waitForTimeout(2500);
  const out = await p.evaluate(() => ({
    roads: Object.values(ALL_ROADS).map(c => ({ id: c.id, city: c.cityId, name: tr(c.name), kind: c.kind, L: c.lengthM, loop: !!c.loop,
      official: c.official || null, path: c.path || null, long: !!c.long, lab: (o => { c.vlab = false; const r = roadLab(c); c.vlab = o; return r; })(c.vlab),   /* 11/27 VERIFY_LAB(검증 미확인)은 빼고 셈 → 검증되면 다시 오픈 판정 */ source: c.source || '', note: tr(c.note) })),
    mtns: TARGETS.filter(t => t.kind === 'mountain').map(t => ({ id: t.id, city: t.cityId, name: tr(t.name), geo: t.geo || null, lab: (o => { t.vlab = false; const r = mtnLab(t); t.vlab = o; return r; })(t.vlab), trail: tr(t.trail), summit: t.summit, peak: t.peak || null }))
  }));
  require('fs').writeFileSync(process.argv[2] || 'data/course_dump.json', JSON.stringify(out));
  console.log('길', out.roads.length, '산', out.mtns.length);
  await b.close();
})();
