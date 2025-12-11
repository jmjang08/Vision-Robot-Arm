'''녹색/검은색 물체 검사 - 외곽선 제외하고 깔끔한 박스만 그리기 + 현재 폴더 저장'''
import cv2
import numpy as np
import requests
import json
import time
import os
from datetime import datetime


# --- 경로 및 설정 초기화 ---
# 현재 스크립트가 있는 폴더 경로
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
URL_FILE_PATH = os.path.join(BASE_DIR, 'url.txt')
MATRIX_FILE_PATH = os.path.join(BASE_DIR, 'homography_matrix.json')

# URL로부터 이미지 읽기
try:
    with open(URL_FILE_PATH, 'r') as f:
        base_url = f.read().strip().rstrip('/')
        ESP32_URL = base_url + '/capture'
    print(f"URL 설정 완료: {ESP32_URL}")
except FileNotFoundError:
    print(f"오류: '{URL_FILE_PATH}' 파일을 찾을 수 없습니다.")
    exit()

# 변환 행렬 불러오기
try:
    with open(MATRIX_FILE_PATH, 'r') as f:
        matrix_list = json.load(f)
        homography_matrix = np.array(matrix_list)
    print(f"변환 행렬 로드 성공")
except FileNotFoundError:
    print(f"오류: '{MATRIX_FILE_PATH}'을 찾을 수 없습니다.")
    exit()


# --- 객체 감지 함수 ---
def find_and_draw_contours(image, mask, color_name, draw_color_bgr, matrix, min_area, min_circularity):
    """
    마스크에서 조건(면적, 원형도)을 통과하는 물체를 찾아 실제 좌표 리스트를 반환합니다.
    """
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    found_coordinates_list = []

    for cnt in contours:
        area = cv2.contourArea(cnt)
        
        if area > min_area:
            perimeter = cv2.arcLength(cnt, True)
            if perimeter == 0: continue
            
            circularity = (4 * np.pi * area) / (perimeter * perimeter)
            
            if circularity > min_circularity:
                x, y, w, h = cv2.boundingRect(cnt)
                M = cv2.moments(cnt)

                if M["m00"] != 0:
                    pixel_cX = int(M["m10"] / M["m00"])
                    pixel_cY = int(M["m01"] / M["m00"])

                    pixel_point = np.array([[[pixel_cX, pixel_cY]]], dtype=np.float32)
                    real_point = cv2.perspectiveTransform(pixel_point, matrix)
                    
                    real_X = float(real_point[0][0][0])
                    real_Y = float(real_point[0][0][1])
                    real_coords = (round(real_X, 1), round(real_Y, 1))

                    # --- 화면 그리기 ---                    
                    cv2.rectangle(image, (x, y), (x + w, y + h), draw_color_bgr, 2)
                    cv2.circle(image, (pixel_cX, pixel_cY), 5, draw_color_bgr, -1)

                    text = f"{color_name} ({real_coords[0]}, {real_coords[1]})"         # Green (5, 3)
                    cv2.putText(image, text, (x, y - 10), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, draw_color_bgr, 2)

                    found_coordinates_list.append(real_coords)          
    return found_coordinates_list


# --- 메인 코드 ---
try:
    print("이미지 요청 중...")
    response = requests.get(ESP32_URL, timeout=5)
    if response.status_code != 200:
        print("이미지 수신 실패")
        exit()

    img_array = np.frombuffer(response.content, dtype=np.uint8)
    image = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    if image is None: exit()
            
    annotated_image = image.copy()
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

    # --- 색상 범위 ---
    lower_green = np.array([49, 101, 35])
    upper_green = np.array([85, 255, 255])

    lower_black = np.array([0, 0, 0])
    upper_black = np.array([180, 255, 50])

    green_mask = cv2.inRange(hsv, lower_green, upper_green)
    black_mask = cv2.inRange(hsv, lower_black, upper_black)

    # --- 필터 값 설정 ---
    GREEN_MIN_AREA = 300
    GREEN_MIN_CIRCULARITY = 0.7
    
    BLACK_MIN_AREA = 100
    BLACK_MIN_CIRCULARITY = 0.5

    # 객체 찾기 함수 호출
    green_objects = find_and_draw_contours(
        annotated_image, green_mask, "Green", (0, 255, 0), homography_matrix,
        GREEN_MIN_AREA, GREEN_MIN_CIRCULARITY
    )
    black_objects = find_and_draw_contours(
        annotated_image, black_mask, "Black", (0, 0, 255), homography_matrix,
        BLACK_MIN_AREA, BLACK_MIN_CIRCULARITY
    )

    # 콘솔 출력
    if green_objects:
        coords_str = str(green_objects)[1:-1] 
        print(f"▶ 발견된 녹색 물체 ({len(green_objects)}개): {coords_str}")
    else:
        print("▷ 녹색 물체 없음")
        
    if black_objects:
        coords_str = str(black_objects)[1:-1]
        print(f"▶ 발견된 검은색 물체 ({len(black_objects)}개): {coords_str}")
    else:
        print("▷ 검은색 물체 없음")

    # 결과 화면 표시
    cv2.imshow("Result", annotated_image)

    print("화면이 정상적으로 띄워졌습니다.")
    print("해당 화면을 저장하려면 'c', 창을 닫으려면 'q'를 누르시오")

    while True:
        key = cv2.waitKey(0) & 0xFF
        if key == ord('c'):
            # 현재 시스템 시간(KST) 가져오기
            now = datetime.now()
            # 포맷 지정: YYYYMMDD_HHMMSS (예: 20251122_235010)
            time_str = now.strftime("%Y%m%d_%H%M%S")
            
            filename = f"detectedIMG_{time_str}.png"
            path = os.path.join(BASE_DIR, filename)
            
            cv2.imwrite(path, annotated_image)
            print(f"저장됨: {path}")
            
        elif key == ord('q'):
            break

    cv2.destroyAllWindows()

except Exception as e:
    print(f"오류 발생: {e}")
