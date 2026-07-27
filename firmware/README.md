# Meemoo firmware — Seeed XIAO ESP32S3 Sense

The bench firmware for the aircraft in docs/BUY_AND_BUILD.md (Box A parts).
Two build targets, one wiring. The aircraft is dumb (Constitution Art. II):
it obeys thrust packets and streams sensors; the only on-board decision is
the failsafe that zeroes the motors so the negative trim lands it.

## The pin table (THE wiring reference for Stages 3 and 4)

Solder exactly this. `firmware/include/pins.h` is the same table in code;
if a wire ever moves, both change in the same commit.

| XIAO pin | GPIO | Goes to | Role |
|----------|------|---------|------|
| D0 | 1 | DRV8833 #1 AIN1 | M1 forward-left motor, IN1 |
| D1 | 2 | DRV8833 #1 AIN2 | M1 forward-left motor, IN2 |
| D2 | 3 | DRV8833 #1 BIN1 | M2 forward-right motor, IN1 |
| D3 | 4 | DRV8833 #1 BIN2 | M2 forward-right motor, IN2 |
| D4 | 5 | VL53L1X SDA + MPU6050 SDA | I2C data (shared bus) |
| D5 | 6 | VL53L1X SCL + MPU6050 SCL | I2C clock (shared bus) |
| D6 | 43 | DRV8833 #2 AIN1 | M3 vertical-left motor, IN1 |
| D7 | 44 | DRV8833 #2 AIN2 | M3 vertical-left motor, IN2 |
| D8 | 7 | DRV8833 #2 BIN1 | M4 vertical-right motor, IN1 |
| D9 | 8 | DRV8833 #2 BIN2 | M4 vertical-right motor, IN2 |
| D10 | 9 | (spare) | future PMW3901 CS or battery divider |
| 3V3 | - | both DRV8833 VCC, VL53L1X VIN, MPU6050 VCC | power |
| GND | - | everything's GND | common ground |

Motor map (matches `meemoo/flight/mqtt_blimp.py` and the simulator's mixer):
M1/M2 are the forward pair (differential drive = yaw), M3/M4 the vertical
pair. Stage 3's single-motor circuit is exactly M1 on D0/D1, so FIGURE 1 in
the buy-and-build manual needs no rewiring later — you just keep adding.

Motor power note: Stage 3 runs the DRV8833 from the XIAO 3V3 pin (fine for
one motor on the bench). The Stage 4 gondola feeds both DRV8833 VCCs from
the 1S LiPo instead, with grounds common — four motors at full duty exceed
what the 3V3 regulator should carry.

The camera and PDM mic are internal to the Sense board (GPIO 10-18, 38-48
region, see `include/camera_pins.h`) and collide with nothing above.

## Build targets

### bench (Stage 3: "make one motor spin")

Spins M1 at 20% / 30% / 50% duty, 5 s each with a 2 s rest, forever.
Serial (115200) prints duty and estimated RPM once a second.

Honesty note: there is no tachometer in the BOM, so RPM is an estimate
(8520 name-plate no-load speed scaled by duty) and is labeled `est` in the
output. The real Stage 3 measurement is the decibel app at 1 m; the real
thrust curve is measured on the 0.1 g scale in Stage 9.

### flight (Stage 6: "first flight in your room")

- WiFi station mode. Copy `include/meemoo_config.sample.h` to
  `include/meemoo_config.h` (gitignored) and fill in your SSID/password.
  The build compiles without it (falls back to the sample) so CI never
  breaks.
- MJPEG camera stream at `http://<aircraft-ip>:81/stream` (800x600, ~12
  fps ceiling) — the same URL shape `video/announce` promises, so
  perception's `VideoSource(mjpeg_url=...)` consumes it unchanged.
- MUP/1 command link on UDP :4210, telemetry back to the last commander.
- Drives all 4 motors through the 2 DRV8833s with the exact mixer the
  simulator models (forward pair shares forward+yaw authority).
- Reads VL53L1X (height) + MPU6050 (attitude/rates) over I2C at 50 Hz;
  missing sensors are reported absent in telemetry, never faked.
- **No decisions on board.** The single autonomous behavior: no fresh
  command for 3 s (link loss) or past the packet ttl, motors go to zero
  and the 2-4 g negative trim lands it. `land_now` mode does the same on
  purpose.

## MUP/1 packet format (UDP)

Canonical byte layout: `meemoo/flight/mup.py` (unit-tested; the future UDP
bridge uses it directly). Mirrored in C++ in `include/mup1.h` with
static_asserts on the sizes. Semantics match the MQTT protocol spec in
`meemoo/flight/mqtt_blimp.py` — MQTT stays the production target, MUP/1 is
the v1 bench transport.

All little-endian. Magic `0x4D55` ("MU"), version 1.

**THRUST** (base -> aircraft, :4210, 16 bytes): magic u16, version u8,
type u8 = 0x01, seq u32, forward_gf i16 x100, vertical_gf i16 x100,
yaw_gf i16 x100, ttl_ms u16. The aircraft drops non-newer seq (wrap-aware)
and zeroes thrust when the newest command is older than its ttl.

**MODE** (base -> aircraft, 16 bytes): header with type 0x02, then mode u8
(0 idle, 1 fly, 2 land_now), 7 bytes reserved.

**TELEMETRY** (aircraft -> last commander, 28 bytes): header with type
0x81 and t_ms in the seq slot, then agl_mm u16 (0xFFFF = ToF absent),
pitch/roll centirad i16, yaw_rate centirad/s i16, az cm/s2 i16, batt_pct
u8 (0xFF = no divider fitted — true for this BOM), flags u8 (bit0
failsafe, bit1 tof ok, bit2 imu ok), duty[4] u8, batt_mv u16 (0 = not
fitted), seq_ack u16.

## Building and flashing

From the repo root (PlatformIO downloads the toolchain on first run):

```
make flash-bench    # compile + upload the bench target, then open serial
make flash-flight   # compile + upload the flight target
```

Compile check without hardware: `cd firmware && pio run` builds both
targets. `make check` runs it automatically when `pio` is on PATH and
skips it honestly when not (missing toolchain never breaks CI).

No PlatformIO? `python3 -m venv ~/.pio && ~/.pio/bin/pip install
platformio`, then `make flash-bench PIO=~/.pio/bin/pio`.

First flash on a fresh XIAO: hold the **B** (boot) button while plugging
in USB if the upload port never appears, then flash again.
