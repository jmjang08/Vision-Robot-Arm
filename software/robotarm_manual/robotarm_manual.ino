/*
  Serial Robot Arm Control (Optimized)
  Python Input Format: base,shoulder,elbow,claw (e.g., 90,120,40,30)
*/
#include <Servo.h>

#define PIN_BASE      11
#define PIN_SHOULDER  10
#define PIN_ELBOW     9
#define PIN_CLAW      5

// Angle limits (Hardware protection) 
const int BASE_MIN = 15; 
const int BASE_MAX = 160; 
const int SHL_MIN = 10;    const int SHL_MAX = 160; 
const int ELB_MIN = 10; 
const int ELB_MAX = 120; 
const int CLAW_CLOSE = 0; 
const int CLAW_OPEN = 30; 

Servo base, shoulder, elbow, claw;

// Current angle variables 
int cur_base = 89; 
int cur_shoulder = 134; 
int cur_elbow = 42; 
int cur_claw = 30; 

void setup() {
  Serial.begin(115200); // Must match Python's BAUD_RATE 
  Serial.setTimeout(50); 

  base.attach(PIN_BASE, 500, 2500); 
  shoulder.attach(PIN_SHOULDER, 500, 2500); 
  elbow.attach(PIN_ELBOW, 500, 2500); 
  claw.attach(PIN_CLAW, 500, 2500); 

  moveServos(); // Move to initial position 
  Serial.println("READY"); 
} 

void loop() {
  if (Serial.available() > 0) { 
    // Read the entire line and parse (more stable) 
    String data = Serial.readStringUntil('\n'); 

    int firstComma = data.indexOf(','); 
    int secondComma = data.indexOf(',', firstComma + 1); 
    int thirdComma = data.indexOf(',', secondComma + 1); 

    if (thirdComma != -1) { 
      int t_base = data.substring(0, firstComma).toInt(); 
      int t_shl = data.substring(firstComma + 1, secondComma).toInt(); 
      int t_elb = data.substring(secondComma + 1, thirdComma).toInt(); 
      int t_claw = data.substring(thirdComma + 1).toInt(); 

      // Apply constraints and update 
      cur_base = constrain(t_base, BASE_MIN, BASE_MAX); 
      cur_shoulder = constrain(t_shl, SHL_MIN, SHL_MAX); 
      cur_elbow = constrain(t_elb, ELB_MIN, ELB_MAX); 
      cur_claw = constrain(t_claw, CLAW_CLOSE, CLAW_OPEN); 

      moveServos(); 

      // Feedback for debugging (displayed in Python terminal) 
      Serial.print("Moved: "); 
      Serial.print(cur_base); Serial.print(","); 
      Serial.print(cur_shoulder); Serial.print(","); 
      Serial.print(cur_elbow); Serial.print(","); 
      Serial.println(cur_claw); 
    } 
  }
}

void moveServos() { 
  base.write(cur_base); 
  shoulder.write(cur_shoulder); 
  elbow.write(cur_elbow); 
  claw.write(cur_claw); 
}
