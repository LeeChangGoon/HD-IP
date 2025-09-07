#include <WiFi.h>
#include <WebServer.h>
#include <Preferences.h>
#include <WiFiManager.h>

const int relayPin = 18;
WebServer server(80);
Preferences preferences;

IPAddress static_IP(192, 168, 1, 3);
IPAddress gateway(192, 168, 1, 1);
IPAddress subnet(255, 255, 255, 0);
WiFiManager wm;

// [NEW] AP 이름 통일
const char* AP_NAME = "ECR조명제어_5";

// [4] 포털 재진입 가드 플래그
volatile bool portalRunning = false;

// [3] 끊김 후 유예 시간(ms) & 마지막 끊김 시각
const unsigned long PORTAL_GRACE_MS = 15000; // 15초 유예
volatile bool shouldStartPortal = false;
volatile unsigned long lastDisconnectMs = 0;

void onWiFiDisconnect(WiFiEvent_t, WiFiEventInfo_t) {
  Serial.println("Wi-Fi 끊김 감지 → 포털 준비 플래그 설정");
  shouldStartPortal = true;
  lastDisconnectMs = millis();
}

// 릴레이 상태 저장
void saveRelayState(bool state) {
  preferences.begin("light", false);
  preferences.putBool("state", state);
  preferences.end();
}

// 릴레이 상태 불러오기
bool loadRelayState() {
  preferences.begin("light", false);
  bool state = preferences.getBool("state", true); // 기본값: on
  preferences.end();
  return state;
}

// 릴레이 OFF / Light ON 핸들러
void handleRelayOn() {
  digitalWrite(relayPin, HIGH);
  saveRelayState(true);
  server.send(200, "application/json", "{\"status\":\"success\",\"message\":\"Relay ON\"}");
}

// 릴레이 ON / Light OFF 핸들러
void handleRelayOff() {
  digitalWrite(relayPin, LOW);
  saveRelayState(false);
  server.send(200, "application/json", "{\"status\":\"success\",\"message\":\"Relay OFF\"}");
}

// 릴레이 상태 확인 핸들러
void handleStatus() {
  bool state = digitalRead(relayPin);
  String status = (state == LOW) ? "OFF" : "ON";
  server.send(200, "application/json", "{\"status\":\"success\",\"Relay_State\":\"" + status + "\"}");
}
void setup() {
  Serial.begin(115200);
  pinMode(relayPin, OUTPUT);

  // (1) 초기 릴레이 상태 세팅 (원문 유지)
  digitalWrite(relayPin, HIGH);
  saveRelayState(true);

  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);

  wm.setSTAStaticIPConfig(static_IP, gateway, subnet);
  wm.setConfigPortalTimeout(180);
  wm.setConfigPortalBlocking(true);
  wm.setBreakAfterConfig(true);

  // [AP_NAME] 통일
  if (!wm.autoConnect(AP_NAME)) {
    Serial.println("Failed to connect and timed out");
    ESP.restart();
  }
  Serial.println("Wi-Fi connected: " + WiFi.SSID());

  WiFi.onEvent(onWiFiDisconnect, ARDUINO_EVENT_WIFI_STA_DISCONNECTED);

  server.on("/commissioning_relay/on",  handleRelayOn);
  server.on("/commissioning_relay/off", handleRelayOff);
  server.on("/commissioning_relay/status", handleStatus);
  server.begin();
  Serial.println("HTTP server started");
}

void loop() {
  if (shouldStartPortal && !portalRunning) {
    unsigned long elapsed = millis() - lastDisconnectMs;

    // [FIX-2] 유예 중 재연결되었으면 플래그 해제하고 끝
    if (WiFi.status() == WL_CONNECTED) {
      shouldStartPortal = false;
    }
    else if (elapsed < PORTAL_GRACE_MS) {
      // 유예 시간: 자동 재연결 기회 부여
      WiFi.reconnect();
    }
    else {
      // 유예 경과 & 아직 미연결이면 포털 진입
      // [FIX-3] 마지막 순간 재연결되었는지 한 번 더 확인
      if (WiFi.status() != WL_CONNECTED) {
        shouldStartPortal = false;
        portalRunning = true;
        Serial.println(">> 설정 포털 모드로 진입합니다");
        server.stop(); // 80 포트 해제

        // [AP_NAME] 통일
        if (wm.startConfigPortal(AP_NAME)) {
          Serial.println("포털에서 새 설정 저장됨, Wi-Fi 연결 시도 중...");
        } else {
          Serial.println("포털 타임아웃 또는 취소됨");
        }

        // 메인 서버 재시작 (+짧은 안정화 딜레이)
        server.begin();
        delay(50); // [FIX-3] 포트 재바인딩 안정화
        portalRunning = false;
        Serial.println("HTTP 서버 재시작");
      } else {
        shouldStartPortal = false;
      }
    }
  }

  server.handleClient();
}
