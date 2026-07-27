#include "link.h"

#include <Arduino.h>
#include <WiFi.h>
#include <WiFiUdp.h>

#include <cstring>

#include "motors.h"
#include "mup1.h"

namespace {

WiFiUDP g_udp;
IPAddress g_peerIp;
uint16_t g_peerPort = 0;
bool g_havePeer = false;

}  // namespace

void linkBegin(uint16_t port) {
  g_udp.begin(port);
}

bool linkPoll(LinkCommand &cmd) {
  bool got = false;
  int size = 0;
  while ((size = g_udp.parsePacket()) > 0) {
    uint8_t buf[64];
    const int n = g_udp.read(buf, sizeof(buf));
    if (n < static_cast<int>(sizeof(MupHeader))) continue;
    MupHeader hdr;
    memcpy(&hdr, buf, sizeof(hdr));
    if (hdr.magic != kMupMagic || hdr.version != kMupVersion) continue;
    if (cmd.lastSeq != 0 && !mupSeqNewer(hdr.seq, cmd.lastSeq)) continue;

    if (hdr.type == kMupTypeThrust && n == static_cast<int>(sizeof(MupThrust))) {
      MupThrust pkt;
      memcpy(&pkt, buf, sizeof(pkt));
      cmd.forwardGf = pkt.forward_cgf / 100.0f;
      cmd.verticalGf = pkt.vertical_cgf / 100.0f;
      cmd.yawGf = pkt.yaw_cgf / 100.0f;
      cmd.lastSeq = hdr.seq;
      cmd.lastRxMs = millis();
      cmd.expiresAtMs = cmd.lastRxMs + pkt.ttl_ms;
      got = true;
    } else if (hdr.type == kMupTypeMode && n == static_cast<int>(sizeof(MupMode))) {
      MupMode pkt;
      memcpy(&pkt, buf, sizeof(pkt));
      cmd.mode = pkt.mode;
      cmd.lastSeq = hdr.seq;
      cmd.lastRxMs = millis();
      got = true;
    } else {
      continue;
    }
    g_peerIp = g_udp.remoteIP();
    g_peerPort = g_udp.remotePort();
    g_havePeer = true;
  }
  return got;
}

void linkSendTelemetry(const SensorReadings &s, const LinkCommand &cmd,
                       bool failsafeActive) {
  if (!g_havePeer) return;
  MupTelemetry t;
  t.hdr.magic = kMupMagic;
  t.hdr.version = kMupVersion;
  t.hdr.type = kMupTypeTelemetry;
  t.hdr.seq = millis();  // t_ms rides the header seq slot (see mup.py)
  t.agl_mm = s.tofOk ? s.aglMm : kMupAglAbsent;
  t.pitch_centirad = static_cast<int16_t>(s.pitchRad * 100.0f);
  t.roll_centirad = static_cast<int16_t>(s.rollRad * 100.0f);
  t.yaw_rate_centirad_s = static_cast<int16_t>(s.yawRateRadS * 100.0f);
  t.az_cm_s2 = static_cast<int16_t>(s.azMs2 * 100.0f);
  t.batt_pct = kMupBattAbsent;  // no divider on the bench BOM: honest absent
  t.flags = static_cast<uint8_t>((failsafeActive ? kMupFlagFailsafe : 0) |
                                 (s.tofOk ? kMupFlagTofOk : 0) |
                                 (s.imuOk ? kMupFlagImuOk : 0));
  motorsDuty(t.duty);
  t.batt_mv = 0;  // not fitted (PIN_SPARE + divider is the future home)
  t.seq_ack = static_cast<uint16_t>(cmd.lastSeq & 0xFFFF);

  g_udp.beginPacket(g_peerIp, g_peerPort);
  g_udp.write(reinterpret_cast<const uint8_t *>(&t), sizeof(t));
  g_udp.endPacket();
}
