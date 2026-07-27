// I2C sensors: VL53L1X downward ToF (height) + MPU6050 IMU (attitude).
// Raw readings only — perception and control live on the base station.

#pragma once

#include <stdint.h>

struct SensorReadings {
  bool tofOk = false;
  bool imuOk = false;
  uint16_t aglMm = 0xFFFF;      // height above floor; 0xFFFF = absent
  float pitchRad = 0.0f;        // accel-derived, low-passed
  float rollRad = 0.0f;
  float yawRateRadS = 0.0f;     // gyro z
  float pitchRateRadS = 0.0f;   // gyro y — feeds the base-side swing damper
  float azMs2 = 0.0f;           // vertical accel, gravity removed
};

void sensorsInit();

// Poll at ~50 Hz from loop(); cheap when a sensor is absent.
void sensorsRead(SensorReadings &out);
