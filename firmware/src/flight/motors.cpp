#include "motors.h"

#include <Arduino.h>

#include "pins.h"

// The ESP32-S3 has 8 LEDC channels and the camera XCLK needs one, so each
// motor gets ONE channel (0..3) that is re-attached to the active DRV8833
// input on direction change; the idle input is driven LOW (fast-decay
// coast). Channels 0..3 sit on LEDC timers 0..1; the camera uses channel 4
// / timer 2 (camera_stream.cpp) — no collision.

namespace {

struct MotorState {
  int ch;
  int pinFwd;   // IN1: PWM here spins forward
  int pinRev;   // IN2: PWM here spins reverse
  int attached; // which pin currently owns the LEDC channel
};

MotorState g_motors[4] = {
    {0, PIN_M1_IN1, PIN_M1_IN2, -1},
    {1, PIN_M2_IN1, PIN_M2_IN2, -1},
    {2, PIN_M3_IN1, PIN_M3_IN2, -1},
    {3, PIN_M4_IN1, PIN_M4_IN2, -1},
};

uint8_t g_duty[4] = {0, 0, 0, 0};

float clampGf(float gf) {
  if (gf > kThrustMaxGfPerMotor) return kThrustMaxGfPerMotor;
  if (gf < -kThrustReverseGfPerMotor) return -kThrustReverseGfPerMotor;
  return gf;
}

void attachActive(MotorState &m, int pinActive, int pinIdle) {
  if (m.attached == pinActive) return;
  if (m.attached >= 0) ledcDetachPin(m.attached);
  pinMode(pinIdle, OUTPUT);
  digitalWrite(pinIdle, LOW);
  ledcAttachPin(pinActive, m.ch);
  m.attached = pinActive;
}

void setMotorGf(int idx, float gf) {
  MotorState &m = g_motors[idx];
  gf = clampGf(gf);
  const float dutyFrac = gf / kThrustMaxGfPerMotor;  // signed, |x| <= 1
  const int duty = static_cast<int>(fabsf(dutyFrac) * kPwmDutyMax);
  if (dutyFrac >= 0.0f) {
    attachActive(m, m.pinFwd, m.pinRev);
  } else {
    attachActive(m, m.pinRev, m.pinFwd);
  }
  ledcWrite(m.ch, duty);
  g_duty[idx] = static_cast<uint8_t>(fabsf(dutyFrac) * 255.0f);
}

}  // namespace

void motorsInit() {
  for (auto &m : g_motors) {
    pinMode(m.pinFwd, OUTPUT);
    pinMode(m.pinRev, OUTPUT);
    digitalWrite(m.pinFwd, LOW);
    digitalWrite(m.pinRev, LOW);
    ledcSetup(m.ch, kPwmFreqHz, kPwmResBits);
    attachActive(m, m.pinFwd, m.pinRev);
    ledcWrite(m.ch, 0);
  }
  motorsZero();
}

void motorsApply(float forwardGf, float verticalGf, float yawGf) {
  // The exact mixer the simulator models (meemoo/flight/physics.py _mix):
  // forward pair shares forward + yaw authority; vertical pair splits vert.
  setMotorGf(0, forwardGf * 0.5f - yawGf);  // M1 forward-left
  setMotorGf(1, forwardGf * 0.5f + yawGf);  // M2 forward-right
  setMotorGf(2, verticalGf * 0.5f);         // M3 vertical-left
  setMotorGf(3, verticalGf * 0.5f);         // M4 vertical-right
}

void motorsZero() {
  for (int i = 0; i < 4; ++i) setMotorGf(i, 0.0f);
}

void motorsDuty(uint8_t out[4]) {
  for (int i = 0; i < 4; ++i) out[i] = g_duty[i];
}
