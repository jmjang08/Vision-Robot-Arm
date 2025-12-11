import cv2
import numpy as np
import json
import urllib.request
import os


# 경로 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
URL_PATH = os.path.join(BASE_DIR, 'url.txt')
SAVE_PATH = os.path.join(BASE_DIR, 'homography_matrix.json')

# URL로부터 이미지 읽기
with open(URL_PATH, 'r') as f:
    url = f.read().strip().rstrip('/') + '/capture'

# 이미지 다운로드
print(f"접속 중: {url}")
with urllib.request.urlopen(url) as resp:
    img_array = np.array(bytearray(resp.read()), dtype=np.uint8)
    img = cv2.imdecode(img_array, -1)

if img is None:
    print("이미지 로드 실패")
    exit()

# 마우스 클릭 설정
points = []
img_disp = img.copy()

def on_mouse(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN and len(points) < 4:
        points.append([x, y])
        cv2.circle(img_disp, (x, y), 5, (0, 0, 255), -1)
        cv2.putText(img_disp, str(len(points)), (x+5, y+5), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        cv2.imshow("Calibration", img_disp)

cv2.namedWindow("Calibration")
cv2.setMouseCallback("Calibration", on_mouse)
cv2.imshow("Calibration", img_disp)

print("네 점 클릭(좌상->우상->좌하->우하) 후 Enter 키를 누르세요.")

# 대기 루프
while True:
    key = cv2.waitKey(1) & 0xFF
    if key == 13 and len(points) == 4:  # Enter
        break
    elif key == 27:  # ESC
        exit()

# 행렬 계산 및 저장
real_pts = np.array([[0,0],
                     [388,0],
                     [0,297],
                     [388,297]], dtype=np.float32)

matrix, _ = cv2.findHomography(np.array(points, dtype=np.float32), real_pts)

with open(SAVE_PATH, 'w') as f:
    json.dump(matrix.tolist(), f, indent=4)     # 기존 행렬 파일 있더라도 덮어씌워짐

print(f"저장 완료: {SAVE_PATH}")
cv2.destroyAllWindows()