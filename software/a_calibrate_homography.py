import cv2
import numpy as np
import json
import urllib.request
import os


# Path settings
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
URL_PATH = os.path.join(BASE_DIR, 'url.txt')
SAVE_PATH = os.path.join(BASE_DIR, 'homography_matrix.json')

# Read image from URL
with open(URL_PATH, 'r') as f:
    url = f.read().strip().rstrip('/') + '/capture'

# Download image
print(f"Connecting to: {url}")
with urllib.request.urlopen(url) as resp:
    img_array = np.array(bytearray(resp.read()), dtype=np.uint8)
    img = cv2.imdecode(img_array, -1)

if img is None:
    print("Failed to load image")
    exit()

# Mouse click settings
points = []
img_disp = img.copy()

def on_mouse(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN and len(points) < 4:
        points.append([x, y])
        cv2.circle(img_disp, (x, y), 5, (0, 0, 255), -1)
        cv2.putText(
            img_disp,
            str(len(points)),
            (x + 5, y + 5),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 0, 255),
            2
        )
        cv2.imshow("Calibration", img_disp)

cv2.namedWindow("Calibration")
cv2.setMouseCallback("Calibration", on_mouse)
cv2.imshow("Calibration", img_disp)

print("Click four points (top-left → top-right → bottom-left → bottom-right), then press Enter.")

# Wait loop
while True:
    key = cv2.waitKey(1) & 0xFF
    if key == 13 and len(points) == 4:  # Enter
        break
    elif key == 27:  # ESC
        exit()

# Compute and save homography matrix
real_pts = np.array([
    [0, 0],
    [388, 0],
    [0, 297],
    [388, 297]
], dtype=np.float32)

matrix, _ = cv2.findHomography(
    np.array(points, dtype=np.float32),
    real_pts
)

with open(SAVE_PATH, 'w') as f:
    json.dump(matrix.tolist(), f, indent=4)  # Overwrites existing matrix file if present

print(f"Saved successfully: {SAVE_PATH}")
cv2.destroyAllWindows()
