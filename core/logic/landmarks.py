"""Convert the pose team's landmark output into the posture_judge pose format.

Accepted inputs (any of these, None = no person):
  core/stubs.py          {"nose": (x, y, visibility), "left_shoulder": ..., ...}
  pose/ddd/pose_detector {PoseLandmark.NOSE: {"x", "y", "z"[, "visibility"][, "px", "py"]}, ...}
  MediaPipe landmark objects with .x .y .visibility

x, y are normalized 0~1 on the ORIGINAL (unflipped) frame unless "px"/"py" are given.
Output: {"nose": {"x": px, "y": px, "confidence": c}, "left_shoulder": ..., "right_shoulder": ...}
Pixels keep x and y on the same scale, which posture_judge needs for angles and ratios.
"""
from math import isfinite
from typing import Mapping, Optional

# MediaPipe Pose indices. PoseLandmark is an IntEnum, so enum keys match these ints.
REQUIRED = {'nose': 0, 'left_shoulder': 11, 'right_shoulder': 12}


def _lookup(lm: Mapping, name: str, index: int):
    for key in (name, name.upper(), index):
        try:
            if key in lm:
                return lm[key]
        except TypeError:
            continue
    return None


def _read(value, width: float, height: float) -> Optional[dict]:
    if value is None:
        return None
    if isinstance(value, Mapping):
        if 'px' in value and 'py' in value:
            x, y = float(value['px']), float(value['py'])
        else:
            x, y = float(value['x']) * width, float(value['y']) * height
        confidence = value.get('visibility', value.get('confidence', 1.0))
    elif isinstance(value, (tuple, list)):
        x, y = float(value[0]) * width, float(value[1]) * height
        confidence = value[2] if len(value) > 2 else 1.0
    else:  # MediaPipe NormalizedLandmark-like object
        x, y = float(value.x) * width, float(value.y) * height
        confidence = getattr(value, 'visibility', 1.0)
    confidence = float(confidence)
    if not all(isfinite(v) for v in (x, y, confidence)):
        return None
    return {'x': x, 'y': y, 'confidence': confidence}


def to_pose(lm: Optional[Mapping], width: float, height: float) -> Optional[dict]:
    """width, height: size of the frame the normalized coordinates refer to.

    Returns None when lm is empty or any required point is missing/invalid."""
    if not lm or width <= 0 or height <= 0:
        return None
    pose = {}
    try:
        for name, index in REQUIRED.items():
            point = _read(_lookup(lm, name, index), width, height)
            if point is None:
                return None
            pose[name] = point
    except (TypeError, ValueError, KeyError, IndexError, AttributeError):
        return None
    return pose
