import cv2
import numpy as np
import requests
import json
import time
import os
import math
import serial


# --- [사용자 설정] 아두이노 포트 설정 ---
SERIAL_PORT = 'COM4' 
BAUD_RATE = 115200

# --- [설정] 로봇 링크 길이 ---
L1 = 82.0
L2 = 81.0

# --- [설정] 로봇 오프셋 ---
ROBOT_OFFSET_X = -50.0
ROBOT_OFFSET_Y = -190.0
catch_z_axis = -30.0

# --- [설정] 분류 위치 (Drop Zone) ---
DROP_GREEN = (145, 139, 28)
DROP_BLACK = (109, 146, 42)

# --- 파일 경로 설정 ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
URL_FILE_PATH = os.path.join(BASE_DIR, 'url.txt')
MATRIX_FILE_PATH = os.path.join(BASE_DIR, 'homography_matrix.json')

# --- 시리얼 포트 연결 ---
try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    time.sleep(2)
    print(f"아두이노 연결 성공: {SERIAL_PORT}")
except Exception as e:
    print(f"아두이노 연결 실패: {e}")
    print("가상 모드로 실행합니다.")
    ser = None

# --- 파일 로드 ---
try:
    with open(URL_FILE_PATH, 'r') as f:
        base_url = f.read().strip().rstrip('/')
        ESP32_URL = base_url + '/capture'
except FileNotFoundError:
    exit()

try:
    with open(MATRIX_FILE_PATH, 'r') as f:
        matrix_list = json.load(f)
        homography_matrix = np.array(matrix_list)
except FileNotFoundError:
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

# [수정됨] 나사 조임 후 오프셋 재보정 (Base -12, Shoulder +16, Elbow +2)
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

# --- 로봇 제어 함수 ---
def send_to_arduino(base, shoulder, elbow, claw, delay=1.0):
    command = f"{base},{shoulder},{elbow},{claw}\n"
    print(f" >> 전송: {command.strip()} (대기 {delay}s)")
    if ser:
        ser.write(command.encode())
        time.sleep(delay)

# ---------------------------------------------------------
# [pick_and_place: 수평 접근(왼쪽 진입) 유지]
# ---------------------------------------------------------
def pick_and_place(color_name, target_coords):
    """ 
    target_coords: (x, y, z) - 물체의 로봇 기준 좌표
    """
    if not target_coords: return
    
    tx, ty, tz = target_coords
    
    # 1. 접근 준비 위치 계산 (물체보다 왼쪽으로 50mm 떨어진 지점)
    approach_dist = 50.0 # 50mm (5cm) 뒤에서 접근
    start_x = tx - approach_dist
    
    # 시작점 역운동학 계산
    angles_start, status_start = inverse_kinematics(start_x, ty, tz)
    
    if status_start != "성공":
        print(" >> [경고] 접근 시작 위치가 로봇 범위를 벗어났습니다. 작업을 중단하거나 기존 방식으로 시도하세요.")
        return

    motor_start = calculate_motor_angles(angles_start)
    motor_target = calculate_motor_angles(inverse_kinematics(tx, ty, tz)[0]) # 최종 위치

    # ---------------------------------------------------------
    # [1단계: 물체 잡기 - 수평 접근 (Slide Approach)]
    # ---------------------------------------------------------

    # 1. 홈 포지션
    send_to_arduino(89, 134, 42, 30, delay=0.5)

    # 2. 물체 왼쪽(뒤) 5cm 위치로 이동 (높이는 물체 높이 tz 유지)
    print(f" >> {color_name} 발견! 왼쪽 측면({start_x:.1f}, {ty:.1f})으로 이동하여 조준...")
    # Claw를 벌린 상태(30)로 이동
    send_to_arduino(*motor_start, 30, delay=1.5)

    # 3. 천천히 수평으로 전진 (Slide)
    print(" >> 물체를 향해 수평으로 접근합니다...")
    steps_slide = 30  # 50단계로 나누어 접근
    
    for i in range(1, steps_slide + 1):
        # 현재 X 좌표 계산 (선형 보간)
        current_x = start_x + (approach_dist * (i / steps_slide))
        
        # 이동할 좌표에 대한 역운동학 계산
        ik_angles, st = inverse_kinematics(current_x, ty, tz)
        
        if st == "성공":
            m_vals = calculate_motor_angles(ik_angles)
            # 딜레이를 주어 안정적으로 연결
            send_to_arduino(*m_vals, 30, delay=0.05)
    
    # 4. 물체 잡기 (최종 위치 도달 상태)
    print(" >> 잡기 시도")
    send_to_arduino(*motor_target, 0, delay=0.8)

    # 5. 들어올리기 (Lift) - 수직으로 살짝 들기
    #    현재 위치에서 Z만 30mm 높임
    angles_lift, _ = inverse_kinematics(tx, ty, tz + 30)
    if angles_lift:
        motor_lift = calculate_motor_angles(angles_lift)
        send_to_arduino(*motor_lift, 0, delay=0.5)
    else:
        # IK 실패시 단순히 어깨만 들어올림
        mb, ms, me = motor_target
        send_to_arduino(mb, ms - 20, me, 0, delay=0.5)

    # ---------------------------------------------------------
    # [2단계: 물체 놓기 (기존 유지)]
    # ---------------------------------------------------------
    if color_name == "Green":
        drop_coords = DROP_GREEN
    elif color_name == "Black":
        drop_coords = DROP_BLACK
    else:
        return

    db, ds, de = drop_coords
    
    print(f" >> {color_name} 분류 위치로 이동")
    send_to_arduino(db, ds, de, 0, delay=1.0) 
    send_to_arduino(db, ds, de, 30, delay=0.5) # 놓기
    
    send_to_arduino(89, 134, 42, 30, delay=1.0) # 복귀
    print(" >> 작업 완료!\n")

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
                        "center": (cX, cY)
                    })
    return results


# --- 메인 실행 루프 ---
def main():
    send_to_arduino(89, 134, 42, 30, delay=1.0)
    
    while True:
        print("\n[대기 중] Enter: 작업 시작 ('q': 종료)")
        key = input()
        if key == 'q': break

        try:
            response = requests.get(ESP32_URL, timeout=5)
            if response.status_code != 200: continue
            img_array = np.frombuffer(response.content, dtype=np.uint8)
            image = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            if image is None: continue
            
            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            
            lower_green = np.array([49, 101, 35])
            upper_green = np.array([85, 255, 255])
            green_mask = cv2.inRange(hsv, lower_green, upper_green)
            
            lower_black = np.array([0, 0, 0])
            upper_black = np.array([180, 255, 50])
            black_mask = cv2.inRange(hsv, lower_black, upper_black)
            
            green_objs = find_objects(image, green_mask, "Green", homography_matrix, 300, 0.7)
            black_objs = find_objects(image, black_mask, "Black", homography_matrix, 300, 0.7)
            
            all_objs = green_objs + black_objs
            
            if not all_objs:
                print(" >> 감지된 물체가 없습니다.")
                continue
            
            target_processed = False
            for obj in all_objs:
                if obj['status'] == "성공":
                    print(f" >> 발견: {obj['color']} ({obj['robot_coords']})")
                    pick_and_place(obj['color'], obj['robot_coords'])
                    target_processed = True
                    break 
            
            if not target_processed:
                print(" >> 물체는 있으나 도달 불가합니다.")

        except Exception as e:
            print(f"에러 발생: {e}")

if __name__ == "__main__":
    main()