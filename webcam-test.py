<<<<<<< HEAD
"""통합 테스트: capture + pose + logic + posture_judge

종료: q, 기준 자세 재측정: c
"""
import time
import cv2

from core.capture.capture import frames
from core.pose.ddd.pose_detector import RealTimePoseDetector
=======
"""Q: 종료 / C: 기준 재측정. 원본으로 추론하고 표시만 거울 모드."""
import time
import cv2
>>>>>>> 8d6c31f0af0682a2bccbc5d2a8c2255d41fccf34
from core.posture_judge.connection import WebcamConnection

PROCESS_EVERY_N = 1
INPUT_WIDTH = 480
<<<<<<< HEAD


def main():
    detector = connection = None
    try:
        detector = RealTimePoseDetector()
        connection = WebcamConnection()
        last_coords, last_seen = None, 0
        prev_time = time.time()
        fps = 0.0

        for frame, infer, ts in frames(skip=PROCESS_EVERY_N, width=INPUT_WIDTH):
            fresh = infer is not None
            if fresh:
                # pose 모듈: 축소 프레임으로 추론, 원본 프레임에 관절 및 스무딩 포인트 렌더링
                last_coords, last_seen = detector.process_and_draw(frame, infer)

            status = f"key points {last_seen}/5" if last_seen > 0 else "NO POSE"

            now = time.time()
            fps = 0.9 * fps + 0.1 * (1 / max(now - prev_time, 1e-6))
            prev_time = now

            # logic + posture_judge 모듈: 캘리브레이션 및 자세 판정, 한글 오버레이, 경고 제어
            frame = connection.update(frame, last_coords, fresh=fresh)

            # FPS 및 포인트 상태 표시
            cv2.putText(frame, f"FPS {fps:.1f} | {status}", (10, frame.shape[0] - 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.imshow("webcam test (q: quit, c: recalibrate)", frame)

=======
WINDOW = "webcam test (q: quit)"


def main():
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap.release()
        print("웹캠을 열 수 없습니다. 다른 프로그램이 쓰고 있는지 확인하세요.")
        return

    connection = None
    try:
        # This object creates exactly one RealTimePoseDetector from pose/ddd.
        connection = WebcamConnection()
        last_coords, seen = None, 0
        frame_idx, prev, fps = 0, time.monotonic(), 0.0
        while True:
            ok, frame = cap.read()
            if not ok:
                print("프레임을 읽지 못했습니다.")
                break

            fresh = frame_idx % PROCESS_EVERY_N == 0
            if fresh:
                h, w = frame.shape[:2]
                small = cv2.resize(frame, (INPUT_WIDTH, max(1, int(h * INPUT_WIDTH / w))))
                last_coords, seen = connection.infer(frame, small)
            frame_idx += 1

            now = time.monotonic()
            fps = 0.9 * fps + 0.1 / max(now - prev, 1e-6)
            prev = now
            frame = connection.update(frame, last_coords, fresh=fresh)
            status = f"key points {seen}/5" if last_coords else "NO POSE"
            cv2.putText(frame, f"FPS {fps:.1f} | {status}", (10, frame.shape[0] - 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.imshow(WINDOW, frame)
>>>>>>> 8d6c31f0af0682a2bccbc5d2a8c2255d41fccf34
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), ord("Q")):
                break
            connection.handle_key(key)
            if cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
                break
<<<<<<< HEAD

    except Exception as e:
        print(f"실행 중 오류 발생: {e}")
        raise
    finally:
        if connection is not None:
            connection.close()
        if detector is not None:
            detector.close()
        cv2.destroyAllWindows()
=======
    finally:
        try:
            if connection is not None:
                connection.close()
        finally:
            cap.release()
            cv2.destroyAllWindows()

>>>>>>> 8d6c31f0af0682a2bccbc5d2a8c2255d41fccf34

if __name__ == "__main__":
    main()
