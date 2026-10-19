"""Team integration without editing logic or pose modules.

From Sit_Right: python -m core.posture_judge.connection
Requires the supplied logic.app.run(extract=...) interface.
"""
import argparse
from importlib import import_module
from pathlib import Path
import time
from collections.abc import Mapping


class WebcamConnection:
    """Own the teammate Pose detector and connect calibration/warnings.

    update receives the existing MediaPipe result and unflipped BGR frame.
    It returns a mirrored display frame. Call fresh=False on skipped frames.
    Construct/update/close on the main UI thread.
    """
    def __init__(self, reference_path=None):
        from . import PostureMonitor, Settings
        from ..logic.calibration import Calibrator, load_reference, save_reference
        from ..logic.landmarks import to_pose
        from ..logic.overlay import TextPainter
        from ..logic.app import calibration_lines, failed_lines, monitor_lines
        self.to_pose = to_pose
        self.save_reference = save_reference
        self.calibration_lines = calibration_lines
        self.failed_lines = failed_lines
        self.monitor_lines = monitor_lines
        self.path = Path(reference_path) if reference_path else (
            Path(__file__).resolve().parents[2] / 'data' / 'reference.json')
        self.settings = Settings()
        reference = load_reference(str(self.path), self.settings)
        self.calibrator = Calibrator(self.settings)
        self.painter = TextPainter()
        self.monitor = PostureMonitor(reference, self.settings)
        try:
            self.detector = create_detector()
        except Exception:
            self.monitor.close()
            raise
        self.state = self.result = None
        self.closed = False
        if reference is None:
            self.calibrator.start()
        print('자세 경고 연결 완료: 60/120/240초. C: 기준 재측정, Q: 종료.', flush=True)
        print('Pose 인식: core.pose.ddd.pose_detector.RealTimePoseDetector', flush=True)

    def infer(self, frame, small_frame):
        """Run only the team detector, drawing on the unflipped original frame."""
        if self.closed:
            raise RuntimeError('WebcamConnection is closed.')
        coords, seen = self.detector.process_and_draw(frame, small_frame)
        if not coords:
            history = getattr(self.detector, 'previous_coords', None)
            if history is not None:
                history.clear()
            return None, seen
        # Use normalized coordinates so logic.to_pose owns scaling consistently.
        return {key: {k: v for k, v in point.items() if k not in ('px', 'py')}
                for key, point in coords.items()}, seen

    def update(self, frame, pose_result, *, fresh=True):
        import cv2
        if self.closed:
            raise RuntimeError('WebcamConnection is closed.')
        now = time.monotonic()
        view = cv2.flip(frame, 1)
        # Inference already ran through self.infer; never run it again here.
        pose = None
<<<<<<< HEAD
        if fresh and pose_result is not None:
            if isinstance(pose_result, dict):
                pose = self.to_pose(pose_result, frame.shape[1], frame.shape[0])
            else:
=======
        if fresh:
            if isinstance(pose_result, Mapping):
                raw = pose_result
                pose = self.to_pose(raw, frame.shape[1], frame.shape[0])
            else:
                # Accept old MediaPipe results for compatibility with existing callers.
>>>>>>> 8d6c31f0af0682a2bccbc5d2a8c2255d41fccf34
                landmarks = getattr(pose_result, 'pose_landmarks', None)
                if landmarks is not None:
                    raw = {index: point for index, point in enumerate(landmarks.landmark)}
                    pose = self.to_pose(raw, frame.shape[1], frame.shape[0])
        if self.calibrator.active:
            if fresh:
                self.state = self.calibrator.update(pose, now=now)
                if self.state['completed']:
                    self.monitor.set_reference(self.state['reference'])
                    self.result = None
                    self.save_reference(str(self.path), self.state['reference'])
                    print('기준 자세 저장 완료.', flush=True)
            lines = self.calibration_lines(self.state) if self.state else []
        elif self.monitor.controller.baseline is None:
            lines = self.failed_lines()
        else:
            if fresh:
                self.result = self.monitor.update(pose, frame=view, now=now)
                if self.result['action']:
                    print(self.result['action'], flush=True)
            elif self.result is not None:
                # Keep video live without advancing logic using a stale pose.
                self.monitor.effects.update(dict(self.result, action=None), frame=view)
            lines = self.monitor_lines(self.result, self.settings,
                                       self.calibrator.status == 'failed') if self.result else []
        return self.painter.draw(view, lines)

    def handle_key(self, key):
        if key not in (ord('c'), ord('C')):
            return
        if self.monitor.controller.level == 3:
            print('3차 교정 중에는 기준을 변경할 수 없습니다.', flush=True)
            return
        self.monitor.effects.clear()
        self.calibrator.start()
        self.state = None

    def close(self):
        if not self.closed:
            self.closed = True
            try:
                self.monitor.close()
            finally:
                self.detector.close()


class PoseExtractor:
    """Adapt process_and_draw(frame, small_frame) to extract(frame).

    Return normalized coordinates unchanged. logic.landmarks.to_pose performs
    name conversion and pixel scaling. Drawing occurs on a disposable copy.
    """
    def __init__(self, detector):
        self.detector = detector

    def __call__(self, infer_frame):
        coords, _ = self.detector.process_and_draw(infer_frame.copy(), infer_frame)
        if not coords:
            # The supplied detector retains smoothing history when nobody is seen.
            # Do not reuse a previous person's coordinates after loss of tracking.
            history = getattr(self.detector, 'previous_coords', None)
            if history is not None:
                history.clear()
            return None
        # Drawing is done at inference resolution. Let logic.to_pose scale x/y
        # to the original frame; returning inference-sized px/py would be wrong.
        normalized = {}
        for key, value in coords.items():
            point = dict(value)
            point.pop('px', None)
            point.pop('py', None)
            normalized[key] = point
        return normalized


def create_detector():
    module = import_module('..pose.ddd.pose_detector', package=__package__)
    # The pasted class omitted its imports. Supply missing module names in
    # memory only; the teammate's source file is never rewritten.
    if not hasattr(module, 'cv2'):
        import cv2
        module.cv2 = cv2
    if not hasattr(module, 'mp'):
        import mediapipe as mp
        module.mp = mp
    return module.RealTimePoseDetector()


def main(argv=None):
    parser = argparse.ArgumentParser(description='실제 Pose + 팀원 캘리브레이션 + 자세 경고')
    parser.add_argument('--camera', type=int, default=0)
    parser.add_argument('--reference', default='data/reference.json')
    parser.add_argument('--recalibrate', action='store_true')
    parser.add_argument('--preview', action='store_true', help='전체 화면 효과 없이 미리보기')
    parser.add_argument('--demo', action='store_true', help='logic 앱의 5/10/15초 시연 설정')
    parser.add_argument('--no-mirror', action='store_true')
    # Fresh inference every frame avoids treating old coordinates as new samples.
    parser.add_argument('--skip', type=int, default=1)
    parser.add_argument('--width', type=int, default=480)
    args = parser.parse_args(argv)
    if args.skip < 1 or args.width < 1:
        parser.error('--skip and --width must be positive.')

    from ..logic.app import run

    detector = None
    try:
        detector = create_detector()
        print('실제 Pose 담당 코드와 연결했습니다. 임시 stubs는 사용하지 않습니다.', flush=True)
        print('기본 경고: 60/120/240초. --demo 옵션: 팀원 앱의 5/10/15초.', flush=True)
        run(camera=args.camera, reference_path=args.reference,
            recalibrate=args.recalibrate, preview_only=args.preview,
            demo=args.demo, mirror=not args.no_mirror,
            skip=args.skip, width=args.width, extract=PoseExtractor(detector))
    finally:
        if detector is not None:
            detector.close()


if __name__ == '__main__':
    main()
