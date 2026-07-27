#include "sensors.h"

#include <Arduino.h>
#include <VL53L1X.h>
#include <Wire.h>

#include "pins.h"

namespace {

constexpr uint8_t kMpuAddr = 0x68;
constexpr uint8_t kRegPwrMgmt1 = 0x6B;
constexpr uint8_t kRegAccelXoutH = 0x3B;
constexpr float kAccelLsbPerG = 16384.0f;   // +/-2 g range
constexpr float kGyroLsbPerDps = 131.0f;    // +/-250 deg/s range
constexpr float kG = 9.80665f;
constexpr float kAttitudeLp = 0.10f;        // accel-attitude low-pass factor

VL53L1X g_tof;
bool g_tofPresent = false;
bool g_imuPresent = false;
float g_pitchLp = 0.0f;
float g_rollLp = 0.0f;

bool mpuWrite(uint8_t reg, uint8_t value) {
  Wire.beginTransmission(kMpuAddr);
  Wire.write(reg);
  Wire.write(value);
  return Wire.endTransmission() == 0;
}

bool mpuReadBurst(uint8_t reg, uint8_t *buf, size_t n) {
  Wire.beginTransmission(kMpuAddr);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom(kMpuAddr, static_cast<uint8_t>(n)) != n) return false;
  for (size_t i = 0; i < n; ++i) buf[i] = Wire.read();
  return true;
}

int16_t be16(const uint8_t *p) {
  return static_cast<int16_t>((p[0] << 8) | p[1]);
}

}  // namespace

void sensorsInit() {
  Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL);
  Wire.setClock(400000);

  g_imuPresent = mpuWrite(kRegPwrMgmt1, 0x00);  // wake from sleep
  if (!g_imuPresent) {
    Serial.println("sensors: MPU6050 not found (telemetry marks imu absent)");
  }

  g_tof.setTimeout(100);
  g_tofPresent = g_tof.init();
  if (g_tofPresent) {
    g_tof.setDistanceMode(VL53L1X::Long);
    g_tof.setMeasurementTimingBudget(50000);
    g_tof.startContinuous(50);
  } else {
    Serial.println("sensors: VL53L1X not found (telemetry marks tof absent)");
  }
}

void sensorsRead(SensorReadings &out) {
  out.tofOk = g_tofPresent;
  out.imuOk = g_imuPresent;

  if (g_tofPresent && g_tof.dataReady()) {
    const uint16_t mm = g_tof.read(false);
    if (!g_tof.timeoutOccurred()) out.aglMm = mm;
  }

  if (!g_imuPresent) return;
  uint8_t raw[14];
  if (!mpuReadBurst(kRegAccelXoutH, raw, sizeof(raw))) return;
  const float ax = be16(raw + 0) / kAccelLsbPerG;
  const float ay = be16(raw + 2) / kAccelLsbPerG;
  const float az = be16(raw + 4) / kAccelLsbPerG;
  const float gx = be16(raw + 8) / kGyroLsbPerDps;   // deg/s
  const float gy = be16(raw + 10) / kGyroLsbPerDps;
  const float gz = be16(raw + 12) / kGyroLsbPerDps;
  (void)gx;

  // Accel-only attitude, low-passed: fine for a slow pendulum-swinging
  // balloon (the base station does any real estimation).
  const float pitch = atan2f(-ax, sqrtf(ay * ay + az * az));
  const float roll = atan2f(ay, az);
  g_pitchLp += (pitch - g_pitchLp) * kAttitudeLp;
  g_rollLp += (roll - g_rollLp) * kAttitudeLp;

  out.pitchRad = g_pitchLp;
  out.rollRad = g_rollLp;
  out.yawRateRadS = gz * static_cast<float>(M_PI) / 180.0f;
  out.pitchRateRadS = gy * static_cast<float>(M_PI) / 180.0f;
  out.azMs2 = (az - 1.0f) * kG;  // gravity removed, gondola-frame vertical
}
