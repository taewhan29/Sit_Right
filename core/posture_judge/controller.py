"""Pose input, posture comparison, and warning timing. No GUI dependencies."""
from dataclasses import dataclass
from math import atan2, degrees, hypot, isfinite
from time import monotonic
from typing import Mapping, Optional


@dataclass(frozen=True)
class Landmark:
    x: float
    y: float
    confidence: float = 1.0


@dataclass(frozen=True)
class Settings:
    min_confidence: float = 0.6
    head_offset_tolerance: float = 0.15
    head_height_tolerance: float = 0.15
    shoulder_angle_tolerance: float = 8.0
    first_warning_seconds: float = 60.0
    second_warning_seconds: float = 120.0
    correction_seconds: float = 240.0
    correction_release_seconds: float = 5.0
    smoothing_seconds: float = 0.25
    max_sample_gap_seconds: float = 0.5

    def __post_init__(self):
        if not (0 < self.first_warning_seconds < self.second_warning_seconds
                < self.correction_seconds):
            raise ValueError('Warning thresholds must increase.')
        values = (self.head_offset_tolerance, self.head_height_tolerance,
                  self.shoulder_angle_tolerance, self.correction_release_seconds,
                  self.max_sample_gap_seconds)
        if any(not isfinite(v) or v <= 0 for v in values):
            raise ValueError('Tolerances and durations must be positive and finite.')
        if not 0 <= self.min_confidence <= 1 or self.smoothing_seconds < 0:
            raise ValueError('Invalid confidence or smoothing value.')


def adapt_pose(raw: Mapping) -> dict[str, Landmark]:
    """Replace ONLY this adapter when your team's Pose format is known.

    Temporary format: {name: {'x': ..., 'y': ..., 'confidence': ...}}.
    Required names: nose, left_shoulder, right_shoulder.
    x/y must share the same scale (pixels are recommended).
    """
    result = {}
    for name in ('nose', 'left_shoulder', 'right_shoulder'):
        value = raw[name]
        result[name] = value if isinstance(value, Landmark) else Landmark(
            float(value['x']), float(value['y']),
            float(value.get('confidence', value.get('visibility', 1.0))))
    return result


def extract_features(points: Mapping[str, Landmark], settings: Settings) -> dict:
    nose, left, right = (points[name] for name in
                         ('nose', 'left_shoulder', 'right_shoulder'))
    for point in (nose, left, right):
        if (not all(isfinite(v) for v in (point.x, point.y, point.confidence))
                or not settings.min_confidence <= point.confidence <= 1):
            raise ValueError('Missing or unreliable landmarks.')
    width = hypot(right.x - left.x, right.y - left.y)
    if width < 1e-6:
        raise ValueError('Shoulder width is too small.')
    angle = degrees(atan2(right.y - left.y, right.x - left.x))
    angle = (angle + 90) % 180 - 90
    return {
        'head_offset': (nose.x - (left.x + right.x) / 2) / width,
        'head_height': ((left.y + right.y) / 2 - nose.y) / width,
        'shoulder_angle': angle,
    }


class PostureController:
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()
        self.baseline = None
        self.filtered = None
        self.level = 0
        self.bad_duration = 0.0
        self.good_duration = 0.0
        self.last_time = None
        self.previous_status = 'unknown'
        self.warning_suspended = False
        self.second_warning_completed = False

    def set_reference(self, raw: Mapping) -> dict:
        """Accept reference landmarks supplied by the reference-setting component.

        Replacing a reference starts a new warning session. No camera or key input."""
        features = extract_features(adapt_pose(raw), self.settings)
        self.baseline = features.copy()
        self.filtered = None
        self.level = 0
        self.bad_duration = self.good_duration = 0.0
        self.last_time = None
        self.previous_status = 'unknown'
        self.warning_suspended = False
        self.second_warning_completed = False
        return features.copy()

    def update(self, raw: Optional[Mapping], now: Optional[float] = None) -> dict:
        """Call once per frame. now is optional monotonic time for testing.

        Level 0: monitoring, 1: popup, 2: blur, 3: correction.
        Unknown frames pause escalation and interrupt continuous good posture.
        """
        now = monotonic() if now is None else float(now)
        if not isfinite(now) or (self.last_time is not None and now < self.last_time):
            raise ValueError('Time must be finite and nondecreasing.')
        gap = 0.0 if self.last_time is None else now - self.last_time
        continuous = gap <= self.settings.max_sample_gap_seconds
        self.last_time = now
        old_level = self.level
        was_suspended = self.warning_suspended
        metrics, reasons = {}, []
        if self.baseline is None:
            status = 'unknown'
            reasons = ['reference_not_set']
        else:
            try:
                metrics = extract_features(adapt_pose(raw), self.settings)
            except (TypeError, KeyError, ValueError, AttributeError):
                status = 'unknown'
                reasons = ['pose_unavailable']
            else:
                if self.filtered is None or not continuous or self.previous_status == 'unknown':
                    self.filtered = metrics.copy()
                else:
                    tau = self.settings.smoothing_seconds
                    alpha = 1.0 if tau == 0 else gap / (tau + gap)
                    for key, value in metrics.items():
                        difference = value - self.filtered[key]
                        if key == 'shoulder_angle':
                            difference = (difference + 90) % 180 - 90
                        self.filtered[key] += alpha * difference
                metrics = self.filtered.copy()
                tolerances = {
                    'head_offset': self.settings.head_offset_tolerance,
                    'head_height': self.settings.head_height_tolerance,
                    'shoulder_angle': self.settings.shoulder_angle_tolerance,
                }
                for key, tolerance in tolerances.items():
                    delta = metrics[key] - self.baseline[key]
                    if key == 'shoulder_angle':
                        delta = (delta + 90) % 180 - 90
                    if abs(delta) > tolerance:
                        reasons.append(key)
                status = 'bad' if reasons else 'good'

        dt = gap if continuous and self.previous_status == status else 0.0
        if not continuous:
            self.good_duration = 0.0
        if status == 'unknown':
            self.good_duration = 0.0
            self.filtered = None
        elif self.level == 3:
            self.good_duration = self.good_duration + dt if status == 'good' else 0.0
            if self.good_duration >= self.settings.correction_release_seconds:
                self.level = 0
                self.bad_duration = self.good_duration = 0.0
                self.warning_suspended = False
                self.second_warning_completed = False
        elif status == 'good':
            self.good_duration += dt
            self.warning_suspended = self.level > 0
            if self.level == 2:
                self.second_warning_completed = True
        else:
            self.warning_suspended = False
            self.good_duration = 0.0
            self.bad_duration += dt
            if self.bad_duration >= self.settings.correction_seconds:
                self.level = 3
            elif self.bad_duration >= self.settings.second_warning_seconds:
                self.level = 2
            elif self.bad_duration >= self.settings.first_warning_seconds:
                self.level = 1
            if self.level == 2 and self.second_warning_completed:
                self.warning_suspended = True
        self.previous_status = status
        actions = {0: 'clear_warnings', 1: 'show_popup',
                   2: 'enable_blur', 3: 'enter_correction'}
        action = actions[self.level] if self.level != old_level else None
        if self.level == old_level and self.warning_suspended != was_suspended:
            if self.warning_suspended:
                action = 'suspend_warnings'
            elif self.level == 2:
                action = 'enable_blur'
        effect_level = 0 if self.warning_suspended else self.level
        return {
            'posture': status,
            'warning_level': self.level,
            'action': action,
            'effect_level': effect_level,
            'warning_suspended': self.warning_suspended,
            'second_warning_completed': self.second_warning_completed,
            'bad_duration': self.bad_duration,
            'correction_good_duration': self.good_duration if self.level == 3 else 0.0,
            'reasons': reasons,
            'metrics': metrics,
        }
