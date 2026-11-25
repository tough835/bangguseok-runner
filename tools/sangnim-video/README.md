# 상림 영상 만들기 (보스 컴퓨터용)

액션캠 원본(20261121_HHMMSS.mp4)을 시간순으로 잇고, 행인 얼굴·차 번호판을 흐리고, 1080 폭 30fps 한 편으로 만든다.

## 1. 준비 (처음 한 번, 윈도우·맥 같음)

```
python -m pip install opencv-python-headless onnxruntime open-image-models imageio-ffmpeg
```

- 파이썬 3.9 이상. ffmpeg는 따로 안 깔아도 됨(imageio-ffmpeg가 들고 옴)
- 번호판 모델(약 7MB)은 첫 실행 때 저절로 받음

## 2. 실행

```
python run.py "<원본 폴더>"
```

- 윈도우 예: `python run.py "D:\액션캠\20261121"`
- 맥 예: `python3 run.py ~/Movies/액션캠/20261121`
- 3초 미만 영상, 같은 시각 중복은 저절로 뺌
- 앞뒤 자르기: `--cut-head 5 --cut-tail 8` (초)
- 시간 범위만: `--from 103944 --to 111536`
- 중간에 꺼져도 다시 같은 명령 → 끝난 영상은 건너뛰고 이어서

## 3. 결과 (out 폴더)

- `sangnim_joined.mp4` : 유튜브에 '일부 공개'로 올릴 최종 영상 (소리 없음)
- `timeline.json` : 원본마다 최종 영상 몇 초에 들어갔는지 + 찍은 시각 (GPS·거점 맞추기용)
- `check/` : 흐림이 애매했던 장면 사진. 눈으로 보고 놓친 얼굴·번호판이 있으면 알려 주기
- `blur/` : 영상별 흐림 결과와 보고서 (다 끝나면 지워도 됨)

속도: 4코어 기준 초당 약 13프레임 → 영상 28분이면 1시간 안팎.
