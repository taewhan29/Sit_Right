"""Full run: capture -> pose -> calibration -> posture monitor (warnings).

Uses the team modules as they are:
  core/capture/capture.py  frames()            webcam input, frame skip, resize
  core/stubs.py            extract_landmarks() pose (swap EXTRACTOR below when the
                                               pose team's real function is ready)
  core/posture_judge       PostureMonitor      judgement timing + popup/blur effects

Run from the repository root:
    python -m core.logic              # normal run
    python -m core.logic --demo       # warnings after 5 / 10 / 15 s (for 시연)
    python -m core.logic --help

Keys in the camera window: c = 기준 자세 재측정, q = 종료.
Warning overlay (level 2/3): Esc or Ctrl+Shift+F12 dismisses the screen.
"""
import argparse
import os
import time

import cv2

from ..posture_judge import PostureMonitor, Settings
from .calibration import Calibrator, load_reference, save_reference
from .landmarks import to_pose
from .overlay import GRAY, GREEN, RED, WHITE, YELLOW, TextPainter, draw_bar, draw_pose

WINDOW = 'Sit_Right  [c] calibrate  [q] quit'
REFERENCE_PATH = os.path.join('data', 'reference.json')
DEMO_SETTINGS = {'first_warning_seconds': 5.0, 'second_warning_seconds': 10.0,
                 'correction_seconds': 15.0}

REASON_TEXT = {
    'head_height': ('고개 숙임/거북목', 'head down'),
    'head_offset': ('머리 좌우 치우침', 'head side'),
    'shoulder_angle': ('어깨 기울어짐', 'shoulder tilt'),
}
LEVEL_TEXT = {0: '정상', 1: '1차(팝업)', 2: '2차(블러)', 3: '3차(교정)'}


def default_extractor():
    """Pose function: frame -> landmarks dict | None (normalized, unflipped frame).

    포즈 담당 코드가 완성되면 이 import 한 줄만 바꾸면 된다."""
    from ..stubs import extract_landmarks
    return extract_landmarks


def calibration_lines(state):
    lines = [('기준 자세 측정', 'CALIBRATION', WHITE, 26)]
    color = YELLOW if state['reason'] else WHITE
    fallback = f"{state['status']} {state['reason'] or ''}".strip()
    if state['status'] == 'countdown':
        fallback += f" {state['countdown_remaining']:.0f}s"
    lines.append((state['message'], fallback, color, 20))
    if state['status'] == 'collecting':
        lines.append((f"측정 중 {state['progress'] * 100:.0f}%",
                      f"measuring {state['progress'] * 100:.0f}%", GRAY, 18))
    return lines


def failed_lines():
    return [('기준 자세 측정 실패', 'CALIBRATION FAILED', RED, 26),
            ('c 키를 눌러 다시 측정하세요.', 'press c to retry', WHITE, 20)]


def monitor_lines(result, settings, calibration_failed):
    posture = result['posture']
    if posture == 'good':
        lines = [('바른 자세', 'GOOD', GREEN, 26)]
    elif posture == 'bad':
        names = [REASON_TEXT.get(r, (r, r)) for r in result['reasons']]
        lines = [('자세 교정 필요: ' + ', '.join(n[0] for n in names),
                  'BAD: ' + ', '.join(n[1] for n in names), RED, 26)]
    else:
        lines = [('자세 인식 안 됨 - 얼굴과 양쪽 어깨가 보이게 앉아 주세요',
                  'NO POSE', YELLOW, 22)]

    level = result['warning_level']
    bad = result['bad_duration']
    status = f"나쁜 자세 누적 {bad:.0f}초 | 경고 {LEVEL_TEXT[level]}"
    fallback = f"bad {bad:.0f}s | level {level}"
    thresholds = (settings.first_warning_seconds, settings.second_warning_seconds,
                  settings.correction_seconds)
    upcoming = [t for t in thresholds if t > bad]
    if level < 3 and upcoming:
        status += f" | 다음 경고까지 {upcoming[0] - bad:.0f}초"
    if level == 3:
        hold = result['correction_good_duration']
        status += f" | 교정 {hold:.1f}/{settings.correction_release_seconds:.0f}초"
    if result['warning_suspended']:
        status += ' | 경고 일시정지'
    lines.append((status, fallback, WHITE, 18))
    if calibration_failed:
        lines.append(('재측정 실패 - 기존 기준 자세로 계속합니다.', 'recalibration failed',
                      YELLOW, 16))
    return lines


def run(camera=0, reference_path=REFERENCE_PATH, recalibrate=False, preview_only=False,
        demo=False, mirror=True, skip=3, width=480, extract=None):
    """skip/width are passed to capture.frames() (같은 기본값: 3프레임마다 추론, 가로 480)."""
    from ..capture.capture import frames

    settings = Settings(**DEMO_SETTINGS) if demo else Settings()
    if os.name != 'nt' and not preview_only:
        print('Windows가 아니라서 화면 블러 없이 미리보기 모드로 실행합니다.')
        preview_only = True
    extract = extract or default_extractor()
    painter = TextPainter()
    if painter.path is None:
        print('한글 폰트를 찾지 못해 화면 안내를 영어로 표시합니다.')

    reference = None if recalibrate else load_reference(reference_path, settings)
    monitor = PostureMonitor(reference, settings, preview_only=preview_only)
    calibrator = Calibrator(settings)
    if reference is None:
        calibrator.start()
    else:
        print('저장된 기준 자세를 불러왔습니다. c 키로 다시 측정할 수 있습니다.')

    stream = frames(skip=skip, width=width, camera_index=camera)
    pose = None
    fps, previous = 0.0, time.monotonic()
    try:
        cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
        for frame, infer, _ in stream:
            if infer is not None:  # skip 간격의 프레임에서만 추론, 나머지는 직전 결과 유지
                pose = to_pose(extract(infer), frame.shape[1], frame.shape[0])
            now = time.monotonic()  # capture의 time.time()은 시계 보정 시 뒤로 갈 수 있음
            fps = 0.9 * fps + 0.1 / max(now - previous, 1e-6)
            previous = now

            draw_pose(frame, pose, settings.min_confidence)
            view = cv2.flip(frame, 1) if mirror else frame.copy()
            progress = None

            if calibrator.active:
                state = calibrator.update(pose, now=now)
                if state['completed']:
                    monitor.set_reference(state['reference'])
                    save_reference(reference_path, state['reference'])
                    print('기준 자세를 저장했습니다:', os.path.abspath(reference_path))
                lines = calibration_lines(state)
                if state['status'] == 'collecting':
                    progress = state['progress']
            elif monitor.controller.baseline is None:
                lines = failed_lines()
            else:
                result = monitor.update(pose, view, now=now)
                lines = monitor_lines(result, settings, calibrator.status == 'failed')

            lines.append((f'[c] 기준 재측정  [q] 종료  |  FPS {fps:.0f}',
                          f'[c] calibrate  [q] quit  |  FPS {fps:.0f}', GRAY, 15))
            view = painter.draw(view, lines)
            if progress is not None:
                draw_bar(view, progress)
            cv2.imshow(WINDOW, view)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
                break
            if key == ord('c'):
                monitor.effects.clear()
                calibrator.start(now)
    finally:
        stream.close()  # capture.frames() releases the camera
        monitor.close()
        cv2.destroyAllWindows()


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python -m core.logic',
                                     description='Sit_Right 자세 감시 (캘리브레이션 + 판정)')
    parser.add_argument('--camera', type=int, default=0, help='웹캠 번호 (기본 0)')
    parser.add_argument('--reference', default=REFERENCE_PATH, help='기준 자세 저장 파일')
    parser.add_argument('--recalibrate', action='store_true', help='저장된 기준 자세 무시하고 새로 측정')
    parser.add_argument('--preview', action='store_true', help='화면 블러 없이 팝업만 사용')
    parser.add_argument('--demo', action='store_true', help='경고 시간을 5/10/15초로 단축 (시연용)')
    parser.add_argument('--no-mirror', action='store_true', help='화면 좌우 반전 끄기')
    parser.add_argument('--skip', type=int, default=3, help='N프레임마다 1번 추론 (기본 3)')
    args = parser.parse_args(argv)
    run(args.camera, args.reference, args.recalibrate, args.preview, args.demo,
        not args.no_mirror, args.skip)


if __name__ == '__main__':
    main()
