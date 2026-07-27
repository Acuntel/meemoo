// WiFi + link config SAMPLE. Copy to firmware/include/meemoo_config.h
// (gitignored) and fill in your real network before `make flash-flight`.
//
//   cp firmware/include/meemoo_config.sample.h firmware/include/meemoo_config.h
//
// (The name is prefixed because a bare "config.h" collides with framework
// headers in the include path.)
// The build falls back to this sample so `pio run` always compiles; the
// aircraft will just sit on the bench failing to join "your-wifi-name".

#pragma once

#define MEEMOO_WIFI_SSID "your-wifi-name"
#define MEEMOO_WIFI_PASS "your-wifi-password"

// MUP/1 UDP command port the aircraft listens on (meemoo/flight/mup.py).
#define MEEMOO_CMD_PORT 4210

// Milliseconds without a fresh command before the failsafe zeroes thrust
// (matches LINK_LOSS_FAILSAFE_MS in meemoo/flight/mup.py — dumb aircraft:
// negative trim lands it).
#define MEEMOO_LINK_LOSS_MS 3000
