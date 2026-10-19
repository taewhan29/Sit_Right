"""Q: 종료 / C: 기준 재측정. 원본으로 추론하고 표시만 거울 모드."""
import time
import cv2
from core.posture_judge.connection import WebcamConnection

PROCESS_EVERY_N = 1
INPUT_WIDTH = 480
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
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), ord("Q")):
                break
            connection.handle_key(key)
            if cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
                break
    finally:
        try:
            if connection is not None:
                connection.close()
        finally:
            cap.release()
            cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
