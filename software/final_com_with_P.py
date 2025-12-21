import cv2
import numpy as np
import requests
import json
import time
import os
import math
import serial


# --- 아두이노 포트 설정 ---
SERIAL_PORT = 'COM4' 
BAUD_RATE = 115200

# --- 로봇 링크 길이 ---
L1 = 82.0
L2 = 81.0

# --- 로봇 오프셋 ---
ROBOT_OFFSET_X = -50.0
ROBOT_OFFSET_Y = -190.0
catch_z_axis = -30.0

# --- 분류 위치 ---
DROP_GREEN = (144, 137, 23)
DROP_BLACK = (108, 137, 42)

# --- PID 제어 관련 상수 ---
Kp = 0.15
MAX_SPEED = 4.0
DT = 0.03
THRESHOLD = 1.0

# --- 파일 경로 설정 ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
URL_FILE_PATH = os.path.join(BASE_DIR, 'url.txt')
MATRIX_FILE_PATH = os.path.join(BASE_DIR, 'homography_matrix.json')

# --- 전역 변수: 현재 로봇 상태 저장 (Base, Shoulder, Elbow, Claw) ---
g_current_angles = [89.0, 134.0, 42.0, 30.0]


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

# 오프셋 보정
def calculate_motor_angles(angles):
    if not angles: return None
    b, s, e = angles

    final_base = int(b + 74)
    final_shoulder = int(s + 105)
    final_elbow = int(e - 42)
    
    final_base = max(29, min(160, final_base))
    final_shoulder = max(10, min(160, final_shoulder))
    final_elbow = max(10, min(120, final_elbow))
    
    return (final_base, final_shoulder, final_elbow)

# --- P-제어 기반 부드러운 이동 함수 ---
def move_smoothly_pid(target_b, target_s, target_e, target_c, arrival_delay=0.5):
    global g_current_angles
    
    targets = [target_b, target_s, target_e, target_c]
    
    while True:
        all_arrived = True
        
        # 각 관절별로 P제어 계산
        for i in range(4):
            error = targets[i] - g_current_angles[i]
            
            # 오차가 허용 범위보다 크면 이동 필요
            if abs(error) > THRESHOLD:
                all_arrived = False
                
                # P 제어: 오차에 비례하여 이동량 결정
                delta = error * Kp
                
                # 속도 제한
                if delta > MAX_SPEED: 
                    delta = MAX_SPEED
                if delta < -MAX_SPEED: 
                    delta = -MAX_SPEED
                
                g_current_angles[i] += delta
            else:
                # 거의 도달했으면 목표값으로 강제 고정
                g_current_angles[i] = targets[i]

        # 아두이노로 전송
        send_base = int(g_current_angles[0])
        send_shoulder = int(g_current_angles[1])
        send_elbow = int(g_current_angles[2])
        send_claw = int(g_current_angles[3])
        
        command = f"{send_base},{send_shoulder},{send_elbow},{send_claw}\n"
        
        if ser:
            ser.write(command.encode())
        
        # 목표 도달 시 루프 종료
        if all_arrived:
            break
            
        # 제어 주기 대기
        time.sleep(DT)

    # 이동 완료 후 안정화 대기
    if arrival_delay > 0:
        time.sleep(arrival_delay)

# --- 초기화나 급한 정지용 ---
def send_raw(base, shoulder, elbow, claw, delay=1.0):
    global g_current_angles
    # 현재 상태 즉시 업데이트
    g_current_angles = [float(base), float(shoulder), float(elbow), float(claw)]
    
    command = f"{base},{shoulder},{elbow},{claw}\n"
    print(f" >> 즉시 이동: {command.strip()}")
    if ser:
        ser.write(command.encode())
        time.sleep(delay)

# --- Pick and Place ---
def pick_and_place(color_name, target_coords):
    if not target_coords: return
    
    tx, ty, tz = target_coords
    
    # 접근 준비 위치 계산
    approach_dist = 50.0 
    start_x = tx - approach_dist
    
    angles_start, status_start = inverse_kinematics(start_x, ty, tz)
    
    if status_start != "성공":
        print(" >> [경고] 접근 위치 오류.")
        return

    motor_start = calculate_motor_angles(angles_start)
    motor_target = calculate_motor_angles(inverse_kinematics(tx, ty, tz)[0])

    # 1. 홈 포지션
    print(" >> 홈으로 이동")
    move_smoothly_pid(89, 134, 42, 30, arrival_delay=0.2)

    # 2. 물체 왼쪽 측면 이동
    print(f" >> {color_name} 접근 준비...")
    move_smoothly_pid(*motor_start, 30, arrival_delay=0.5)

    # 3. 수평 진입
    print(" >> 수평 접근 중...")
    steps_slide = 20
    
    for i in range(1, steps_slide + 1):
        current_x = start_x + (approach_dist * (i / steps_slide))
        ik_angles, st = inverse_kinematics(current_x, ty, tz)
        
        if st == "성공":
            m_vals = calculate_motor_angles(ik_angles)
            move_smoothly_pid(*m_vals, 30, arrival_delay=0.0) 
    
    # 4. 물체 잡기 (최종 위치 확정)
    print(" >> 잡기")
    move_smoothly_pid(*motor_target, 0, arrival_delay=0.5)

    # 5. 들어올리기
    angles_lift, _ = inverse_kinematics(tx, ty, tz + 40)
    if angles_lift:
        motor_lift = calculate_motor_angles(angles_lift)
        move_smoothly_pid(*motor_lift, 0, arrival_delay=0.3)
    else:
        mb, ms, me = motor_target
        move_smoothly_pid(mb, ms - 25, me, 0, arrival_delay=0.3)

    # 6. 분류 위치로 이동
    if color_name == "Green":
        drop_coords = DROP_GREEN
    elif color_name == "Black":
        drop_coords = DROP_BLACK
    else:
        return

    db, ds, de = drop_coords
    
    print(f" >> {color_name} 분류 위치로 이동")
    move_smoothly_pid(db, ds, de, 0, arrival_delay=0.5)
    
    # 놓기
    move_smoothly_pid(db, ds, de, 30, arrival_delay=0.5)
    
    # 복귀
    move_smoothly_pid(89, 134, 42, 30, arrival_delay=0.5) 
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
    # 초기화: 홈 위치 이동
    send_raw(89, 134, 42, 30, delay=1.0)
    
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
            black_objs = find_objects(image, black_mask, "Black", homography_matrix, 200, 0.6)
            
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
            # 에러 발생 시 잠시 대기
            time.sleep(1)

if __name__ == "__main__":
    main()
