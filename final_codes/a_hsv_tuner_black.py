import cv2
import numpy as np
import requests
import os

# --- 1. 경로 및 URL 설정 ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
URL_FILE_PATH = os.path.join(BASE_DIR, 'url.txt')

try:
    with open(URL_FILE_PATH, 'r') as f:
        base_url = f.read().strip().rstrip('/')
        ESP32_URL = base_url + '/capture'
    print(f"URL 설정 완료: {ESP32_URL}")
except FileNotFoundError:
    print(f"오류: '{URL_FILE_PATH}' 파일을 찾을 수 없습니다.")
    exit()

# --- 2. 트랙바 초기화 (검은색 감지용 초기값) ---
def nothing(x):
    pass

cv2.namedWindow("HSV Tuner")

# 검은색은 Hue(색상)와 Saturation(채도)에 상관없이 Value(명도)가 낮은 것입니다.
# 따라서 H와 S는 전체 범위를 잡고, V_max를 낮게 시작합니다.

cv2.createTrackbar("H_min", "HSV Tuner", 0, 179, nothing)   # 0부터 시작
cv2.createTrackbar("H_max", "HSV Tuner", 179, 179, nothing) # 전체 범위
cv2.createTrackbar("S_min", "HSV Tuner", 0, 255, nothing)   # 0부터 시작
cv2.createTrackbar("S_max", "HSV Tuner", 255, 255, nothing) # 전체 범위
cv2.createTrackbar("V_min", "HSV Tuner", 0, 255, nothing)   # 0 (완전 어두움)
cv2.createTrackbar("V_max", "HSV Tuner", 60, 255, nothing)  # 60 (어두운 회색 정도, 조절 필요)

print("--- HSV 튜너 시작 (검은색 모드) ---")
print("1. V_max (명도 최대값)을 조절하여 검은색 물체만 잡히도록 하세요.")
print("2. 주변 그림자도 검은색으로 인식될 수 있으니 조명에 주의하세요.")
print("3. 완료되면 'q'를 눌러 종료하세요.")

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
        # 마스크가 너무 작게 보이면 cv2.resize로 키울 수 있습니다.
        cv2.imshow("Mask (White=Select, Black=Ignore)", mask)
        cv2.imshow("Result (Preview)", result)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break

    except requests.exceptions.RequestException:
        break
    except KeyboardInterrupt:
        break

cv2.destroyAllWindows()

# --- 최종 값 출력 ---
print("\n" + "="*30)
print(" [최종 튜닝 결과 (Black Detection)] ")
print(" 아래 코드를 복사해서 사용하세요:")
print("="*30)
print(f"lower_black = np.array([{h_min}, {s_min}, {v_min}])")
print(f"upper_black = np.array([{h_max}, {s_max}, {v_max}])")
print("="*30)