'''Find a mask for a specific colored object (HSV Tuner)'''
import cv2
import numpy as np
import requests
import os


# --- 1. Path and URL setup ---
# Based on current file location
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
URL_FILE_PATH = os.path.join(BASE_DIR, 'url.txt')

# Read url.txt
try:
    with open(URL_FILE_PATH, 'r') as f:
        base_url = f.read().strip().rstrip('/')
        ESP32_URL = base_url + '/capture'
    print(f"URL setup completed: {ESP32_URL}")
except FileNotFoundError:
    print(f"Error: '{URL_FILE_PATH}' file not found.")
    print("Please create url.txt in the same folder.")
    exit()

# --- 2. Trackbar initialization ---
def nothing(x):
    pass

# Color select
COLOR_PRESET = {
    "green":      (35, 85, 50, 255, 50, 255),
    "dark grey":  (0, 179, 0, 255, 0, 60),
}

mode_select = input("Choose color (green / dark grey): ").strip().lower()
if mode_select in COLOR_PRESET:
    color_H_min, color_H_max, color_S_min, color_S_max, color_V_min, color_V_max = COLOR_PRESET[mode_select]
else:
    print("Undefined color.")

cv2.namedWindow("HSV Tuner")
cv2.createTrackbar("H_min", "HSV Tuner", color_H_min, 179, nothing)
cv2.createTrackbar("H_max", "HSV Tuner", color_H_max, 179, nothing)
cv2.createTrackbar("S_min", "HSV Tuner", color_S_min, 255, nothing)
cv2.createTrackbar("S_max", "HSV Tuner", color_S_max, 255, nothing)
cv2.createTrackbar("V_min", "HSV Tuner", color_V_min, 255, nothing)
cv2.createTrackbar("V_max", "HSV Tuner", color_V_max, 255, nothing)

print("--- HSV Tuner Started ---")
print("1. Adjust so that the object becomes 'white' in the Mask window.")
print("2. Adjust so that the background and noise become 'black'.")
print("3. Press 'q' to quit when finished.")

# Variable initialization
color_h_min, s_min, v_min = 0, 0, 0
h_max, s_max, v_max = 179, 255, 255

while True:
    try:
        # --- Fetch image ---
        response = requests.get(ESP32_URL, timeout=5)
        if response.status_code != 200:
            print("Waiting for ESP32 communication...")
            continue
            
        img_array = np.frombuffer(response.content, dtype=np.uint8)
        image = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        
        if image is None:
            continue

        # --- Image processing ---
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        # Read trackbar values
        color_h_min = cv2.getTrackbarPos("H_min", "HSV Tuner")
        h_max = cv2.getTrackbarPos("H_max", "HSV Tuner")
        s_min = cv2.getTrackbarPos("S_min", "HSV Tuner")
        s_max = cv2.getTrackbarPos("S_max", "HSV Tuner")
        v_min = cv2.getTrackbarPos("V_min", "HSV Tuner")
        v_max = cv2.getTrackbarPos("V_max", "HSV Tuner")

        # Create mask
        lower_range = np.array([color_h_min, s_min, v_min])
        upper_range = np.array([h_max, s_max, v_max])
        mask = cv2.inRange(hsv, lower_range, upper_range)
        
        # Combine result
        result = cv2.bitwise_and(image, image, mask=mask)

        # --- Display ---
        cv2.imshow("Mask (White=Select, Black=Ignore)", mask)
        cv2.imshow("Result (Preview)", result)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break

    except requests.exceptions.RequestException:
        # Ignore connection errors and retry (prevent terminal spam)
        break
    except KeyboardInterrupt:
        break

cv2.destroyAllWindows()

# --- Final values output ---
print("\n" + "="*30)
print(" [Final Tuning Result] ")
print(" Copy and use the code below:")
print("="*30)
print(f"lower_color = np.array([{color_h_min}, {s_min}, {v_min}])")
print(f"upper_color = np.array([{h_max}, {s_max}, {v_max}])")
print("="*30)
