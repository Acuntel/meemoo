// Meemoo flight target — the dumb aircraft (Constitution Art. II 1).
//
// It joins WiFi, streams MJPEG on :81/stream, obeys MUP/1 thrust packets on
// UDP :4210, and telemeters VL53L1X + MPU6050 back to the commander. It
// decides NOTHING except the failsafe: on link loss (> MEEMOO_LINK_LOSS_MS
// without a fresh command) or command ttl expiry it zeroes the motors and
// the 2-4 g negative trim lands it gently. That is the whole brain.
//
// Packet format: firmware/include/mup1.h, canonical in meemoo/flight/mup.py.
// Wiring: firmware/include/pins.h (the README renders the same table).

#include <Arduino.h>
#include <WiFi.h>

#if __has_include("meemoo_config.h")
#include "meemoo_config.h"
#else
#include "meemoo_config.sample.h"
#warning "firmware/include/meemoo_config.h not found - building with sample WiFi creds"
#endif

#include "camera_stream.h"
#include "link.h"
#include "motors.h"
#include "mup1.h"
#include "sensors.h"

namespace {

constexpr uint32_t kSensorEveryMs = 20;    // 50 Hz
constexpr uint32_t kTelemetryEveryMs = 50; // 20 Hz
constexpr uint32_t kWifiRetryMs = 5000;

LinkCommand g_cmd;
SensorReadings g_sensors;
bool g_failsafe = false;
uint32_t g_nextSensorMs = 0;
uint32_t g_nextTelemetryMs = 0;
uint32_t g_nextWifiCheckMs = 0;
bool g_announced = false;

void wifiConnect() {
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);  // latency beats power on a 20-minute pack
  WiFi.begin(MEEMOO_WIFI_SSID, MEEMOO_WIFI_PASS);
  Serial.printf("wifi: joining %s ...\n", MEEMOO_WIFI_SSID);
}

// The one decision the aircraft is allowed to make (Art. IV 6).
bool failsafeCheck() {
  const uint32_t now = millis();
  if (WiFi.status() != WL_CONNECTED) return true;
  if (g_cmd.lastRxMs == 0) return true;  // nobody has commanded yet
  if (now - g_cmd.lastRxMs > MEEMOO_LINK_LOSS_MS) return true;
  return false;
}

}  // namespace

void setup() {
  Serial.begin(115200);
  delay(2000);  // give the USB CDC console a moment to attach
  Serial.println("Meemoo flight firmware (MUP/1, dumb aircraft)");
  motorsInit();   // motors zeroed before anything else can go wrong
  sensorsInit();
  wifiConnect();
  cameraStreamBegin();  // failure tolerated: it flies without video
  linkBegin(MEEMOO_CMD_PORT);
}

void loop() {
  const uint32_t now = millis();

  // WiFi keepalive: retry the join forever, never reboot mid-air.
  if (WiFi.status() != WL_CONNECTED && now >= g_nextWifiCheckMs) {
    g_nextWifiCheckMs = now + kWifiRetryMs;
    WiFi.disconnect();
    WiFi.begin(MEEMOO_WIFI_SSID, MEEMOO_WIFI_PASS);
  }
  if (WiFi.status() == WL_CONNECTED && !g_announced) {
    g_announced = true;
    Serial.printf("wifi: %s  mjpeg http://%s:81/stream  udp cmd :%d\n",
                  WiFi.localIP().toString().c_str(),
                  WiFi.localIP().toString().c_str(), MEEMOO_CMD_PORT);
  }

  linkPoll(g_cmd);

  const bool failsafe = failsafeCheck();
  if (failsafe != g_failsafe) {
    g_failsafe = failsafe;
    Serial.println(failsafe ? "failsafe: motors zero (link loss)"
                            : "failsafe: cleared, link live");
  }

  if (failsafe || g_cmd.mode != kMupModeFly || now > g_cmd.expiresAtMs) {
    // Link lost, told to idle/land, or the command went stale (ttl):
    // thrust zero. Negative trim does the landing; no cleverness here.
    motorsZero();
  } else {
    motorsApply(g_cmd.forwardGf, g_cmd.verticalGf, g_cmd.yawGf);
  }

  if (now >= g_nextSensorMs) {
    g_nextSensorMs = now + kSensorEveryMs;
    sensorsRead(g_sensors);
  }
  if (now >= g_nextTelemetryMs) {
    g_nextTelemetryMs = now + kTelemetryEveryMs;
    linkSendTelemetry(g_sensors, g_cmd, g_failsafe);
  }
  delay(2);
}
