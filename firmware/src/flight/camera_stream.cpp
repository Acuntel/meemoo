#include "camera_stream.h"

#include <Arduino.h>
#include <esp_camera.h>
#include <esp_http_server.h>

#include "camera_pins.h"

namespace {

constexpr char kBoundary[] = "meemooframe";

esp_err_t streamHandler(httpd_req_t *req) {
  char part[128];
  httpd_resp_set_type(
      req, "multipart/x-mixed-replace;boundary=" "meemooframe");
  while (true) {
    camera_fb_t *fb = esp_camera_fb_get();
    if (fb == nullptr) {
      return ESP_FAIL;
    }
    const int head = snprintf(
        part, sizeof(part),
        "--%s\r\nContent-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n",
        kBoundary, static_cast<unsigned>(fb->len));
    esp_err_t res = httpd_resp_send_chunk(req, part, head);
    if (res == ESP_OK) {
      res = httpd_resp_send_chunk(
          req, reinterpret_cast<const char *>(fb->buf), fb->len);
    }
    if (res == ESP_OK) {
      res = httpd_resp_send_chunk(req, "\r\n", 2);
    }
    esp_camera_fb_return(fb);
    if (res != ESP_OK) {
      return res;  // client went away; the server keeps listening
    }
    vTaskDelay(pdMS_TO_TICKS(80));  // ~12 fps ceiling (video/announce spec)
  }
}

bool cameraInit() {
  camera_config_t config = {};
  config.ledc_channel = LEDC_CHANNEL_4;  // motors own 0..3 (motors.cpp)
  config.ledc_timer = LEDC_TIMER_2;      // motor channels sit on timers 0..1
  config.pin_pwdn = CAM_PIN_PWDN;
  config.pin_reset = CAM_PIN_RESET;
  config.pin_xclk = CAM_PIN_XCLK;
  config.pin_sccb_sda = CAM_PIN_SIOD;
  config.pin_sccb_scl = CAM_PIN_SIOC;
  config.pin_d7 = CAM_PIN_D7;
  config.pin_d6 = CAM_PIN_D6;
  config.pin_d5 = CAM_PIN_D5;
  config.pin_d4 = CAM_PIN_D4;
  config.pin_d3 = CAM_PIN_D3;
  config.pin_d2 = CAM_PIN_D2;
  config.pin_d1 = CAM_PIN_D1;
  config.pin_d0 = CAM_PIN_D0;
  config.pin_vsync = CAM_PIN_VSYNC;
  config.pin_href = CAM_PIN_HREF;
  config.pin_pclk = CAM_PIN_PCLK;
  config.xclk_freq_hz = 20000000;
  config.frame_size = FRAMESIZE_SVGA;  // 800x600 per the video/announce spec
  config.pixel_format = PIXFORMAT_JPEG;
  config.grab_mode = CAMERA_GRAB_LATEST;
  config.fb_location = CAMERA_FB_IN_PSRAM;
  config.jpeg_quality = 12;
  config.fb_count = 2;
  return esp_camera_init(&config) == ESP_OK;
}

}  // namespace

bool cameraStreamBegin() {
  if (!cameraInit()) {
    Serial.println("camera: init failed - flying without video");
    return false;
  }
  httpd_config_t config = HTTPD_DEFAULT_CONFIG();
  config.server_port = 81;
  config.ctrl_port = 32081;
  httpd_handle_t server = nullptr;
  if (httpd_start(&server, &config) != ESP_OK) {
    Serial.println("camera: http server failed - flying without video");
    return false;
  }
  static const httpd_uri_t streamUri = {
      .uri = "/stream",
      .method = HTTP_GET,
      .handler = streamHandler,
      .user_ctx = nullptr,
  };
  httpd_register_uri_handler(server, &streamUri);
  Serial.println("camera: MJPEG on :81/stream");
  return true;
}
