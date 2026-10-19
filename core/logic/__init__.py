"""Sit_Right logic (로직 담당): landmark adapter, calibration, posture judgement.

dev_main.py 연결 (stubs 교체):
    from core.logic import calibrate, compute_metrics, judge_posture
전체 실행 (캘리브레이션 + 경고 효과까지):
    python -m core.logic
"""
from .calibration import CalibrationSettings, Calibrator, load_reference, save_reference
from .interface import calibrate, compute_metrics, judge_posture
from .landmarks import to_pose


def run(*args, **kwargs):
    """Start the full app (imports the camera/pose modules only when called)."""
    from .app import run as _run
    return _run(*args, **kwargs)


__all__ = ['CalibrationSettings', 'Calibrator', 'calibrate', 'compute_metrics',
           'judge_posture', 'load_reference', 'run', 'save_reference', 'to_pose']
