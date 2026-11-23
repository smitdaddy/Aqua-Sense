
#include <Arduino.h>
#include <math.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <OneWire.h>
#include <DallasTemperature.h>

// =====================================================
// WIFI CONFIGURATION
// =====================================================

const char* WIFI_SSID = "Binod";
const char* WIFI_PASSWORD = "12345678";

// =====================================================
// MQTT CONFIGURATION
// =====================================================

const char* MQTT_SERVER = "10.146.196.229";
const int MQTT_PORT = 1883;

const char* MQTT_USER = "esp32_device";
const char* MQTT_PASSWORD = "Maisinglehu69";

const char* MQTT_TOPIC = "water-quality/device-01/sensors";

WiFiClient espClient;
PubSubClient mqttClient(espClient);

unsigned long lastMqttAttempt = 0;
const unsigned long MQTT_RECONNECT_INTERVAL = 5000;

// =====================================================
// SENSOR PIN CONFIGURATION
// =====================================================

constexpr uint8_t TURBIDITY_PIN = 34;
constexpr uint8_t TDS_PIN = 35;
constexpr uint8_t DS18B20_PIN = 4;

// =====================================================
// DS18B20 CONFIGURATION
// =====================================================

#define USE_DS18B20 1

OneWire oneWire(DS18B20_PIN);
DallasTemperature tempSensors(&oneWire);

constexpr float DEFAULT_WATER_TEMP_C = 25.0f;

bool temperatureSensorValid = false;

// =====================================================
// TURBIDITY VOLTAGE DIVIDER
// =====================================================

constexpr float R1_OHMS = 20000.0f;
constexpr float R2_OHMS = 10000.0f;

constexpr float DIVIDER_MULTIPLIER =
    (R1_OHMS + R2_OHMS) / R2_OHMS;

// =====================================================
// TURBIDITY CALIBRATION
// Based on your measured voltage readings
// =====================================================

// Clear water reference
constexpr float TURB_CLEAR_V = 1.05f;

// Dirty water reference
constexpr float TURB_DIRTY_V = 0.675f;

// Exponential filter
constexpr float TURB_FILTER_ALPHA = 0.25f;

float filteredTurbidityVoltage = 0.0f;
bool turbidityFilterInitialized = false;

// =====================================================
// TDS CONFIGURATION
// =====================================================

constexpr float TDS_K_FACTOR = 1.0f;

constexpr int TDS_SAMPLE_COUNT = 30;
constexpr int TDS_SAMPLE_DELAY_MS = 10;

// =====================================================
// SAMPLING CONFIGURATION
// =====================================================

constexpr int TURB_SAMPLE_COUNT = 50;
constexpr int TURB_SAMPLE_DELAY_MS = 5;

constexpr unsigned long READ_INTERVAL_MS = 2000;

unsigned long lastReadTime = 0;

// =====================================================
// WIFI CONNECTION
// =====================================================

void connectWiFi() {

  if (WiFi.status() == WL_CONNECTED) return;

  Serial.println("[WIFI] Connecting...");

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  unsigned long start = millis();

  while (WiFi.status() != WL_CONNECTED &&
         millis() - start < 20000) {

    delay(500);
    Serial.print(".");
  }

  if (WiFi.status() == WL_CONNECTED) {

    Serial.println("\n[WIFI] Connected!");

    Serial.print("[WIFI] ESP32 IP: ");
    Serial.println(WiFi.localIP());

  } else {

    Serial.println("\n[WIFI] Connection failed!");
  }
}

// =====================================================
// MQTT CONNECTION
// =====================================================

void connectMQTT() {

  if (WiFi.status() != WL_CONNECTED) return;

  if (mqttClient.connected()) return;

  if (millis() - lastMqttAttempt <
      MQTT_RECONNECT_INTERVAL) {
    return;
  }

  lastMqttAttempt = millis();

  Serial.print("[MQTT] Connecting to ");
  Serial.println(MQTT_SERVER);

  String clientId =
      "ESP32-WaterMonitor-" +
      String((uint32_t)ESP.getEfuseMac(), HEX);

  if (mqttClient.connect(
        clientId.c_str(),
        MQTT_USER,
        MQTT_PASSWORD)) {

    Serial.println("[MQTT] Connected successfully!");

  } else {

    Serial.print("[MQTT] Connection failed. State: ");
    Serial.println(mqttClient.state());
  }
}

// =====================================================
// GENERIC FILTERED VOLTAGE READING
// Used by TDS
// =====================================================

float readFilteredMilliVolts(
    uint8_t pin,
    int sampleCount,
    int sampleDelay) {

  uint32_t samples[sampleCount];

  for (int i = 0; i < sampleCount; i++) {

    samples[i] = analogReadMilliVolts(pin);

    delay(sampleDelay);
  }

  // Sort samples
  for (int i = 1; i < sampleCount; i++) {

    uint32_t key = samples[i];

    int j = i - 1;

    while (j >= 0 && samples[j] > key) {

      samples[j + 1] = samples[j];
      j--;
    }

    samples[j + 1] = key;
  }

  // Remove lowest and highest 20%
  int trim = sampleCount / 5;

  uint32_t sum = 0;
  int count = 0;

  for (int i = trim; i < sampleCount - trim; i++) {

    sum += samples[i];
    count++;
  }

  if (count == 0) return 0.0f;

  return (float)sum / count;
}

// =====================================================
// TURBIDITY VOLTAGE READING
// =====================================================

float readTurbidityVoltage() {

  uint32_t samples[TURB_SAMPLE_COUNT];

  // Collect ADC voltage samples
  for (int i = 0; i < TURB_SAMPLE_COUNT; i++) {

    samples[i] = analogReadMilliVolts(TURBIDITY_PIN);

    delay(TURB_SAMPLE_DELAY_MS);
  }

  // Sort samples
  for (int i = 1; i < TURB_SAMPLE_COUNT; i++) {

    uint32_t key = samples[i];

    int j = i - 1;

    while (j >= 0 && samples[j] > key) {

      samples[j + 1] = samples[j];
      j--;
    }

    samples[j + 1] = key;
  }

  // Trim lowest and highest 20%
  int trim = TURB_SAMPLE_COUNT / 5;

  uint32_t sum = 0;
  int count = 0;

  for (int i = trim; i < TURB_SAMPLE_COUNT - trim; i++) {

    sum += samples[i];
    count++;
  }

  if (count == 0) return 0.0f;

  float adcVoltage =
      (sum / (float)count) / 1000.0f;

  // Reconstruct sensor voltage before divider
  float sensorVoltage =
      adcVoltage * DIVIDER_MULTIPLIER;

  // Apply exponential smoothing
  if (!turbidityFilterInitialized) {

    filteredTurbidityVoltage = sensorVoltage;

    turbidityFilterInitialized = true;

  } else {

    filteredTurbidityVoltage =
        TURB_FILTER_ALPHA * sensorVoltage +
        (1.0f - TURB_FILTER_ALPHA) *
        filteredTurbidityVoltage;
  }

  return filteredTurbidityVoltage;
}

// =====================================================
// TURBIDITY INDEX CALCULATION
// Output: 0 to 100
// This is NOT actual NTU
// =====================================================

float calculateTurbidityIndex(float voltage) {

  float index =
      ((TURB_CLEAR_V - voltage) /
       (TURB_CLEAR_V - TURB_DIRTY_V)) * 100.0f;

  return constrain(index, 0.0f, 100.0f);
}

// =====================================================
// TURBIDITY STATUS
// =====================================================

const char* getTurbidityStatus(float index) {

  if (index <= 10.0f)
    return "CLEAR";

  else if (index <= 40.0f)
    return "SLIGHTLY CLOUDY";

  else if (index <= 70.0f)
    return "MODERATELY TURBID";

  else
    return "HIGHLY TURBID";
}

// =====================================================
// TDS CALCULATION
// =====================================================

float calculateTDS(
    float tdsVoltage,
    float waterTempC) {

  if (tdsVoltage < 0.02f) return 0.0f;

  float compensationCoeff =
      1.0f + 0.02f * (waterTempC - 25.0f);

  float compensationVoltage =
      tdsVoltage / compensationCoeff;

  float tdsPpm =
      (133.42f * powf(compensationVoltage, 3)
       - 255.86f * powf(compensationVoltage, 2)
       + 857.39f * compensationVoltage) * 0.5f;

  tdsPpm *= TDS_K_FACTOR;

  return tdsPpm > 0.0f ? tdsPpm : 0.0f;
}

// =====================================================
// TDS STATUS
// =====================================================

const char* getTDSStatus(float tdsPpm) {

  if (tdsPpm < 5.0f)
    return "PROBE DRY / DISTILLED";

  if (tdsPpm <= 150.0f)
    return "EXCELLENT";

  if (tdsPpm <= 300.0f)
    return "GOOD";

  if (tdsPpm <= 500.0f)
    return "ACCEPTABLE";

  return "HIGH TDS";
}

// =====================================================
// DS18B20 TEMPERATURE READING
// =====================================================

float readWaterTemperatureC() {

#if USE_DS18B20

  tempSensors.requestTemperatures();

  float tempC =
      tempSensors.getTempCByIndex(0);

  if (tempC == DEVICE_DISCONNECTED_C ||
      !isfinite(tempC) ||
      tempC < -10.0f ||
      tempC > 85.0f) {

    temperatureSensorValid = false;

    Serial.println("[WARN] DS18B20 invalid reading!");

    return DEFAULT_WATER_TEMP_C;
  }

  temperatureSensorValid = true;

  return tempC;

#else

  temperatureSensorValid = false;

  return DEFAULT_WATER_TEMP_C;

#endif
}

// =====================================================
// MQTT DATA PUBLISHING
// =====================================================

void publishSensorData(
    float tds,
    float turbidityIndex,
    float temperature,
    float tdsVoltage,
    float turbidityVoltage,
    bool temperatureValid) {

  if (!mqttClient.connected()) {

    Serial.println("[MQTT] Not connected. Data not published.");

    return;
  }

  char payload[320];

  snprintf(
    payload,
    sizeof(payload),

    "{\"device_id\":\"device-01\","
    "\"tds\":%.2f,"
    "\"turbidity_index\":%.2f,"
    "\"temperature\":%.2f,"
    "\"temperature_valid\":%s,"
    "\"tds_voltage\":%.3f,"
    "\"turbidity_sensor_voltage\":%.3f,"
    "\"uptime_ms\":%lu}",

    tds,
    turbidityIndex,
    temperature,
    temperatureValid ? "true" : "false",
    tdsVoltage,
    turbidityVoltage,
    millis()
  );

  bool success = mqttClient.publish(
      MQTT_TOPIC,
      payload
  );

  if (success) {

    Serial.println("[MQTT] Data published:");

    Serial.println(payload);

  } else {

    Serial.println("[MQTT] Publish failed!");
  }
}

// =====================================================
// SETUP
// =====================================================

void setup() {

  Serial.begin(115200);

  delay(1000);

  // ADC configuration
  analogReadResolution(12);

  analogSetPinAttenuation(
      TURBIDITY_PIN,
      ADC_11db
  );

  analogSetPinAttenuation(
      TDS_PIN,
      ADC_11db
  );

  pinMode(TURBIDITY_PIN, INPUT);
  pinMode(TDS_PIN, INPUT);

  // Initialize DS18B20
#if USE_DS18B20

  Serial.println("[TEMP] Initializing DS18B20...");

  tempSensors.begin();

  tempSensors.setResolution(12);

  tempSensors.setWaitForConversion(true);

  Serial.print("[TEMP] Sensors detected: ");

  Serial.println(tempSensors.getDeviceCount());

#endif

  // Configure MQTT
  mqttClient.setServer(
      MQTT_SERVER,
      MQTT_PORT
  );

  mqttClient.setBufferSize(512);

  mqttClient.setKeepAlive(30);

  // Connect Wi-Fi
  connectWiFi();

  Serial.println("\n======================================");

  Serial.println(" ESP32 SMART BOD MONITOR");

  Serial.println("======================================");

  Serial.print("MQTT Broker: ");
  Serial.println(MQTT_SERVER);

  Serial.print("MQTT Topic: ");
  Serial.println(MQTT_TOPIC);

  Serial.println("Turbidity: NORMALIZED INDEX");

  Serial.println("Turbidity Pin: GPIO 34");

  Serial.println("TDS Pin: GPIO 35");

  Serial.println("Temperature Pin: GPIO 4");

  Serial.println("======================================");
}

// =====================================================
// MAIN LOOP
// =====================================================

void loop() {

  // Maintain Wi-Fi
  if (WiFi.status() != WL_CONNECTED) {

    connectWiFi();
  }

  // Maintain MQTT
  connectMQTT();

  mqttClient.loop();

  // Sensor reading interval
  if (millis() - lastReadTime < READ_INTERVAL_MS) {

    return;
  }

  lastReadTime = millis();

  // -----------------------------------
  // TEMPERATURE
  // -----------------------------------

  float waterTempC =
      readWaterTemperatureC();

  // -----------------------------------
  // TDS
  // -----------------------------------

  float tdsMilliVolts =
      readFilteredMilliVolts(
          TDS_PIN,
          TDS_SAMPLE_COUNT,
          TDS_SAMPLE_DELAY_MS
      );

  float tdsVoltage =
      tdsMilliVolts / 1000.0f;

  float tdsPpm =
      calculateTDS(
          tdsVoltage,
          waterTempC
      );

  // -----------------------------------
  // TURBIDITY
  // -----------------------------------

  float turbSensorVoltage =
      readTurbidityVoltage();

  float turbidityIndex =
      calculateTurbidityIndex(
          turbSensorVoltage
      );

  const char* turbidityStatus =
      getTurbidityStatus(turbidityIndex);

  // -----------------------------------
  // DISPLAY RESULTS
  // -----------------------------------

  Serial.println("\n--------------------------------------");

  Serial.printf(
      "Temperature       : %.2f C\n",
      waterTempC
  );

  Serial.printf(
      "Temperature Valid : %s\n",
      temperatureSensorValid ? "YES" : "NO"
  );

  Serial.printf(
      "TDS Voltage       : %.3f V\n",
      tdsVoltage
  );

  Serial.printf(
      "TDS               : %.2f ppm\n",
      tdsPpm
  );

  Serial.printf(
      "TDS Status        : %s\n",
      getTDSStatus(tdsPpm)
  );

  Serial.printf(
      "Turbidity Voltage : %.3f V\n",
      turbSensorVoltage
  );

  Serial.printf(
      "Turbidity Index   : %.2f / 100\n",
      turbidityIndex
  );

  Serial.printf(
      "Turbidity Status  : %s\n",
      turbidityStatus
  );

  // -----------------------------------
  // MQTT PUBLISH
  // -----------------------------------

  publishSensorData(
      tdsPpm,
      turbidityIndex,
      waterTempC,
      tdsVoltage,
      turbSensorVoltage,
      temperatureSensorValid
  );

  Serial.println("--------------------------------------");
}
