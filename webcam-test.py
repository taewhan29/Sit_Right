""" 종료 : q """
# 원본 프레임으로 추론, 화면 출력만 거울모드

import time
import cv2
import mediapipe as mp

PROCESS_EVERY_N = 1  # 2~3으로 올리면 프레임 스킵 (연산량 감소)
INPUT_WIDTH = 480

mp_pose = mp.solutions.pose
mp_draw = mp.solutions.drawing_utils
PL = mp_pose.PoseLandmark
KEY_POINTS = [PL.NOSE, PL.LEFT_EAR, PL.RIGHT_EAR, PL.LEFT_SHOULDER, PL.RIGHT_SHOULDER]


def main():
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print("웹캠을 열 수 없습니다. 다른 프로그램이 쓰고 있는지 확인하세요.")
        return

    pose = mp_pose.Pose(
        model_complexity=0,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    )
    last_result, frame_idx, prev, fps = None, 0, time.time(), 0.0

    while True:
        ok, frame = cap.read()
        if not ok:
            print("프레임을 읽지 못했습니다.")
            break

        if frame_idx % PROCESS_EVERY_N == 0:
            h, w = frame.shape[:2]
            small = cv2.resize(frame, (INPUT_WIDTH, int(h * INPUT_WIDTH / w)))
            last_result = pose.process(cv2.cvtColor(small, cv2.COLOR_BGR2RGB))
        frame_idx += 1

        status = "NO POSE"
        if last_result and last_result.pose_landmarks:
            lm = last_result.pose_landmarks
            mp_draw.draw_landmarks(frame, lm, mp_pose.POSE_CONNECTIONS)
            h, w = frame.shape[:2]
            for p in KEY_POINTS:
                pt = lm.landmark[p]
                if pt.visibility > 0.5:
                    cv2.circle(frame, (int(pt.x * w), int(pt.y * h)), 7, (0, 255, 255), -1)
            seen = sum(lm.landmark[p].visibility > 0.5 for p in KEY_POINTS)
            status = f"key points {seen}/{len(KEY_POINTS)}"

        now = time.time()
        fps = 0.9 * fps + 0.1 * (1 / max(now - prev, 1e-6))
        prev = now

        frame = cv2.flip(frame, 1)  # 화면에 보여줄 때만 거울 모드
        cv2.putText(frame, f"FPS {fps:.1f} | {status}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.imshow("webcam test (q: quit)", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    pose.close()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()