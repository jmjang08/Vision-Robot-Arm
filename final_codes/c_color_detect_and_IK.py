import cv2
import numpy as np
import requests
import json
import time
import os
import math

# --- [설정] 로봇 링크 길이 ---
L1 = 82.0
L2 = 81.0

# --- [설정] 로봇 오프셋 ---
ROBOT_OFFSET_X = -50.0
ROBOT_OFFSET_Y = -190.0
catch_z_axis = -30.0

# --- 파일 경로 설정 ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
URL_FILE_PATH = os.path.join(BASE_DIR, 'url.txt')
MATRIX_FILE_PATH = os.path.join(BASE_DIR, 'homography_matrix.json')

# --- 파일 로드 ---
try:
    with open(URL_FILE_PATH, 'r') as f:
        base_url = f.read().strip().rstrip('/')
        ESP32_URL = base_url + '/capture'
except FileNotFoundError:
    print(f"[에러] '{URL_FILE_PATH}' 파일을 찾을 수 없습니다.")
    exit()

try:
    with open(MATRIX_FILE_PATH, 'r') as f:
        matrix_list = json.load(f)
        homography_matrix = np.array(matrix_list)
except FileNotFoundError:
    print(f"[에러] '{MATRIX_FILE_PATH}' 파일을 찾을 수 없습니다.")
    exit()

# --- 역운동학 함수 ---
def inverse_kinematics(x, y, z):
    r_dist = math.sqrt(x**2 + y**2)
    dist = math.sqrt(r_dist**2 + z**2)
    
    if dist > (L1 + L2): return None, "거리 초과"
    
    theta_base = math.degrees(math.atan2(y, x))
    try:
        cos_alpha = (L1**2 + dist**2 - L2**2) / (2 * L1 * dist)
        cos_beta = (L1**2 + L2**2 - dist**2) / (2 * L1 * L2)
        
        if cos_alpha < -1 or cos_alpha > 1 or cos_beta < -1 or cos_beta > 1:
             return None, "각도 불가"

        alpha = math.acos(cos_alpha)
        beta = math.acos(cos_beta)
        target_elevation = math.atan2(z, r_dist)
        
        theta_shoulder = math.degrees(target_elevation + alpha)
        theta_elbow = math.degrees(beta)
        return (theta_base, theta_shoulder, theta_elbow), "성공"
    except ValueError:
        return None, "수학적 에러"

# [설정] 모터 각도 보정
def calculate_motor_angles(angles):
    if not angles: return None
    b, s, e = angles
    
    # 수정된 보정값
    # Base: 70 + 4 = 74
    final_base = int(b + 74) 
    
    # Shoulder: 107 - 2 = 105
    final_shoulder = int(s + 105)
    
    # Elbow: -49 + 7 = -42
    final_elbow = int(e - 42)
    
    final_base = max(29, min(160, final_base))
    final_shoulder = max(10, min(160, final_shoulder))
    final_elbow = max(10, min(120, final_elbow))
    
    return (final_base, final_shoulder, final_elbow)

# --- 객체 감지 함수 ---
def find_objects(image, mask, color_name, matrix, min_area, min_circularity):
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    results = []
    
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area > min_area:
            perimeter = cv2.arcLength(cnt, True)
            if perimeter == 0: continue
            circularity = (4 * np.pi * area) / (perimeter * perimeter)
            
            if circularity > min_circularity:
                M = cv2.moments(cnt)
                if M["m00"] != 0:
                    cX = int(M["m10"] / M["m00"])
                    cY = int(M["m01"] / M["m00"])
                    
                    pixel_point = np.array([[[cX, cY]]], dtype=np.float32)
                    real_point = cv2.perspectiveTransform(pixel_point, matrix)
                    paper_x = float(real_point[0][0][0])
                    paper_y = float(real_point[0][0][1])
                    
                    robot_x = paper_x + ROBOT_OFFSET_X
                    robot_y = -(paper_y + ROBOT_OFFSET_Y)
                    robot_z = catch_z_axis
                    
                    angles, status = inverse_kinematics(robot_x, robot_y, robot_z)
                    motor_vals = calculate_motor_angles(angles)
                    
                    results.append({
                        "color": color_name,
                        "motor_vals": motor_vals,
                        "robot_coords": (robot_x, robot_y, robot_z),
                        "status": status,
                        "pixel_coords": (cX, cY),
                        "contour": cnt
                    })
    return results

# --- 메인 실행 루프 ---
def main():
    print("\n--- 물체 감지 및 시각화 ---")
    print("ESP32 URL:", ESP32_URL)
    
    image = None
    
    # 1. 이미지 가져오기
    try:
        print(f" >> 이미지 요청 중...")
        response = requests.get(ESP32_URL, timeout=5)
        if response.status_code == 200:
            img_array = np.frombuffer(response.content, dtype=np.uint8)
            image = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            if image is not None:
                print(" >> 이미지 수신 성공!\n")
    except Exception as e:
        print(f"    연결 에러: {e}")
    
    if image is None:
        print("[실패] 이미지를 가져오지 못했습니다. 카메라 연결을 확인하세요.")
        return

    # 2. 이미지 처리
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    
    lower_green = np.array([49, 101, 35])
    upper_green = np.array([85, 255, 255])
    green_mask = cv2.inRange(hsv, lower_green, upper_green)
    
    lower_black = np.array([0, 0, 0])
    upper_black = np.array([180, 255, 50])
    black_mask = cv2.inRange(hsv, lower_black, upper_black)
    
    green_objs = find_objects(image, green_mask, "Green", homography_matrix, 300, 0.7)
    black_objs = find_objects(image, black_mask, "Black", homography_matrix, 200, 0.6)
    
    all_objs = green_objs + black_objs
    
    result_image = image.copy()

    # 3. 결과 시각화
    print("       [분석 결과]")
    
    if all_objs:
        for i, obj in enumerate(all_objs):
            color = obj['color']
            status = obj['status']
            rx, ry, rz = obj['robot_coords']
            cx, cy = obj['pixel_coords']
            cnt = obj['contour']
            
            print(f"{i+1}. 발견된 물체: [{color}]")
            if status == "성공":
                b, s, e = obj['motor_vals']
                print(f"   - 로봇 좌표 : X={rx:.1f}, Y={ry:.1f}, Z={rz:.1f}")
                print(f"   - 모터 각도 : (Base, Shoulder, Elbow) = ({b}, {s}, {e})")
                
                text_line1 = f"{color} (OK)"
                text_line2 = f"XYZ: {rx:.0f}, {ry:.0f}, {rz:.0f}"
                text_line3 = f"Ang: {b}, {s}, {e}"
                box_color = (0, 255, 0)
            else:
                print(f"   - 로봇 좌표 : X={rx:.1f}, Y={ry:.1f}, Z={rz:.1f}")
                print(f"   - 상태     : {status}")
                
                text_line1 = f"{color} (FAIL)"
                text_line2 = f"XYZ: {rx:.0f}, {ry:.0f}, {rz:.0f}"
                text_line3 = f"Status: {status}"
                box_color = (0, 0, 255)

            cv2.drawContours(result_image, [cnt], -1, box_color, 2)
            cv2.circle(result_image, (cx, cy), 5, (255, 0, 0), -1)

            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.5
            font_thick = 1
            
            cv2.putText(result_image, text_line1, (cx - 40, cy + 20), font, font_scale, box_color, font_thick)
            cv2.putText(result_image, text_line2, (cx - 40, cy + 40), font, font_scale, box_color, font_thick)
            cv2.putText(result_image, text_line3, (cx - 40, cy + 60), font, font_scale, box_color, font_thick)

    else:
        print(" >> 감지된 물체가 없습니다.")
        cv2.putText(result_image, "No Objects Found", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
    
    # 4. [수정됨] 윈도우 창 띄우기 및 키 입력 처리
    print("\n   [키보드 조작 안내]")
    print("   'c' 키 : 현재 화면 저장 (Capture)")
    print("   'q' 키 : 프로그램 종료 (Quit)")

    cv2.imshow("Detection Result", result_image)

    while True:
        key = cv2.waitKey(0) & 0xFF  # 키 입력 대기 (무한 대기)

        if key == ord('q'):
            print("\n >> 프로그램을 종료합니다.")
            break
        
        elif key == ord('c'):
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"capture_{timestamp}.jpg"
            cv2.imwrite(filename, result_image)
            print(f" >> [저장 완료] {filename}")

    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()