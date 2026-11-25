#!/usr/bin/env python3
"""얼굴·번호판 흐림.  python3 -I blur.py 입력.mp4 출력.mp4 [보고.json]
- 얼굴: OpenCV YuNet (models/yunet.onnx), 번호판: open-image-models YOLOv9 번호판 모델
- 놓침 줄이기: 낮은 기준값 + 찾은 상자를 앞뒤 HOLD 프레임 유지(깜빡임 방지) + 상자 넓게
- 보고: 프레임별 찾은 개수, '애매한(기준 근처)' 장면 시각 목록 → 사람이 다시 볼 곳
- 출력: 1080 폭 세로 기준 그대로 비율 유지, 30fps, 소리 없음(행인 목소리 보호)
"""
import sys, json, subprocess, os, collections
import cv2, numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
def FFMPEG():
    try:
        import imageio_ffmpeg; return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return 'ffmpeg'
FACE_T, FACE_LOW = 0.55, 0.35     # 흐림 기준 / 애매 표시 기준
PLATE_T, PLATE_LOW = 0.30, 0.15
HOLD = 8                          # 찾은 상자를 앞뒤 몇 프레임 더 흐릴지
PAD = 0.35                        # 상자 넓히는 비율

def main(src, dst, rep=None):
    import warnings; warnings.filterwarnings('ignore')
    from open_image_models import LicensePlateDetector
    plate = LicensePlateDetector(detection_model='yolo-v9-t-384-license-plate-end2end', conf_thresh=PLATE_LOW)
    cap = cv2.VideoCapture(src)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    W, H = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    s = 1080 / min(W, H) if min(W, H) > 1080 else 1.0
    ow, oh = int(round(W * s / 2) * 2), int(round(H * s / 2) * 2)
    face = cv2.FaceDetectorYN.create(os.path.join(HERE, 'models/yunet.onnx'), '', (ow, oh), FACE_LOW, 0.3, 5000)
    ff = subprocess.Popen([FFMPEG(), '-loglevel', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{ow}x{oh}',
                           '-r', str(fps), '-i', '-', '-vf', 'fps=30', '-an', '-c:v', 'libx264', '-preset', 'medium', '-crf', '21',
                           '-pix_fmt', 'yuv420p', '-movflags', '+faststart', dst], stdin=subprocess.PIPE)
    buf = collections.deque()   # (frame, boxes) 지연 버퍼: 앞 프레임에도 뒤에서 찾은 상자 적용
    log, unsure = [], []
    i = 0
    def flush(force=False):
        while buf and (force or len(buf) > HOLD):
            fr, _ = buf[0]
            boxes = [b for _, bx in list(buf)[:HOLD + 1] for b in bx]
            for x, y, w, h in boxes:
                x0, y0 = max(0, int(x - w * PAD)), max(0, int(y - h * PAD))
                x1, y1 = min(ow, int(x + w * (1 + PAD))), min(oh, int(y + h * (1 + PAD)))
                if x1 > x0 and y1 > y0:
                    roi = fr[y0:y1, x0:x1]
                    k = max(15, (max(x1 - x0, y1 - y0) // 3) | 1)
                    fr[y0:y1, x0:x1] = cv2.GaussianBlur(cv2.resize(cv2.resize(roi, (8, 8)), (x1 - x0, y1 - y0)), (k, k), 0)
            ff.stdin.write(fr.tobytes()); buf.popleft()
    recent = collections.deque(maxlen=HOLD)  # 뒤쪽 HOLD 유지용
    while True:
        ok, fr = cap.read()
        if not ok: break
        if s != 1.0: fr = cv2.resize(fr, (ow, oh), interpolation=cv2.INTER_AREA)
        bx, nf, npl = [], 0, 0
        _, F = face.detect(fr)
        for f in (F if F is not None else np.zeros((0, 15))):
            c = float(f[-1])
            if c >= FACE_T: bx.append(tuple(f[:4])); nf += 1
            else: unsure.append({'t': round(i / fps, 1), 'kind': 'face', 'conf': round(c, 2)})
        for d in plate.predict(fr):
            b, c = d.bounding_box, float(d.confidence)
            if c >= PLATE_T: bx.append((b.x1, b.y1, b.x2 - b.x1, b.y2 - b.y1)); npl += 1
            else: unsure.append({'t': round(i / fps, 1), 'kind': 'plate', 'conf': round(c, 2)})
        cur = bx + [b for r in recent for b in r]
        recent.append(bx)
        buf.append((fr, cur)); flush()
        if nf or npl: log.append({'t': round(i / fps, 2), 'face': nf, 'plate': npl})
        i += 1
    flush(True); ff.stdin.close(); ff.wait(); cap.release()
    out = {'src': os.path.basename(src), 'frames': i, 'fps': fps, 'blurred_frames': len(log),
           'faces': sum(l['face'] for l in log), 'plates': sum(l['plate'] for l in log), 'unsure': unsure, 'hits': log}
    if rep: json.dump(out, open(rep, 'w'), ensure_ascii=False)
    print(json.dumps({k: v for k, v in out.items() if k not in ('hits', 'unsure')} | {'unsure': len(unsure)}, ensure_ascii=False))

if __name__ == '__main__':
    main(*sys.argv[1:4])
