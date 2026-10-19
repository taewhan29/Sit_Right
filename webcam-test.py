"""통합 테스트: capture + pose + logic + posture_judge

Q: 종료 / C: 기준 자세 재측정
"""
import time
import cv2

from core.capture.capture import frames
from core.posture_judge.connection import WebcamConnection

PROCESS_EVERY_N = 1
INPUT_WIDTH = 480
WINDOW = "webcam test (q: quit, c: recalibrate)"


def main():
    connection = None
    try:
        # 내부적으로 core.pose.ddd.pose_detector.RealTimePoseDetector를 생성하여 관리
        connection = WebcamConnection()
        last_coords, seen = None, 0
        prev, fps = time.monotonic(), 0.0

        for frame, infer, ts in frames(skip=PROCESS_EVERY_N, width=INPUT_WIDTH):
            fresh = infer is not None
            if fresh:
                # pose 모듈: 축소 프레임으로 추론, 원본 프레임에 관절 및 스무딩 포인트 렌더링
                last_coords, seen = connection.infer(frame, infer)

            now = time.monotonic()
            fps = 0.9 * fps + 0.1 / max(now - prev, 1e-6)
            prev = now

            # logic + posture_judge 모듈: 캘리브레이션 및 자세 판정, 한글 오버레이, 경고 제어
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

    except Exception as e:
        print(f"실행 중 오류 발생: {e}")
        raise
    finally:
        if connection is not None:
            connection.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
