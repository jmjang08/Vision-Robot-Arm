'''특정 색의 물체의 마스크 알아내기 (HSV Tuner)'''
import cv2
import numpy as np
import requests
import os


# --- 1. 경로 및 URL 설정 ---
# 현재 파일 위치 기준
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
URL_FILE_PATH = os.path.join(BASE_DIR, 'url.txt')

# url.txt 읽기
try:
    with open(URL_FILE_PATH, 'r') as f:
        base_url = f.read().strip().rstrip('/')
        ESP32_URL = base_url + '/capture'
    print(f"URL 설정 완료: {ESP32_URL}")
except FileNotFoundError:
    print(f"오류: '{URL_FILE_PATH}' 파일을 찾을 수 없습니다.")
    print("같은 폴더에 url.txt를 만들어주세요.")
    exit()

# --- 2. 트랙바 초기화 ---
def nothing(x):
    pass

cv2.namedWindow("HSV Tuner")
cv2.createTrackbar("H_min", "HSV Tuner", 35, 179, nothing)
cv2.createTrackbar("H_max", "HSV Tuner", 85, 179, nothing)
cv2.createTrackbar("S_min", "HSV Tuner", 50, 255, nothing)
cv2.createTrackbar("S_max", "HSV Tuner", 255, 255, nothing)
cv2.createTrackbar("V_min", "HSV Tuner", 50, 255, nothing)
cv2.createTrackbar("V_max", "HSV Tuner", 255, 255, nothing)

print("--- HSV 튜너 시작 ---")
print("1. Mask 창을 보면서 물체가 '흰색'이 되도록 조절하세요.")
print("2. 배경이나 잡음은 '검은색'이 되도록 조절하세요.")
print("3. 완료되면 'q'를 눌러 종료하세요.")

# 변수 초기화
h_min, s_min, v_min = 0, 0, 0
h_max, s_max, v_max = 179, 255, 255

while True:
    try:
        # --- 이미지 가져오기 ---
        response = requests.get(ESP32_URL, timeout=5)
        if response.status_code != 200:
            print("ESP32 통신 대기 중...")
            continue
            
        img_array = np.frombuffer(response.content, dtype=np.uint8)
        image = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        
        if image is None:
            continue

        # --- 이미지 처리 ---
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        # 트랙바 값 읽기
        h_min = cv2.getTrackbarPos("H_min", "HSV Tuner")
        h_max = cv2.getTrackbarPos("H_max", "HSV Tuner")
        s_min = cv2.getTrackbarPos("S_min", "HSV Tuner")
        s_max = cv2.getTrackbarPos("S_max", "HSV Tuner")
        v_min = cv2.getTrackbarPos("V_min", "HSV Tuner")
        v_max = cv2.getTrackbarPos("V_max", "HSV Tuner")

        # 마스크 생성
        lower_range = np.array([h_min, s_min, v_min])
        upper_range = np.array([h_max, s_max, v_max])
        mask = cv2.inRange(hsv, lower_range, upper_range)
        
        # 결과 합성
        result = cv2.bitwise_and(image, image, mask=mask)

        # --- 화면 출력 ---
        cv2.imshow("Mask (White=Select, Black=Ignore)", mask)
        cv2.imshow("Result (Preview)", result)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break

    except requests.exceptions.RequestException:
        # 연결 끊김 등의 에러는 무시하고 재시도 (터미널 도배 방지)
        break
    except KeyboardInterrupt:
        break

cv2.destroyAllWindows()

# --- 최종 값 출력 ---
print("\n" + "="*30)
print(" [최종 튜닝 결과] ")
print(" 아래 코드를 복사해서 사용하세요:")
print("="*30)
print(f"lower_color = np.array([{h_min}, {s_min}, {v_min}])")
print(f"upper_color = np.array([{h_max}, {s_max}, {v_max}])")
print("="*30)
