#!/usr/bin/env python3
"""상림 영상 만들기 (윈도우·맥·리눅스 공통)

  python run.py <원본폴더> [--from 103944] [--to 111536] [--cut-head 0] [--cut-tail 0] [--skip-short 3]

1) 원본폴더의 20261121_HHMMSS.* 영상을 파일명(=찍은 시각) 순으로 정렬, 같은 이름 중복·3초 미만은 뺌
2) 영상마다 얼굴·번호판 흐림 (blur.py) → out/blur/  (중간에 끊겨도 다시 돌리면 이어서)
3) 하나로 잇기 → out/sangnim_joined.mp4 (1080 폭, 30fps, 소리 없음)
   --cut-head/--cut-tail 초: 전체 앞뒤 군더더기 자르기
4) out/timeline.json: 각 원본이 이은 영상의 몇 초에 들어갔는지 + 실제 시각 (GPS 시각과 맞추는 데 씀)
5) out/check/: 흐림이 애매했던 장면 사진 (사람이 눈으로 한 번 볼 곳)

처음 한 번: pip install opencv-python-headless onnxruntime open-image-models imageio-ffmpeg
(번호판 모델은 첫 실행 때 저절로 받음, 약 7MB)
"""
import sys, os, re, json, subprocess, argparse, glob

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import blur

def ff(): return blur.FFMPEG()

def dur(path):
    r = subprocess.run([ff(), '-i', path], capture_output=True, text=True)
    m = re.search(r'Duration: (\d+):(\d+):([\d.]+)', r.stderr)
    return int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3]) if m else 0.0

def main():
    a = argparse.ArgumentParser()
    a.add_argument('src'); a.add_argument('--out', default=os.path.join(HERE, 'out'))
    a.add_argument('--from', dest='t0', default='000000'); a.add_argument('--to', dest='t1', default='235959')
    a.add_argument('--cut-head', type=float, default=0); a.add_argument('--cut-tail', type=float, default=0)
    a.add_argument('--skip-short', type=float, default=3)
    o = a.parse_args()
    os.makedirs(os.path.join(o.out, 'blur'), exist_ok=True); os.makedirs(os.path.join(o.out, 'check'), exist_ok=True)
    seen, clips = set(), []
    for p in sorted(glob.glob(os.path.join(o.src, '*'))):
        m = re.search(r'(\d{8})_(\d{6})', os.path.basename(p))
        if not m or not p.lower().endswith(('.mp4', '.mov', '.m4v', '.mkv')): continue
        if m[2] in seen or not (o.t0 <= m[2] <= o.t1): continue
        d = dur(p)
        if d < o.skip_short: print('짧아서 뺌', os.path.basename(p), d); continue
        seen.add(m[2]); clips.append({'file': p, 'date': m[1], 'hms': m[2], 'dur': d})
    print(f'영상 {len(clips)}개, 합계 {sum(c["dur"] for c in clips)/60:.1f}분')
    lines, t, tl = [], 0.0, []
    for i, c in enumerate(clips):
        name = f'{i:02d}_{c["hms"]}'
        dst = os.path.join(o.out, 'blur', name + '.mp4'); rep = os.path.join(o.out, 'blur', name + '.json')
        if not (os.path.exists(dst) and os.path.exists(rep)):
            print(f'[{i+1}/{len(clips)}] 흐림 중', os.path.basename(c['file']), flush=True)
            blur.main(c['file'], dst + '.part.mp4', rep); os.replace(dst + '.part.mp4', dst)
        r = json.load(open(rep, encoding='utf-8'))
        d = dur(dst)
        hh, mm, ss = int(c['hms'][:2]), int(c['hms'][2:4]), int(c['hms'][4:])
        tl.append({'i': i, 'src': os.path.basename(c['file']), 'clock': f'{hh:02d}:{mm:02d}:{ss:02d}',
                   'start': round(t, 2), 'dur': round(d, 2), 'faces': r['faces'], 'plates': r['plates'], 'unsure': len(r['unsure'])})
        # 애매 장면 사진: 영상마다 최대 6장
        for u in r['unsure'][::max(1, len(r['unsure']) // 6)][:6]:
            subprocess.run([ff(), '-loglevel', 'error', '-y', '-ss', str(u['t']), '-i', dst, '-frames:v', '1', '-vf', 'scale=360:-2',
                            os.path.join(o.out, 'check', f'{name}_{u["t"]:07.1f}s_{u["kind"]}.jpg')])
        lines.append("file '" + dst.replace('\\', '/').replace("'", "'\\''") + "'"); t += d
    lst = os.path.join(o.out, 'list.txt'); open(lst, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    joined = os.path.join(o.out, 'sangnim_joined.mp4')
    cmd = [ff(), '-loglevel', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', lst]
    if o.cut_head or o.cut_tail:
        cmd += ['-ss', str(o.cut_head), '-t', str(max(1, t - o.cut_head - o.cut_tail)), '-c:v', 'libx264', '-crf', '21', '-preset', 'medium', '-pix_fmt', 'yuv420p']
    else:
        cmd += ['-c', 'copy']
    subprocess.run(cmd + ['-an', '-movflags', '+faststart', joined], check=True)
    json.dump({'cut_head': o.cut_head, 'total': round(t, 2), 'clips': tl}, open(os.path.join(o.out, 'timeline.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('끝:', joined, f'{dur(joined)/60:.1f}분', '· 흐린 얼굴', sum(c['faces'] for c in tl), '· 번호판', sum(c['plates'] for c in tl),
          '· 다시 볼 곳', sum(c['unsure'] for c in tl))

if __name__ == '__main__':
    main()
