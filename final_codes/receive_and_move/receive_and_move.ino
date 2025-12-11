/*
  Serial Robot Arm Control
  파이썬에서 계산된 좌표(각도)를 시리얼로 입력받아 이동하는 코드
  
  입력 형식: base,shoulder,elbow,claw (예: 90,120,40,30)
*/

#include <Servo.h>

// --- 핀 및 설정 (robotarm_manual.ino 참조) ---
#define PIN_BASE      11
#define PIN_SHOULDER  10  // Manual 코드의 'Left Servo'
#define PIN_ELBOW     9   // Manual 코드의 'Right Servo'
#define PIN_CLAW      5

// --- 각도 제한 (하드웨어 보호용) ---
// Manual 코드의 Min/Max 값 참조 
const int BASE_MIN = 0;    const int BASE_MAX = 180;
const int SHL_MIN = 10;    const int SHL_MAX = 160;
const int ELB_MIN = 10;    const int ELB_MAX = 120;
const int CLAW_CLOSE = 0;  const int CLAW_OPEN = 30;

Servo base, shoulder, elbow, claw;

// 현재 각도 저장 변수 (초기값은 Manual 코드의 init 값 참조)
int cur_base = 89;
int cur_shoulder = 134;
int cur_elbow = 42;
int cur_claw = 30;

void setup() {
  Serial.begin(115200); // 파이썬 코드의 Baudrate와 일치 (필요시 시리얼 모니터에서 변경)
  
  // 서보 모터 연결
  base.attach(PIN_BASE, 500, 2500);
  shoulder.attach(PIN_SHOULDER, 500, 2500);
  elbow.attach(PIN_ELBOW, 500, 2500);
  claw.attach(PIN_CLAW, 500, 2500);

  // 초기 위치 이동
  moveServos();
  
  Serial.println("READY"); // 파이썬 또는 사용자가 준비 상태를 알 수 있게 출력
  Serial.println("Input Format: Base, Shoulder, Elbow, Claw (e.g., 90,100,50,30)");
}

void loop() {
  // 시리얼 데이터가 들어오면 읽음
  if (Serial.available() > 0) {
    // 1. 데이터 파싱 (콤마로 구분된 정수 4개 읽기)
    int target_base = Serial.parseInt();
    int target_shoulder = Serial.parseInt();
    int target_elbow = Serial.parseInt();
    int target_claw = Serial.parseInt();

    // 입력 버퍼 비우기 (엔터 키 등 잔여 데이터 제거)
    while (Serial.available() > 0) {
      char t = Serial.read();
      if (t == '\n') break;
    }

    // 2. 유효성 검사 (값이 모두 0인 경우 읽기 실패로 간주할 수 있음)
    //    단, 실제 각도가 0,0,0,0일 수도 있으므로 상황에 따라 조정 필요
    //    여기서는 간단히 실행합니다.

    // 3. 안전 범위 제한 (Constraint) - Manual 코드의 제한값 적용
    cur_base = constrain(target_base, BASE_MIN, BASE_MAX);
    cur_shoulder = constrain(target_shoulder, SHL_MIN, SHL_MAX);
    cur_elbow = constrain(target_elbow, ELB_MIN, ELB_MAX);
    
    // Claw는 30(열림) 또는 0(닫힘) 위주로 사용되므로 범위 제한
    cur_claw = constrain(target_claw, CLAW_CLOSE, CLAW_OPEN);

    // 4. 이동 실행 및 정보 출력
    Serial.print("Moving to: ");
    Serial.print(cur_base); Serial.print(", ");
    Serial.print(cur_shoulder); Serial.print(", ");
    Serial.print(cur_elbow); Serial.print(", ");
    Serial.println(cur_claw);

    moveServos();
  }
}

void moveServos() {
  base.write(cur_base);
  shoulder.write(cur_shoulder);
  elbow.write(cur_elbow);
  claw.write(cur_claw);
}