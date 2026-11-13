import cv2
import mediapipe as mp


class RealTimePoseDetector:
    def __init__(self, min_detection_confidence=0.5, min_tracking_confidence=0.5, smoothing_factor=0.35):
        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose(
            model_complexity=1,  # 1로 설정하여 정확도 상승
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )
        self.mp_draw = mp.solutions.drawing_utils
        self.PL = self.mp_pose.PoseLandmark
        
        # 7개 포인트 (눈, 코, 귀, 어깨)
        # 0: 코, 2: 왼쪽 눈, 5: 오른쪽 눈, 7: 왼쪽 귀
        # 8: 오른쪽 귀, 11: 왼쪽 어깨, 12: 오른쪽 어깨
        self.target_points = [
            self.PL.NOSE, 
            self.PL.LEFT_EYE,
            self.PL.RIGHT_EYE,
            self.PL.LEFT_EAR, 
            self.PL.RIGHT_EAR, 
            self.PL.LEFT_SHOULDER, 
            self.PL.RIGHT_SHOULDER
        ]
        
        # 좌표 저장소
        self.previous_coords = {}
        self.smoothing_factor = smoothing_factor

    # 오작동 방지
    def _apply_smoothing_filter(self, point, current_x, current_y, current_z):
        if point not in self.previous_coords:
            self.previous_coords[point] = {"x": current_x, "y": current_y, "z": current_z}
            return current_x, current_y, current_z
            
        prev_x = self.previous_coords[point]["x"]
        prev_y = self.previous_coords[point]["y"]
        prev_z = self.previous_coords[point]["z"]
        
        distance_sq = (current_x - prev_x)**2 + (current_y - prev_y)**2
        factor = self.smoothing_factor
        if distance_sq > 0.08:
            factor = 0.05

        smoothed_x = (factor * current_x) + ((1 - factor) * prev_x)
        smoothed_y = (factor * current_y) + ((1 - factor) * prev_y)
        smoothed_z = (factor * current_z) + ((1 - factor) * prev_z)
        
        self.previous_coords[point] = {"x": smoothed_x, "y": smoothed_y, "z": smoothed_z}
        return smoothed_x, smoothed_y, smoothed_z

    # 뼈대 선 그리기 (좌표 정확도 확인을 위하여)
    def process_and_draw(self, frame, small_frame):
        h, w = frame.shape[:2]
        results = self.pose.process(cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB))
        
        extracted_coords = {}
        seen_count = 0

        if results.pose_landmarks:
            lm = results.pose_landmarks
            
            self.mp_draw.draw_landmarks(frame, lm, self.mp_pose.POSE_CONNECTIONS)
            
            for p in self.target_points:
                pt = lm.landmark[p]
                
                if pt.visibility > 0.5:
                    smoothed_x, smoothed_y, smoothed_z = self._apply_smoothing_filter(p, pt.x, pt.y, pt.z)
                    
                    # 눈의 좌표는 담지 않음 (코, 귀, 어깨 좌표값만)
                    if p not in [self.PL.LEFT_EYE, self.PL.RIGHT_EYE]:
                        extracted_coords[p] = {
                            "x": smoothed_x, 
                            "y": smoothed_y,
                            "z": smoothed_z
                        }
                        seen_count += 1
                    
                    px, py = int(smoothed_x * w), int(smoothed_y * h)
                    cv2.circle(frame, (px, py), 7, (0, 255, 255), -1) 
                    
                else:
                    if p in self.previous_coords:
                        del self.previous_coords[p]
            # print(extracted_coords) <- (좌표값 확인)
                        
        return extracted_coords, seen_count

    def close(self):
        self.pose.close()
