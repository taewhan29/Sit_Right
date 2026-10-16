"""웹캠 입력 및 프레임 처리 (프레임 스킵, 추론용 축소, 화면 표시)

- 원본 프레임은 메모리에서만 쓰고 디스크에 저장하지 않는다.
- 추론은 항상 좌우 반전하지 않은 원본 프레임으로 한다.
  거울 모드는 화면에 보여주는 순간에만 적용한다.
"""
import time

import cv2


def frames(skip=3, width=480, camera_index=0):
    """웹캠 프레임을 하나씩 돌려준다.

    yield: (frame, infer_frame, timestamp)
      frame       : 원본 BGR 프레임 (화면 표시용)
      infer_frame : 추론용으로 축소한 프레임. skip 간격이 아닌 프레임에서는 None
      timestamp   : 프레임을 읽은 시각 이벤트 발생 시각 기록에 사용
    """
    cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        raise RuntimeError(
            "웹캠을 열 수 없습니다. 카메라 개인정보 보호 모드나 "
            "다른 프로그램의 카메라 사용 여부를 확인하세요."
        )

    idx = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            ts = time.time()

            infer = None
            if idx % skip == 0: 
                h, w = frame.shape[:2]
                infer = cv2.resize(frame, (width, int(h * width / w)))
            idx += 1

            yield frame, infer, ts
    finally:
        cap.release()
        cv2.destroyAllWindows()


def show(frame, text="", title="posture (q: quit)"):
    """화면에 거울 모드로 표시한다. q를 누르면 True를 돌려준다."""
    view = cv2.flip(frame, 1) 
    if text:
        cv2.putText(view, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                    0.7, (0, 255, 0), 2)
    cv2.imshow(title, view)
    return (cv2.waitKey(1) & 0xFF) == ord("q")