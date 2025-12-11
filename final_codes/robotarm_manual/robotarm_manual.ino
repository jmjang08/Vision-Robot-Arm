/*
  Simple Robot ARM
  JoyStick Control for UNO/NANO Board

  pins:
  11 : Servo base
  10 : Servo left
  9 : Servo right
  5 : Servo claw

*/

#include <Servo.h>

#define SERVOS      (4)     // 로봇팔에 필요한 모터의 개수

Servo arm_servos[SERVOS];
// 서보 모터 선언

int servo_pins[SERVOS];         // 모터가 연결될 메인보드의 I/O 포트
int servo_cur_angle[SERVOS];    // 모터의 현재 회전 각도
int servo_min_angle[SERVOS];
// 모터 회전 가능 최소값
int servo_max_angle[SERVOS];    // 모터 회전 가능 최대값
int servo_init_angle[SERVOS];   // 전원을 켠 직후, 모터의 초기 각도

int joystick_value[SERVOS];
#define JOYSTICK_MIN_THRESH   (300)   // 조이스틱 ADC 값의 최소 임계값
#define JOYSTICK_MAX_THRESH   (700)   // 조이스틱 ADC 값의 최대 임계값

#define CLAW_OPEN_ANGLE   (30)    // 집게가 펼쳐졌을 때의 모터 각도
#define CLAW_CLOSE_ANGLE  (0)     // 집게가 접혔을 때의 모터 각도
#define CLAW_SERVO_INDEX  (SERVOS-1)  // 집게 모터의 일련번호, 마지막에서 하나 전

#define JOYSTICK_LED      (3)     // 조이스틱 모듈 위의 LED 램프는 메인보드 3번 핀에 연결됩니다.
#define JOYSTICK_LEFT_BUTTON (2)    // 왼쪽 버튼은 초기 위치 복귀에 사용

void setup() {
  Serial.begin(115200);

  pinMode(JOYSTICK_LED, OUTPUT);
  digitalWrite(JOYSTICK_LED, HIGH); // LED 켜기

  // 왼쪽 조이스틱 버튼 핀을 내부 풀업 저항 입력 모드로 설정
  pinMode(JOYSTICK_LEFT_BUTTON, INPUT_PULLUP); 

  Serial.println("System Running...");
  Serial.println("Press Left Joystick Button to return to initial position."); 

  // 초기화 작업
  initialization();
}

void loop() {
  // 조이스틱 왼쪽 버튼이 눌렸는지 확인 (PULLUP 모드이므로 LOW일 때 눌림)
  if (digitalRead(JOYSTICK_LEFT_BUTTON) == LOW) { 
    // 버튼이 눌렸으면 초기 위치로 복귀
    return_to_initial();

    // 버튼에서 손을 뗄 때까지 대기 (반복 실행 방지)
    while (digitalRead(JOYSTICK_LEFT_BUTTON) == LOW) {
      delay(50);
    }
  } else {
    // 버튼이 눌리지 않았으면 조이스틱으로 로봇 팔 제어
    move_by_joystick_control();
  }
} 

void initialization() {
  // Base servo
  servo_pins[0] = 11;         // 연결핀: 11
  servo_min_angle[0] = 15;
  // 모터 회전 가능 최소값
  servo_max_angle[0] = 160;   // 모터 회전 가능 최대값
  servo_init_angle[0] = 89;
  // 전원을 켤 때 모터의 초기 각도

  // Left servo               // 2중 링크
  servo_pins[1] = 10;
  // 연결핀: 10
  servo_min_angle[1] = 10;    // 모터 회전 가능 최소값
  servo_max_angle[1] = 160;
  // 모터 회전 가능 최대값
  servo_init_angle[1] = 119;   // 전원을 켤 때 모터의 초기 각도

  // Right servo              // 직결 링크
  servo_pins[2] = 9;
  // 연결핀: 9
  servo_min_angle[2] = 10;    // 모터 회전 가능 최소값
  servo_max_angle[2] = 120;
  // 모터 회전 가능 최대값
  servo_init_angle[2] = 15;   // 전원을 켤 때 모터의 초기 각도

  // Claw servo
  servo_pins[3] = 5;
  // 연결핀: 5
  servo_min_angle[3] = CLAW_CLOSE_ANGLE;  // 모터 회전 가능 최소값, 집게 닫음
  servo_max_angle[3] = CLAW_OPEN_ANGLE;
  // 모터 회전 가능 최대값, 집게 열림
  servo_init_angle[3] = CLAW_OPEN_ANGLE;
  // 전원을 켤 때 모터의 초기 각도, 집게 열림

  // 모든 모터에 초기 각도 설정
  init_servos();
}

void init_servos() {
  for (int i = 0; i < SERVOS; i++)
  {
    arm_servos[i].attach(servo_pins[i], 500, 2500);
    // 스위치를 해당 PWM 핀에 연결한다
    arm_servos[i].write(servo_init_angle[i]);
    // 모터의 초기 각도 설정
    servo_cur_angle[i] = servo_init_angle[i]; // 현재 각도 변수도 초기화
    joystick_value[i] = 0;
    // 조이스틱 ADC 값을 초기값 0으로 설정
    delay(500);
    // 모터 초기화 시 0.5초 딜레이
  }
}


// 모든 서보 모터를 초기 위치로 되돌리는 함수
void return_to_initial() {
  Serial.println("Returning to initial position...");
  for (int i = 0; i < SERVOS; i++) {
    // initialization()에서 설정한 초기 각도 값으로 서보를 이동
    arm_servos[i].write(servo_init_angle[i]);
    
    // 현재 각도를 저장하는 변수도 초기 각도로 업데이트
    servo_cur_angle[i] = servo_init_angle[i];
  }
  Serial.println("Initial position set.");
  // 서보가 위치로 이동할 시간을 줌
  delay(1000); 
}



// 집게 개폐 제어
void close_claw(bool close)
{
  if (close) {
    arm_servos[CLAW_SERVO_INDEX].write(CLAW_CLOSE_ANGLE);
  } else {
    arm_servos[CLAW_SERVO_INDEX].write(CLAW_OPEN_ANGLE);
  }
}

void move_by_joystick_control()
{
  bool joy_changed = false;
  for (int i = 0; i < SERVOS; i++)
  {
    // 조이스틱 ADC 값 읽기
    joystick_value[i] = analogRead(i);
    // 모터의 현재 회전 각도 읽기
    servo_cur_angle[i] = arm_servos[i].read();
    if (joystick_value[i] > JOYSTICK_MAX_THRESH)      // 조이스틱 ADC 값이 최대 임계값을 초과하면
    {
      joy_changed = true;
      // 조이스틱이 너무 세게 눌렸어요!

      if (servo_cur_angle[i] > servo_min_angle[i])
      {
        // 만약 모터의 현재 각도가 허용되는 최소 회전 각도를 초과할 경우, 모터 각도를 1도 낮춘다.
        --servo_cur_angle[i];
      }

      // 집게 모터인 경우, 발톱을 직접 엽니다.
      if (i == CLAW_SERVO_INDEX)
      {
        servo_cur_angle[i] = CLAW_OPEN_ANGLE;
      }
    }
    else if (joystick_value[i] < JOYSTICK_MIN_THRESH) // 조이스틱 ADC 값이 최소 임계값보다 작으면
    {
      joy_changed = true;
      // 조이스틱이 너무 세게 눌렸어요!

      if (servo_cur_angle[i] < servo_max_angle[i])
      {
        // 만약 모터의 현재 각도가 허용되는 최대 회전 각도 미만일 경우, 모터 각도를 1도 증가시킨다.
        ++servo_cur_angle[i];
      }

      // 집게 모터인 경우, 발톱을 직접 닫습니다.
      if (i == CLAW_SERVO_INDEX)
      {
        servo_cur_angle[i] = CLAW_CLOSE_ANGLE;
      }
    }
  }

  if (true == joy_changed)
  {
    // 조이스틱이 움직이면 모터 각도를 새로 고침, 현재 모터의 각도 값을 모터에 기록합니다.
    Serial.println("--- Angle Update ---");
    for (int i = 0 ; i < SERVOS; i++)
    {
      String servoName;
      switch(i) {
        case 0: servoName = "Base "; break;
        case 1: servoName = "Left "; break;
        case 2: servoName = "Right"; break;
        case 3: servoName = "Claw "; break;
      }
      
      // 각 서보의 이름과 현재 각도를 명확하게 출력
      Serial.print(servoName);
      Serial.print(" Servo: ");
      Serial.print(servo_cur_angle[i]);
      Serial.println(" deg");

      arm_servos[i].write(servo_cur_angle[i]);
    }
    Serial.println("--------------------");
  }

  delay(20);
}