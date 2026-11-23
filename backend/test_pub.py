import json
import time
import paho.mqtt.client as mqtt
from dotenv import dotenv_values

config = dotenv_values(".env")

broker = config.get("MQTT_BROKER", "127.0.0.1")
port = int(config.get("MQTT_PORT", "1883"))
username = config.get("MQTT_USERNAME")
password = config.get("MQTT_PASSWORD")
topic = config.get("MQTT_TOPIC", "water-quality/device-01/sensors")

client = mqtt.Client(
    callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
    client_id="smart-bod-test-publisher",
    protocol=mqtt.MQTTv311
)

client.username_pw_set(username, password)
client.connect(broker, port, 60)
client.loop_start()

readings = [
    (54.3, 12.0, 28.8),
    (54.5, 14.0, 28.9),
    (54.4, 16.0, 28.9),
    (54.6, 18.0, 29.0),
    (54.5, 20.0, 29.1),
    (54.7, 22.0, 29.1),
]

for i, (tds, turbidity, temperature) in enumerate(readings, 1):
    payload = {
        "device_id": "device-01",
        "tds": tds,
        "turbidity_index": turbidity,
        "temperature": temperature,
        "tds_voltage": 0.142,
        "turbid ty_sensor_voltage": 2.85,
        "uptime_ms": i * 2000        "uptime_ms": i * 2000  lish(topic, json.dumps(payload), qo        "uptime_ms": i * 2000        "uptime_mf"Published packet {i}: {payload}")
    time.sleep(2)

client.loop_stop()
client.disconnect()

print("\nAll 6 test packets sent.")
