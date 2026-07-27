// MUP/1 — Meemoo UDP Protocol, aircraft side.
//
// CANONICAL byte layout lives in meemoo/flight/mup.py (unit-tested); this
// header mirrors it struct-for-struct. Field semantics match the MQTT spec
// in meemoo/flight/mqtt_blimp.py (cmd/thrust, cmd/mode, telemetry).
// All little-endian; ESP32 is little-endian so packed structs are exact.

#pragma once

#include <stdint.h>

constexpr uint16_t kMupMagic = 0x4D55;  // "MU"
constexpr uint8_t kMupVersion = 1;
constexpr uint8_t kMupTypeThrust = 0x01;
constexpr uint8_t kMupTypeMode = 0x02;
constexpr uint8_t kMupTypeTelemetry = 0x81;

constexpr uint8_t kMupModeIdle = 0;
constexpr uint8_t kMupModeFly = 1;
constexpr uint8_t kMupModeLandNow = 2;

constexpr uint8_t kMupFlagFailsafe = 0x01;
constexpr uint8_t kMupFlagTofOk = 0x02;
constexpr uint8_t kMupFlagImuOk = 0x04;

constexpr uint16_t kMupAglAbsent = 0xFFFF;
constexpr uint8_t kMupBattAbsent = 0xFF;

#pragma pack(push, 1)

struct MupHeader {          // 8 bytes
  uint16_t magic;
  uint8_t version;
  uint8_t type;
  uint32_t seq;
};

struct MupThrust {          // 16 bytes total
  MupHeader hdr;
  int16_t forward_cgf;      // gram-force x100
  int16_t vertical_cgf;
  int16_t yaw_cgf;          // differential: right minus left, per motor
  uint16_t ttl_ms;          // command expires this long after receipt
};

struct MupMode {            // 16 bytes total
  MupHeader hdr;
  uint8_t mode;
  uint8_t reserved[7];
};

struct MupTelemetry {       // 28 bytes total
  MupHeader hdr;            // seq field carries t_ms (aircraft millis)
  uint16_t agl_mm;          // 0xFFFF = ToF absent
  int16_t pitch_centirad;
  int16_t roll_centirad;
  int16_t yaw_rate_centirad_s;
  int16_t az_cm_s2;
  uint8_t batt_pct;         // 0xFF = no battery sense fitted
  uint8_t flags;
  uint8_t duty[4];          // m1..m4 magnitude, 0..255 = 0..100%
  uint16_t batt_mv;         // 0 = not fitted
  uint16_t seq_ack;         // low 16 bits of last accepted command seq
};

#pragma pack(pop)

static_assert(sizeof(MupHeader) == 8, "MUP/1 header drifted from mup.py");
static_assert(sizeof(MupThrust) == 16, "MUP/1 thrust drifted from mup.py");
static_assert(sizeof(MupMode) == 16, "MUP/1 mode drifted from mup.py");
static_assert(sizeof(MupTelemetry) == 28, "MUP/1 telemetry drifted from mup.py");

// Serial-number arithmetic: true when `seq` is newer than `last` (wrap-aware).
inline bool mupSeqNewer(uint32_t seq, uint32_t last) {
  return static_cast<int32_t>(seq - last) > 0;
}
