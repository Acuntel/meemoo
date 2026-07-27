// Motor mixer — the dumb on-board table from meemoo/flight/mqtt_blimp.py:
// fwd/yaw -> M1/M2 (differential), vert -> M3/M4. No control loops here;
// the base station is the brain (Constitution Art. II 1).

#pragma once

#include <stdint.h>

void motorsInit();

// Apply a thrust command in gram-force (the ThrustCommand shape). Each
// motor is clamped to [-kThrustReverseGfPerMotor, +kThrustMaxGfPerMotor]
// and mapped linearly to PWM duty (bench Stage 9 replaces the linear map
// with the measured curve).
void motorsApply(float forwardGf, float verticalGf, float yawGf);

void motorsZero();

// Last applied duty magnitudes for telemetry, 0..255 per motor (m1..m4).
void motorsDuty(uint8_t out[4]);
