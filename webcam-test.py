"""통합 테스트: capture + pose + logic + posture_judge

종료: q, 기준 자세 재측정: c
"""
import time
import cv2

from core.capture.capture import frames
from core.pose.ddd.pose_detector import RealTimePoseDetector
from core.posture_judge.connection import WebcamConnection

PROCESS_EVERY_N = 1  # 2~3으로 올리면 프레임 스킵 (연산량 감소)
INPUT_WIDTH = 480


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

            key = cv2.waitKey(1) & 0xFF
            connection.handle_key(key)
            if key == ord("q"):
                break

    except Exception as e:
        print(f"실행 중 오류 발생: {e}")
        raise
    finally:
        if connection is not None:
            connection.close()
        if detector is not None:
            detector.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
