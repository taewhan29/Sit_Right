"""Status text and progress bar on OpenCV frames.

cv2.putText cannot draw Hangul, so Korean text is drawn with Pillow and a system
Korean font. If no font is found, the ASCII fallback text is drawn instead.
"""
import os

import cv2
import numpy as np

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # Pillow missing -> ASCII fallback only
    Image = ImageDraw = ImageFont = None

FONT_CANDIDATES = (
    r'C:\Windows\Fonts\malgun.ttf',
    r'C:\Windows\Fonts\gulim.ttc',
    '/System/Library/Fonts/AppleSDGothicNeo.ttc',
    '/usr/share/fonts/truetype/nanum/NanumGothic.ttf',
    '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
)

WHITE = (255, 255, 255)
GREEN = (90, 210, 90)
RED = (70, 70, 235)
YELLOW = (60, 210, 240)
GRAY = (190, 190, 190)


class TextPainter:
    def __init__(self):
        self.path = None
        if Image is not None:
            self.path = next((p for p in FONT_CANDIDATES if os.path.exists(p)), None)
        self._fonts = {}

    def _font(self, size):
        if size not in self._fonts:
            self._fonts[size] = ImageFont.truetype(self.path, size)
        return self._fonts[size]

    def draw(self, frame, lines, margin=14):
        """lines: [(korean_text, ascii_fallback, bgr_color, font_size), ...].

        Draws a translucent panel at the top of frame and the lines on it.
        Returns the frame (a new array when Pillow is used)."""
        if not lines:
            return frame
        height = margin * 2 + sum(int(size * 1.4) for *_, size in lines)
        height = min(height, frame.shape[0])
        panel = frame[:height]
        panel[:] = (panel * 0.35).astype(np.uint8)

        if self.path is None:
            y = margin
            for _, fallback, color, size in lines:
                scale = size / 32
                y += int(size * 1.4)
                cv2.putText(frame, fallback, (margin, y - int(size * 0.35)),
                            cv2.FONT_HERSHEY_SIMPLEX, scale, color, 2, cv2.LINE_AA)
            return frame

        image = Image.fromarray(frame[:, :, ::-1])
        canvas = ImageDraw.Draw(image)
        y = margin
        for text, _, color, size in lines:
            canvas.text((margin, y), text, font=self._font(size), fill=tuple(reversed(color)))
            y += int(size * 1.4)
        return np.ascontiguousarray(np.asarray(image)[:, :, ::-1])


def draw_pose(frame, pose, min_confidence=0.6):
    """Keypoints + shoulder line + neck line on the ORIGINAL frame (before mirroring).

    pose: landmarks.to_pose() output (pixel coordinates) or None."""
    if not pose:
        return frame
    visible = {name: (int(p['x']), int(p['y'])) for name, p in pose.items()
               if p['confidence'] >= min_confidence}
    left, right = visible.get('left_shoulder'), visible.get('right_shoulder')
    if left and right:
        cv2.line(frame, left, right, (255, 200, 0), 3)
        if 'nose' in visible:
            middle = ((left[0] + right[0]) // 2, (left[1] + right[1]) // 2)
            cv2.line(frame, middle, visible['nose'], (255, 200, 0), 2)
    for point in visible.values():
        cv2.circle(frame, point, 7, (0, 255, 255), -1)
    return frame


def draw_bar(frame, ratio, color=GREEN, height=12, margin=14):
    """Progress bar along the bottom edge of frame (ratio 0.0 ~ 1.0)."""
    h, w = frame.shape[:2]
    top = h - margin - height
    right = w - margin
    cv2.rectangle(frame, (margin, top), (right, top + height), (60, 60, 60), -1)
    filled = margin + int((right - margin) * max(0.0, min(1.0, ratio)))
    if filled > margin:
        cv2.rectangle(frame, (margin, top), (filled, top + height), color, -1)
    return frame
