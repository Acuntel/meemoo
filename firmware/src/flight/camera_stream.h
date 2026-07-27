// MJPEG stream on :81/stream — the mqtt_blimp.py video/announce handoff:
// perception's VideoSource(mjpeg_url=...) consumes it unchanged.

#pragma once

// Init the OV2640 + start the stream server. Returns false (and the
// aircraft keeps flying) when the camera is absent or init fails — a
// missing sensor never bricks the vehicle.
bool cameraStreamBegin();
