"""임시(스텁) 구현 - 각 담당자의 실제 코드가 올라오면 이 파일의 함수를 교체한다.

입출력 약속(안):
  extract_landmarks(infer_frame) -> dict | None
      {"nose": (x, y, visibility), "left_ear": ..., "right_ear": ...,
       "left_shoulder": ..., "right_shoulder": ...}
      x, y는 0~1 정규화 좌표(좌우 반전하지 않은 원본 기준), 사람이 없으면 None
  compute_metrics(lm) -> float | None   핵심 점이 잘 안 보이면 None
  calibrate(samples) -> dict            기준값
  judge_posture(metric, baseline, ts) -> {"state", "deviation", "timestamp"}

여기 있는 지표와 임계값은 전체 흐름을 돌려보기 위한 임시값이다.
"""
import statistics

import cv2
import mediapipe as mp

_PL = mp.solutions.pose.PoseLandmark
_KEYS = {
    "nose": _PL.NOSE,
    "left_ear": _PL.LEFT_EAR,
    "right_ear": _PL.RIGHT_EAR,
    "left_shoulder": _PL.LEFT_SHOULDER,
    "right_shoulder": _PL.RIGHT_SHOULDER,
}
_pose = mp.solutions.pose.Pose(
    model_complexity=0, min_detection_confidence=0.5, min_tracking_confidence=0.5
)


def extract_landmarks(infer_frame):
    result = _pose.process(cv2.cvtColor(infer_frame, cv2.COLOR_BGR2RGB))
    if not result.pose_landmarks:
        return None
    lm = result.pose_landmarks.landmark
    return {name: (lm[i].x, lm[i].y, lm[i].visibility) for name, i in _KEYS.items()}


def compute_metrics(lm):
    """귀~어깨 수직 거리를 어깨너비로 나눈 값 (임시 지표)."""
    if any(p[2] < 0.5 for p in lm.values()):
        return None
    ls, rs = lm["left_shoulder"], lm["right_shoulder"]
    le, re = lm["left_ear"], lm["right_ear"]
    width = abs(ls[0] - rs[0])
    if width < 1e-6:
        return None
    return ((ls[1] + rs[1]) / 2 - (le[1] + re[1]) / 2) / width


def calibrate(samples):
    return {"baseline": statistics.median(samples)}


def judge_posture(metric, baseline, ts, threshold=0.15):
    if metric is None:
        return {"state": "unknown", "deviation": None, "timestamp": ts}
    base = baseline["baseline"]
    dev = (metric - base) / abs(base)
    # 머리가 아래로 내려오면 귀와 어깨의 거리가 줄어 지표가 작아진다
    state = "warning" if dev < -threshold else "normal"
    return {"state": state, "deviation": dev, "timestamp": ts}