#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// WiFi credentials
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// Server configuration
const char* serverUrl = "http://127.0.0.1:5000";  // Change this to your server's IP
const char* apiKey = "your-secure-api-key-1";     // Must match the key in app.py
const char* deviceId = "ESP32_001";               // Unique device ID

// Pin configuration for sensors
const int pulsePin = 34;     // Analog pin for pulse sensor
const int systolicPin = 35;  // Analog pin for systolic pressure
const int diastolicPin = 32; // Analog pin for diastolic pressure

void setup() {
  Serial.begin(115200);
  
  // Connect to WiFi
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(1000);
    Serial.println("Connecting to WiFi...");
  }
  Serial.println("Connected to WiFi");
  
  // Connect to server
  connectToServer();
}

void loop() {
  if (WiFi.status() == WL_CONNECTED) {
    // Read sensor values (simulated here)
    float systolic = analogRead(systolicPin) / 4095.0 * 50 + 100;  // Range: 100-150
    float diastolic = analogRead(diastolicPin) / 4095.0 * 30 + 60; // Range: 60-90
    float pulse = analogRead(pulsePin) / 4095.0 * 40 + 60;         // Range: 60-100
    
    // Send reading to server
    sendReading(systolic, diastolic, pulse);
    
    // Check connection status
    checkStatus();
  }
  
  delay(5000); // Wait 5 seconds before next reading
}

void connectToServer() {
  HTTPClient http;
  
  // Prepare the URL
  String url = String(serverUrl) + "/api/esp32/connect";
  
  // Prepare JSON data
  StaticJsonDocument<200> doc;
  doc["device_id"] = deviceId;
  
  String jsonString;
  serializeJson(doc, jsonString);
  
  // Send POST request
  http.begin(url);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-API-Key", apiKey);
  
  int httpResponseCode = http.POST(jsonString);
  
  if (httpResponseCode > 0) {
    String response = http.getString();
    Serial.println("Connected to server");
    Serial.println(response);
  } else {
    Serial.print("Error connecting to server: ");
    Serial.println(httpResponseCode);
  }
  
  http.end();
}

void sendReading(float systolic, float diastolic, float pulse) {
  HTTPClient http;
  
  // Prepare the URL
  String url = String(serverUrl) + "/api/workwi/reading";
  
  // Prepare JSON data
  StaticJsonDocument<200> doc;
  doc["device_id"] = deviceId;
  doc["systolic"] = systolic;
  doc["diastolic"] = diastolic;
  doc["pulse"] = pulse;
  
  String jsonString;
  serializeJson(doc, jsonString);
  
  // Send POST request
  http.begin(url);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-API-Key", apiKey);
  
  int httpResponseCode = http.POST(jsonString);
  
  if (httpResponseCode > 0) {
    String response = http.getString();
    Serial.println("Reading sent");
    Serial.println(response);
  } else {
    Serial.print("Error sending reading: ");
    Serial.println(httpResponseCode);
  }
  
  http.end();
}

void checkStatus() {
  HTTPClient http;
  
  // Prepare the URL
  String url = String(serverUrl) + "/api/workwi/status/" + deviceId;
  
  // Send GET request
  http.begin(url);
  http.addHeader("X-API-Key", apiKey);
  
  int httpResponseCode = http.GET();
  
  if (httpResponseCode > 0) {
    String response = http.getString();
    Serial.println("Status checked");
    Serial.println(response);
  } else {
    Serial.print("Error checking status: ");
    Serial.println(httpResponseCode);
  }
  
  http.end();
}
