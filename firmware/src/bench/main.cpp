// Meemoo bench target — Stage 3 of docs/BUY_AND_BUILD.md.
//
// Spins motor 1 (XIAO D0/D1 -> DRV8833 #1 -> 8520 motor) at 20/30/50% PWM
// in a loop and prints duty + estimated RPM over serial. Hold the decibel
// app 1 m away and write down the number at the slow setting: that is
// Meemoo's real in-flight voice level.
//
// HONESTY NOTE: there is no tachometer on the bench BOM, so the RPM column
// is an ESTIMATE (8520 name-plate no-load speed scaled linearly by duty,
// printed with "est"). The decibel reading is the real measurement; the
// per-duty thrust curve gets measured on the scale in Stage 9.

#include <Arduino.h>

#include "pins.h"

namespace {

constexpr int kChIn1 = 0;
constexpr int kChIn2 = 1;

// 8520 coreless no-load speed is ~40k RPM around 3.7 V; the DRV8833 here is
// fed from the XIAO's 3V3 rail in the Stage 3 circuit, so scale down.
constexpr float kEstRpmAtFullDuty = 35000.0f;

constexpr int kDutySteps[] = {20, 30, 50};
constexpr uint32_t kStepMs = 5000;
constexpr uint32_t kRestMs = 2000;
constexpr uint32_t kPrintEveryMs = 1000;

void setDutyPct(int pct) {
  const int duty = (kPwmDutyMax * pct) / 100;
  ledcWrite(kChIn1, duty);  // IN1 PWM, IN2 low = forward
  ledcWrite(kChIn2, 0);
}

void printLine(int pct) {
  const float estRpm = kEstRpmAtFullDuty * (static_cast<float>(pct) / 100.0f);
  Serial.printf("motor1 duty=%d%%  est_rpm~%.0f (estimate, no tach fitted)\n",
                pct, static_cast<double>(estRpm));
}

}  // namespace

void setup() {
  Serial.begin(115200);
  delay(2000);  // give the USB CDC console a moment to attach
  ledcSetup(kChIn1, kPwmFreqHz, kPwmResBits);
  ledcSetup(kChIn2, kPwmFreqHz, kPwmResBits);
  ledcAttachPin(PIN_M1_IN1, kChIn1);
  ledcAttachPin(PIN_M1_IN2, kChIn2);
  setDutyPct(0);
  Serial.println("Meemoo bench: Stage 3 noise test.");
  Serial.println("Motor 1 cycles 20% -> 30% -> 50%, 5 s each, 2 s rest.");
  Serial.println("Decibel app at 1 m; write down the 20% number.");
}

void loop() {
  for (const int pct : kDutySteps) {
    setDutyPct(pct);
    const uint32_t until = millis() + kStepMs;
    uint32_t nextPrint = 0;
    while (millis() < until) {
      if (millis() >= nextPrint) {
        printLine(pct);
        nextPrint = millis() + kPrintEveryMs;
      }
      delay(10);
    }
  }
  setDutyPct(0);
  Serial.println("motor1 duty=0%  (rest)");
  delay(kRestMs);
}
