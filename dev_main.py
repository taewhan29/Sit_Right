"""전체 흐름 확인용 메인 루프: 웹캠 -> 포즈 인식 -> 캘리브레이션 -> 판정

stubs.py의 임시 함수를 각 담당자의 실제 함수로 바꿔 끼우면 된다.
(아래 import 한 줄만 바꾸면 됨)
"""


import cv2

from core.capture.capture import frames, show
from core.stubs import calibrate, compute_metrics, extract_landmarks, judge_posture

CALIB_SECONDS = 5  # 캘리브레이션 수집 시간(초)
SKIP = 3           # N프레임마다 1번만 추론
WIDTH = 480        # 추론용 가로 크기


def draw_points(frame, lm):
    """판정에 쓰는 점을 노란 점으로 표시 (원본 프레임 위에, 반전 전에 그린다)."""
    h, w = frame.shape[:2]
    for x, y, v in lm.values():
        if v > 0.5:
            cv2.circle(frame, (int(x * w), int(y * h)), 6, (0, 255, 255), -1)


def main():
    samples, baseline, start = [], None, None
    lm, result = None, None

    for frame, infer, ts in frames(skip=SKIP, width=WIDTH):
        start = start or ts

        if infer is not None:  # skip 간격의 프레임에서만 추론
            lm = extract_landmarks(infer)
            metric = compute_metrics(lm) if lm else None

            if baseline is None:  # 캘리브레이션 중: 바른 자세 샘플 수집
                if metric is not None:
                    samples.append(metric)
                if ts - start >= CALIB_SECONDS and samples:
                    baseline = calibrate(samples)
            else:                 # 캘리브레이션 완료: 기준값과 비교해 판정
                result = judge_posture(metric, baseline, ts)

        if lm:
            draw_points(frame, lm)

        if baseline is None:
            remain = max(0, CALIB_SECONDS - (ts - start))
            text = f"calibrating... {remain:.0f}s (sit straight)"
        else:
            text = f"state: {result['state'] if result else '-'}"

        if show(frame, text):
            break


if __name__ == "__main__":
    main()