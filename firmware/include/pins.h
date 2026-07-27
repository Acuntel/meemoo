// Meemoo pin map — Seeed XIAO ESP32S3 Sense (the Stage 3/4 wiring truth).
//
// This header IS the wiring reference: firmware/README.md renders the same
// table for human eyes. If a wire moves, both move in the same commit.
//
// Motor map follows meemoo/flight/mqtt_blimp.py: M1/M2 = forward pair
// (differential = yaw), M3/M4 = vertical pair. Stage 3 (one motor) uses
// exactly M1 on D0/D1, matching FIGURE 1 in docs/BUY_AND_BUILD.md.
//
// The camera + PDM mic on the Sense sit on internal GPIOs (see
// camera_pins.h) and do not collide with any pin below.

#pragma once

// ---- DRV8833 #1: forward pair --------------------------------------------
constexpr int PIN_M1_IN1 = 1;   // XIAO D0  -> DRV8833 #1 AIN1  (M1 fwd-left)
constexpr int PIN_M1_IN2 = 2;   // XIAO D1  -> DRV8833 #1 AIN2
constexpr int PIN_M2_IN1 = 3;   // XIAO D2  -> DRV8833 #1 BIN1  (M2 fwd-right)
constexpr int PIN_M2_IN2 = 4;   // XIAO D3  -> DRV8833 #1 BIN2

// ---- I2C bus: VL53L1X (0x29) + MPU6050 (0x68) ----------------------------
constexpr int PIN_I2C_SDA = 5;  // XIAO D4
constexpr int PIN_I2C_SCL = 6;  // XIAO D5

// ---- DRV8833 #2: vertical pair -------------------------------------------
constexpr int PIN_M3_IN1 = 43;  // XIAO D6  -> DRV8833 #2 AIN1  (M3 vert-left)
constexpr int PIN_M3_IN2 = 44;  // XIAO D7  -> DRV8833 #2 AIN2
constexpr int PIN_M4_IN1 = 7;   // XIAO D8  -> DRV8833 #2 BIN1  (M4 vert-right)
constexpr int PIN_M4_IN2 = 8;   // XIAO D9  -> DRV8833 #2 BIN2

// ---- spare ----------------------------------------------------------------
constexpr int PIN_SPARE = 9;    // XIAO D10 - future PMW3901 CS or VBAT divider

// ---- PWM ------------------------------------------------------------------
constexpr int kPwmFreqHz = 20000;  // above audible: you hear the prop, not the PWM
constexpr int kPwmResBits = 10;
constexpr int kPwmDutyMax = (1 << kPwmResBits) - 1;

// Thrust scaling (research/06: ~10 gf per motor at full duty; reverse props
// are roughly half as effective — the same numbers the simulator flies).
constexpr float kThrustMaxGfPerMotor = 10.0f;
constexpr float kThrustReverseGfPerMotor = 5.0f;
