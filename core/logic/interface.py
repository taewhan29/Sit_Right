"""Real implementation of the core/stubs.py 약속 인터페이스 (로직 담당 부분).

dev_main.py에서 import 한 줄만 바꾸면 된다:
    from core.stubs import extract_landmarks                       # 포즈 담당 (그대로)
    from core.logic import calibrate, compute_metrics, judge_posture # 로직 담당 (교체)

  compute_metrics(lm) -> dict | None
      {'head_offset', 'head_height', 'shoulder_angle', 'points'}
      posture_judge/controller.py와 같은 지표(코·양 어깨 기준). 점이 안 보이면 None.
  calibrate(samples) -> dict | None
      {'baseline': 지표 기준값, 'reference': 기준 랜드마크(PostureMonitor.set_reference용),
       'sample_count': 사용한 샘플 수}
      최근 샘플 중 흔들림 없이 이어진 구간의 중앙값. 안정 구간이 부족하면 None
      (dev_main은 None이면 계속 샘플을 모으다가 다시 호출한다).
  judge_posture(metric, baseline, ts) -> {'state', 'deviation', 'timestamp', 'reasons', 'deltas'}
      state: 'normal' | 'warning' | 'unknown'
      deviation: 허용치 대비 가장 큰 벗어남 비율 (1.0 초과 = 허용치 넘음)
      한 프레임 즉시 판정이다. 누적 시간·팝업·블러 경고는 posture_judge.PostureMonitor가 한다.
"""
from typing import Mapping, Optional, Sequence, Tuple

from ..posture_judge.controller import Settings, adapt_pose, extract_features
from .calibration import (FEATURES, CalibrationSettings, posture_problem, reference_from,
                          stability_limits, stable_tail, wrap_angle)
from .landmarks import to_pose

DEFAULT_SETTINGS = Settings()
DEFAULT_CALIBRATION = CalibrationSettings()
DEFAULT_FRAME_SIZE = (640, 480)   # typical webcam (4:3)
MAX_CALIBRATION_SAMPLES = 120     # only the most recent samples are examined


def tolerances(settings: Settings) -> dict:
    return {'head_offset': settings.head_offset_tolerance,
            'head_height': settings.head_height_tolerance,
            'shoulder_angle': settings.shoulder_angle_tolerance}


def compute_metrics(lm: Optional[Mapping], frame_size: Optional[Tuple[int, int]] = None,
                    settings: Optional[Settings] = None) -> Optional[dict]:
    """lm: extract_landmarks() result (normalized 0~1).

    frame_size=(width, height) of the camera frame keeps x/y on one scale.
    If omitted, a 4:3 webcam is assumed; pass frame.shape[1], frame.shape[0]
    for 16:9 cameras. Ignored when the landmarks already carry px/py pixels."""
    width, height = frame_size or DEFAULT_FRAME_SIZE
    points = to_pose(lm, width, height)
    if points is None:
        return None
    try:
        features = extract_features(adapt_pose(points), settings or DEFAULT_SETTINGS)
    except (TypeError, KeyError, ValueError, AttributeError):
        return None
    features['points'] = points
    return features


def calibrate(samples: Sequence[Optional[Mapping]], settings: Optional[Settings] = None,
              calibration: Optional[CalibrationSettings] = None) -> Optional[dict]:
    """samples: compute_metrics() results collected while the user sits straight."""
    settings = settings or DEFAULT_SETTINGS
    calibration = calibration or DEFAULT_CALIBRATION
    valid = [s for s in samples if s is not None and 'points' in s]
    limits = stability_limits(settings, calibration.stability_ratio)
    tail = stable_tail(valid, lambda s: s, limits, MAX_CALIBRATION_SAMPLES)
    if len(tail) < calibration.min_samples:
        return None
    try:
        reference, baseline = reference_from([s['points'] for s in tail], settings)
    except (TypeError, KeyError, ValueError, AttributeError):
        return None
    if posture_problem(baseline, calibration):
        return None
    return {'baseline': baseline, 'reference': reference, 'sample_count': len(tail)}


def judge_posture(metric: Optional[Mapping], baseline: Optional[Mapping], ts,
                  settings: Optional[Settings] = None) -> dict:
    if metric is None or not baseline:
        return {'state': 'unknown', 'deviation': None, 'timestamp': ts,
                'reasons': [], 'deltas': {}}
    limits = tolerances(settings or DEFAULT_SETTINGS)
    base = baseline['baseline']
    deltas = {}
    for key in FEATURES:
        delta = metric[key] - base[key]
        deltas[key] = wrap_angle(delta) if key == 'shoulder_angle' else delta
    reasons = [key for key in FEATURES if abs(deltas[key]) > limits[key]]
    deviation = max(abs(deltas[key]) / limits[key] for key in FEATURES)
    return {'state': 'warning' if reasons else 'normal', 'deviation': deviation,
            'timestamp': ts, 'reasons': reasons, 'deltas': deltas}
