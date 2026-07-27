// MUP/1 UDP link: receive thrust/mode commands, send telemetry back to the
// last commander. Stale-command guard (ttl) + link-loss failsafe are the
// ONLY autonomous behaviors on the aircraft (mqtt_blimp.py evt/failsafe).

#pragma once

#include <stdint.h>

#include "sensors.h"

struct LinkCommand {
  float forwardGf = 0.0f;
  float verticalGf = 0.0f;
  float yawGf = 0.0f;
  uint8_t mode = 1;            // kMupModeFly until told otherwise
  uint32_t lastSeq = 0;
  uint32_t lastRxMs = 0;       // millis() at last accepted command
  uint32_t expiresAtMs = 0;    // receipt + ttl_ms; stale = thrust zero
};

void linkBegin(uint16_t port);

// Drain pending UDP packets into `cmd`. Returns true if anything arrived.
bool linkPoll(LinkCommand &cmd);

// 20 Hz telemetry to whoever commanded last (no-op before first command).
void linkSendTelemetry(const SensorReadings &s, const LinkCommand &cmd,
                       bool failsafeActive);
