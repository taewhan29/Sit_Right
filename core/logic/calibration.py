"""Reference-posture calibration (기준 자세 측정).

Two ways to use it:
  1. calibrate(samples)  in interface.py - stateless, for dev_main.py (stubs 약속 인터페이스)
  2. Calibrator          - per-frame state machine with countdown/progress/messages (app.py)

Calibrator flow: idle -> countdown -> collecting -> done | failed
  countdown : time for the user to sit up straight (no measurement).
  collecting: a sliding window of valid frames. The window restarts when the pose
              is lost, the frame stream stalls, the shoulders are tilted, or the
              user moves. It completes once hold_seconds of stable frames exist.
  done      : reference = per-landmark median of the stable window.
Feed it the pose from landmarks.to_pose(); when completed=True pass
result['reference'] to PostureMonitor.set_reference().
"""
import json
import os
from dataclasses import dataclass
from math import ceil, isfinite
from statistics import median
from time import monotonic
from typing import Callable, Mapping, Optional, Sequence

from ..posture_judge.controller import Settings, adapt_pose, extract_features

NAMES = ('nose', 'left_shoulder', 'right_shoulder')
FEATURES = ('head_offset', 'head_height', 'shoulder_angle')

MESSAGES = {
    'idle': '기준 자세 측정 대기 중입니다.',
    'collecting': '바른 자세를 그대로 유지하세요.',
    'done': '기준 자세 설정이 완료되었습니다.',
    'pose_unavailable': '얼굴과 양쪽 어깨가 화면에 보이도록 앉아 주세요.',
    'shoulder_tilted': '어깨가 기울어져 있습니다. 수평을 맞춰 주세요.',
    'head_below_shoulders': '머리가 어깨보다 낮게 인식됩니다. 카메라 위치를 확인해 주세요.',
    'moving': '움직임이 감지되어 측정을 다시 시작합니다.',
    'frame_gap': '영상이 끊겨 측정을 다시 시작합니다.',
    'timeout': '안정된 자세를 찾지 못했습니다. 다시 시도해 주세요.',
    'cancelled': '기준 자세 측정이 취소되었습니다.',
}


@dataclass(frozen=True)
class CalibrationSettings:
    countdown_seconds: float = 3.0   # preparation time before measuring
    hold_seconds: float = 3.0        # stable time required for the reference
    timeout_seconds: float = 30.0    # measuring time limit (after countdown)
    min_samples: int = 15            # at least this many frames in the window
    stability_ratio: float = 0.5     # allowed jitter = ratio x posture tolerance
    max_shoulder_tilt: float = 15.0  # degrees; reject an already tilted reference

    def __post_init__(self):
        if not isfinite(self.countdown_seconds) or self.countdown_seconds < 0:
            raise ValueError('countdown_seconds must be finite and >= 0.')
        values = (self.hold_seconds, self.timeout_seconds, self.max_shoulder_tilt)
        if any(not isfinite(v) or v <= 0 for v in values):
            raise ValueError('Durations and tilt limit must be positive and finite.')
        if self.timeout_seconds <= self.hold_seconds:
            raise ValueError('timeout_seconds must be longer than hold_seconds.')
        if self.min_samples < 1:
            raise ValueError('min_samples must be at least 1.')
        if not 0 < self.stability_ratio <= 1:
            raise ValueError('stability_ratio must be in (0, 1].')


# ------------------------------------------------------------ shared helpers
def wrap_angle(value: float) -> float:
    return (value + 90) % 180 - 90


def stability_limits(settings: Settings, ratio: float) -> dict:
    """Allowed frame-to-frame jitter while measuring, per feature."""
    return {'head_offset': ratio * settings.head_offset_tolerance,
            'head_height': ratio * settings.head_height_tolerance,
            'shoulder_angle': ratio * settings.shoulder_angle_tolerance}


def median_features(features_list: Sequence[Mapping]) -> dict:
    center = {}
    for key in FEATURES:
        values = [features[key] for features in features_list]
        if key == 'shoulder_angle':
            base = values[0]
            center[key] = wrap_angle(base + median(wrap_angle(v - base) for v in values))
        else:
            center[key] = median(values)
    return center


def fits(features: Mapping, center: Mapping, limits: Mapping) -> bool:
    for key, limit in limits.items():
        delta = features[key] - center[key]
        if key == 'shoulder_angle':
            delta = wrap_angle(delta)
        if abs(delta) > limit:
            return False
    return True


def posture_problem(features: Mapping, calibration: CalibrationSettings) -> Optional[str]:
    """Reason a frame cannot be a reference posture, or None."""
    if abs(features['shoulder_angle']) > calibration.max_shoulder_tilt:
        return 'shoulder_tilted'
    if features['head_height'] <= 0:
        return 'head_below_shoulders'
    return None


def stable_tail(items: Sequence, key: Callable, limits: Mapping,
                max_items: Optional[int] = None) -> list:
    """Longest run of the most recent items whose features agree with each other."""
    recent = list(items[-max_items:] if max_items else items)
    tail = []
    for item in reversed(recent):
        candidate = [item] + tail
        if tail and not fits(key(item), median_features([key(x) for x in candidate]), limits):
            break
        tail = candidate
    while len(tail) > 1 and not fits(key(tail[0]), median_features([key(x) for x in tail]), limits):
        tail.pop(0)
    return tail


def reference_from(points_list: Sequence[Mapping], settings: Settings):
    """Per-landmark median -> (reference pose, its features). Raises ValueError if unusable."""
    reference = {}
    for name in NAMES:
        marks = [points[name] for points in points_list]
        reference[name] = {'x': median(m['x'] for m in marks),
                           'y': median(m['y'] for m in marks),
                           'confidence': median(m.get('confidence', 1.0) for m in marks)}
    features = extract_features(adapt_pose(reference), settings)
    return reference, features


# ------------------------------------------------------------- Calibrator
class Calibrator:
    def __init__(self, settings: Optional[Settings] = None,
                 calibration: Optional[CalibrationSettings] = None):
        """settings must be the same Settings object the PostureController uses."""
        self.settings = settings or Settings()
        self.calibration = calibration or CalibrationSettings()
        self.limits = stability_limits(self.settings, self.calibration.stability_ratio)
        self.status = 'idle'
        self.reason = None
        self.reference = None
        self.reference_features = None
        self.samples = []  # (time, pose, features)
        self.started_at = self.collect_started_at = self.last_time = None

    def start(self, now: Optional[float] = None) -> None:
        """Begin (or restart) calibration. Previous result is discarded."""
        now = monotonic() if now is None else float(now)
        if not isfinite(now):
            raise ValueError('Time must be finite.')
        self.status = 'countdown'
        self.reason = None
        self.reference = self.reference_features = None
        self.samples = []
        self.started_at = self.last_time = now
        self.collect_started_at = None

    def cancel(self) -> None:
        self.status = 'idle'
        self.reason = 'cancelled'
        self.samples = []

    @property
    def active(self) -> bool:
        return self.status in ('countdown', 'collecting')

    def update(self, pose: Optional[Mapping], now: Optional[float] = None) -> dict:
        """Call once per frame while active. pose: landmarks.to_pose() output or None."""
        now = monotonic() if now is None else float(now)
        if not isfinite(now) or (self.last_time is not None and now < self.last_time):
            raise ValueError('Time must be finite and nondecreasing.')
        gap = 0.0 if self.last_time is None else now - self.last_time
        self.last_time = now
        if not self.active:
            return self._result(now, {}, False)

        reason, points, features = None, None, {}
        try:
            points = adapt_pose(pose)
            features = extract_features(points, self.settings)
        except (TypeError, KeyError, ValueError, AttributeError):
            reason, points, features = 'pose_unavailable', None, {}
        else:
            reason = posture_problem(features, self.calibration)

        if self.status == 'countdown':
            if now - self.started_at < self.calibration.countdown_seconds:
                self.reason = reason
                return self._result(now, features, False)
            self.status = 'collecting'
            self.collect_started_at = now
            self.samples = []

        if now - self.collect_started_at >= self.calibration.timeout_seconds:
            self.status, self.reason, self.samples = 'failed', 'timeout', []
            return self._result(now, features, False)

        if self.samples and gap > self.settings.max_sample_gap_seconds:
            self.samples = []
            reason = reason or 'frame_gap'
        if reason in ('pose_unavailable', 'shoulder_tilted', 'head_below_shoulders'):
            self.samples = []
        else:
            if self.samples and not fits(features, self._center(), self.limits):
                self.samples = []
                reason = 'moving'
            self.samples.append((now, points, features))
            if self._trim_drift():
                reason = reason or 'moving'
        self.reason = reason

        completed = False
        if (len(self.samples) >= self.calibration.min_samples
                and now - self.samples[0][0] >= self.calibration.hold_seconds):
            completed = self._finalize()
        return self._result(now, features, completed)

    def _center(self) -> dict:
        return median_features([sample[2] for sample in self.samples])

    def _trim_drift(self) -> bool:
        """Drop the oldest frames while slow drift makes the window inconsistent."""
        trimmed = False
        while len(self.samples) > 1 and not fits(self.samples[0][2], self._center(), self.limits):
            self.samples.pop(0)
            trimmed = True
        return trimmed

    def _finalize(self) -> bool:
        marks = [{name: {'x': p.x, 'y': p.y, 'confidence': p.confidence}
                  for name, p in sample[1].items()} for sample in self.samples]
        try:
            reference, features = reference_from(marks, self.settings)
        except (TypeError, KeyError, ValueError, AttributeError):
            self.samples = []
            self.reason = 'pose_unavailable'
            return False
        self.reference, self.reference_features = reference, features
        self.status, self.reason = 'done', None
        return True

    def _result(self, now: float, features: Mapping, completed: bool) -> dict:
        remaining = None
        progress = 0.0
        if self.status == 'countdown':
            remaining = max(0.0, self.calibration.countdown_seconds - (now - self.started_at))
        elif self.status == 'collecting' and self.samples:
            progress = min(1.0, (now - self.samples[0][0]) / self.calibration.hold_seconds)
        elif self.status == 'done':
            progress = 1.0

        if self.reason:
            message = MESSAGES[self.reason]
        elif self.status == 'countdown':
            message = f'{ceil(remaining)}초 후 측정을 시작합니다. 바른 자세로 앉아 주세요.'
        else:
            message = MESSAGES.get(self.status, '')
        return {
            'status': self.status,            # idle / countdown / collecting / done / failed
            'completed': completed,           # True only on the frame calibration finished
            'progress': progress,             # 0.0 ~ 1.0 of hold_seconds
            'countdown_remaining': remaining,
            'reason': self.reason,
            'message': message,
            'sample_count': len(self.samples),
            'features': dict(features),
            'reference': self.reference,      # pass to set_reference() when completed
            'reference_features': self.reference_features,
        }


# ------------------------------------------------------------ persistence
def save_reference(path: str, reference: Mapping) -> None:
    """Save a reference so the user need not recalibrate every launch.

    This is personal posture data; keep it out of git (e.g. data/*.json in .gitignore)."""
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    payload = {'version': 1, 'reference': {
        name: {'x': float(reference[name]['x']), 'y': float(reference[name]['y']),
               'confidence': float(reference[name].get('confidence', 1.0))}
        for name in NAMES}}
    with open(path, 'w', encoding='utf-8') as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


def load_reference(path: str, settings: Optional[Settings] = None) -> Optional[dict]:
    """Return a saved reference, or None if missing or unusable."""
    try:
        with open(path, encoding='utf-8') as file:
            reference = json.load(file)['reference']
        extract_features(adapt_pose(reference), settings or Settings())
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None
    return reference
