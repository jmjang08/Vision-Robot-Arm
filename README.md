# Vision-Based Pick & Place Robot Arm

Project for a university graduation thesis in 2025.<br>
This project implements a **vision-based pick & place system** for a **meArm-style robotic arm** using an **ESP32 camera**, **OpenCV**, **homography calibration**, and **inverse kinematics**.
Detected objects are converted from camera pixel coordinates into real-world coordinates, then into joint angles, and finally sent to an Arduino to physically move the robot arm.

---

## ✨ Features

* ESP32 Camera WebServer image acquisition
* Perspective (homography) calibration from camera → real plane
* HSV-based color detection (green & black objects)
* Object filtering using area and circularity
* Inverse kinematics for a 3-DOF meArm-style robot
* Pick & place logic with predefined drop zones
* Optional **P-control (proportional control)** for smooth motion
* Serial communication with Arduino (`.ino` firmware)

---

## 🧠 System Overview

```
ESP32 Camera
     ↓
CameraWebServer (image stream)
     ↓
a_*.py  → Calibration & color tuning
     ↓
(b_color_detect_and_IK.py → Object detection & coordinate conversion)
     ↓
final_com_no_PID.py → motion planning
     /
final_com_with_P.py → IK + motion planning
     ↓
Serial (USB)
     ↓
Arduino (final_arm.ino)
     ↓
meArm Robot Arm
```

---

## ⚙️ Hardware Requirements

* meArm-style 4-DOF robotic arm + custom gripper(hardware folder) <br>
  custom gripper: Print all .stl files inside hardware folder. Files labeled x2 require two copies.
* Arduino UNO
* SG90 or MG90 *4 (Base, Shoulder, Elbow, Claw)
* ESP32-CAM AI thinker
* Arduino cable (PC ↔ Arduino)
* Stable lighting (for color detection)

---

## 🧩 Software Requirements

* Python 3.8+
* Arduino IDE

---

## 🚀 Setup & Usage

### 1. ESP32 Camera Setup

* Flash **CameraWebServer** example to the ESP32-CAM<br>
Enter the Wi-Fi name and password into `CameraWebServer.ino`.
* Confirm live image access via browser
* ESP32-CAM should be able to see robot arm and workspace entirely<br>
(I used two sheets of white A4 paper stacked together as my workspace.)<br>
<img src="./img/workspace_setting.JPG" width="300">
* Paste the camera URL into `url.txt`

```
# Example:
http://192.168.x.xxx
```

---

### 2. Camera Calibration (Homography)

Run:

```bash
python a_calibrate_homography.py
```

* Click **4 corner points** of workspace in this order:

  1. Top-Left
  2. Top-Right
  3. Bottom-Left
  4. Bottom-Right
* A `homography_matrix.json` file will be generated

This maps camera pixels → real-world coordinates (mm).

---

### 3. Color Tuning (HSV)

Tune HSV values for your environment:

```bash
python a_hsv_tuner.py
```

* Adjust trackbars until the object is **white** and the background **black**
* Copy the printed HSV ranges into the detection scripts if needed

---

### 4. Detection & IK Test (Optional)

```bash
python b_color_detect_and_IK.py
```

* Detects objects
* Converts to robot coordinates
* Calculates joint angles (no physical movement)

Useful for debugging geometry before motion.

---

### 5. Arduino Firmware

* Open `final_arm.ino` in Arduino IDE
* Upload to Arduino
* Confirm servo directions and neutral positions

---

### 6. Run the Full Pick & Place System

#### Without smooth control:

```bash
python final_com_no_PID.py
```

#### With P-control (recommended):

```bash
python final_com_with_P.py
```

Controls:

* **Enter** → start pick & place
* **q** → quit program

---

## 🦾 Motion Control Details

* **Inverse Kinematics**

  * 2-link planar arm (L1, L2)
  * Base rotation + shoulder + elbow
* **P-Control (final_com_with_P.py)**

  * Smooth joint interpolation
  * Adjustable `Kp`, speed limits, and thresholds
* **Pick Strategy**

  * Horizontal side approach
  * Slide motion toward object
  * Lift → move → drop → return home

---

## 📌 Drop Zones

Predefined joint angles for sorting:

```python
DROP_GREEN = (base, shoulder, elbow)
DROP_BLACK = (base, shoulder, elbow)
```

These can be customized per setup.
Use robotarm_manual to copy the angles

---

## ⚠️ Notes & Tips

* Lighting stability is critical for HSV detection
* Calibrate homography **after camera position is fixed**
* Servo offsets must be tuned per robot

---

## 📜 License

This project is released under the **MIT License**.
Feel free to use, modify, and share.

---

## 🙌 Acknowledgements

* OpenCV
* ESP32 CameraWebServer example
* meArm community