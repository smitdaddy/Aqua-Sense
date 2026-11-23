
import json
import logging
import math
import sys
from pathlib import Path

import paho.mqtt.client as mqtt
from dotenv import dotenv_values

from model_predictor import BODPredictor
from database import SupabaseDatabase


# ============================================================
# 1. CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"
CONFIG = dotenv_values(ENV_FILE)

MQTT_BROKER = CONFIG.get("MQTT_BROKER") or "127.0.0.1"
MQTT_PORT = int(CONFIG.get("MQTT_PORT") or "1883")
MQTT_USERNAME = CONFIG.get("MQTT_USERNAME")
MQTT_PASSWORD = CONFIG.get("MQTT_PASSWORD")
MQTT_TOPIC = CONFIG.get("MQTT_TOPIC") or "water-quality/device-01/sensors"

CLIENT_ID = "smart-bod-python-subscriber"
KEEPALIVE = 60

# Persistent instances
predictor = None
database = None


# ============================================================
# 2. LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S"
)

logger = logging.getLogger(__name__)


# ============================================================
# 3. CONFIGURATION VALIDATION
# ============================================================

def validate_config():

    print("\n========== CONFIGURATION CHECK ==========")
    print("Environment file:", ENV_FILE)
    print("File exists:", ENV_FILE.exists())
    print("Broker:", f"{MQTT_BROKER}:{MQTT_PORT}")
    print("Username loaded:", bool(MQTT_USERNAME))
    print("Password loaded:", bool(MQTT_PASSWORD))
    print("Topic:", MQTT_TOPIC)

    if not ENV_FILE.exists():
        raise FileNotFoundError(f".env file not found: {ENV_FILE}")

    if not MQTT_USERNAME or not MQTT_PASSWORD:
        raise ValueError("MQTT username or password is missing in .env")

    print("Configuration loaded successfully!")
    print("====================================\n")


# ============================================================
# 4. SENSOR DATA VALIDATION
# ============================================================

def validate_sensor_data(data):

    if not isinstance(data, dict):
        raise ValueError("Payload must be a JSON object.")

    # Normalize ESP32 field name
    if "turbidity" not in data and "turbidity_index" in data:
        data["turbidity"] = data["turbidity_index"]

    required_fields = [
        "device_id",
        "tds",
        "turbidity",
        "temperature"
    ]

    for field in required_fields:
        if field not in data:
            raise ValueError(f"Missing field: {field}")

    # Convert sensor values to floats
    for field in ["tds", "turbidity", "temperature"]:
        try:
            data[field] = float(data[field])
        except (ValueError, TypeError):
            raise ValueError(f"Invalid value for {field}")

        if not math.isfinite(data[field]):
            raise ValueError(f"{field} must be a finite number.")

    # Validate ranges
    if data["tds"] < 0:
        raise ValueError("TDS cannot be negative.")

    if data["turbidity"] < 0:
        raise ValueError("Turbidity cannot be negative.")

    if not -10 <= data["temperature"] <= 85:
        raise ValueError("Temperature outside expected range.")

    return data


# ============================================================
# 5. MQTT CONNECTION CALLBACK
# ============================================================

def on_connect(client, userdata, flags, reason_code, properties):

    if not reason_code.is_failure:

        logger.info("Connected to Mosquitto successfully!")

        result, mid = client.subscribe(MQTT_TOPIC, qos=1)

        if result == mqtt.MQTT_ERR_SUCCESS:
            logger.info("Subscribed to topic: %s", MQTT_TOPIC)
        else:
            logger.error("Subscription failed: %s", result)

    else:
        logger.error("MQTT connection rejected: %s", reason_code)


# ============================================================
# 6. SUBSCRIPTION CALLBACK
# ============================================================

def on_subscribe(client, userdata, mid, reason_code_list, properties):
    logger.info("Subscription acknowledged.")


# ============================================================
# 7. MESSAGE CALLBACK
# ============================================================

def on_message(client, userdata, msg):

    global predictor, database

    try:

        # ----------------------------------------------------
        # Decode incoming MQTT payload
        # ----------------------------------------------------

        payload = msg.payload.decode("utf-8")
        data = json.loads(payload)
        data = validate_sensor_data(data)

        # ----------------------------------------------------
        # Extract sensor values
        # ----------------------------------------------------

        device_id = data["device_id"]
        tds = data["tds"]
        turbidity = data["turbidity"]
        temperature = data["temperature"]

        # ----------------------------------------------------
        # Generate BOD prediction
        # ----------------------------------------------------

        prediction_result = predictor.predict_from_reading(
            tds=tds,
            turbidity=turbidity,
            temperature=temperature
        )

        ready = prediction_result["ready"]

        predicted_bod = (
            prediction_result["predicted_bod"]
            if ready
            else None
        )

        # ----------------------------------------------------
        # Extract enhanced model metadata
        # ----------------------------------------------------

        prediction_interval = None
        uncertainty = None
        confidence = None
        confidence_tier = None
        mahalanobis_distance = None
        ood_factor = None
        shap_values = None
        top_shap_drivers = None

        if ready:

            prediction_interval = prediction_result["prediction_interval"]
            uncertainty = prediction_result["uncertainty"]
            confidence = prediction_result["confidence"]
            confidence_tier = prediction_result["confidence_tier"]
            mahalanobis_distance = prediction_result["mahalanobis_distance"]
            ood_factor = prediction_result["ood_factor"]
            shap_values = prediction_result["shap_values"]
            top_shap_drivers = prediction_result["top_shap_drivers"]

        # ----------------------------------------------------
        # SAVE READING AND PREDICTION TO SUPABASE
        # ----------------------------------------------------

        try:

            database.insert_sensor_reading(
                device_id=device_id,
                tds=tds,
                turbidity=turbidity,
                temperature=temperature,
                predicted_bod=predicted_bod,
                prediction_interval=prediction_interval,
                uncertainty=uncertainty,
                confidence=confidence,
                confidence_tier=confidence_tier,
                mahalanobis_distance=mahalanobis_distance,
                ood_factor=ood_factor,
                shap_values=shap_values,
                top_shap_drivers=top_shap_drivers
            )

            logger.info("Sensor reading saved to Supabase.")

        except Exception:
            # DB failure should not interrupt MQTT processing
            logger.exception("Failed to save sensor reading to Supabase.")

        # ----------------------------------------------------
        # DISPLAY SENSOR READINGS
        # ----------------------------------------------------

        print("\n" + "=" * 65)
        print("             SMART BOD - LIVE SENSOR MONITOR")
        print("=" * 65)

        print(f"Device ID      : {device_id}")
        print(f"TDS            : {tds:.2f} ppm")
        print(f"Turbidity      : {turbidity:.2f} NTU")
        print(f"Temperature    : {temperature:.2f} °C")

        if "tds_voltage" in data:
            print(f"TDS Voltage    : {data['tds_voltage']} V")

        if "turbidity_sensor_voltage" in data:
            print(f"Turbidity Volt : {data['turbidity_sensor_voltage']} V")

        elif "turbidity_voltage" in data:
            print(f"Turbidity Volt : {data['turbidity_voltage']} V")

        if "uptime_ms" in data:
            print(f"Uptime         : {data['uptime_ms']} ms")

        print("-" * 65)

        # ----------------------------------------------------
        # DISPLAY PREDICTION OR WARM-UP STATUS
        # ----------------------------------------------------

        if ready:

            interval = prediction_interval
            drivers = top_shap_drivers or []

            print("BOD PREDICTION")
            print(f"Predicted BOD  : {predicted_bod:.4f} mg/L")

            print(
                f"{interval['level']}% Interval    : "
                f"{interval['low']:.4f} - "
                f"{interval['high']:.4f} mg/L"
            )

            print(
                f"Uncertainty    : "
                f"±{uncertainty:.4f} mg/L"
            )

            print(f"Confidence     : {confidence:.1f}%")
            print(f"Confidence Tier: {confidence_tier}")

            print(
                f"OOD Distance  : "
                f"{mahalanobis_distance:.4f}"
            )

            print(
                f"OOD Factor    : "
                f"{ood_factor:.4f}"
            )

            print("-" * 65)
            print("TOP SHAP DRIVERS")

            for driver in drivers:

                impact = driver["impact"]
                direction = "↑" if impact > 0 else "↓"

                print(
                    f"  {direction} {driver['feature']:<25} "
                    f"{impact:+.4f}"
                )

            print("-" * 65)
            print("Status         : Enhanced prediction generated")

        else:

            collected = prediction_result["readings_collected"]

            print("BOD PREDICTION")
            print("Status         : Warming up feature history")
            print(f"History        : {collected}/4 readings collected")
            print("Prediction     : Not available yet")

        print("=" * 65)

    # --------------------------------------------------------
    # ERROR HANDLING
    # --------------------------------------------------------

    except json.JSONDecodeError:
        logger.error("Invalid JSON received.")

    except (UnicodeDecodeError, ValueError) as error:
        logger.error("Invalid sensor data: %s", error)

    except Exception:
        logger.exception("Unexpected message processing error.")


# ============================================================
# 8. DISCONNECTION CALLBACK
# ============================================================

def on_disconnect(
    client,
    userdata,
    disconnect_flags,
    reason_code,
    properties
):

    if reason_code.is_failure:
        logger.warning("Unexpected disconnection: %s", reason_code)
    else:
        logger.info("Disconnected from MQTT broker.")


# ============================================================
# 9. MAIN FUNCTION
# ============================================================

def main():

    global predictor, database

    validate_config()

    # --------------------------------------------------------
    # Load ML model once at startup
    # --------------------------------------------------------

    logger.info("Initializing BOD predictor...")

    predictor = BODPredictor()

    logger.info("BOD predictor ready!")

    # --------------------------------------------------------
    # Initialize Supabase database
    # --------------------------------------------------------

    logger.info("Initializing Supabase database...")

    database = SupabaseDatabase()

    if database.test_connection():
        logger.info("Supabase database ready!")
    else:
        logger.warning("Supabase connection check failed!")

    # --------------------------------------------------------
    # Create MQTT client
    # --------------------------------------------------------

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=CLIENT_ID,
        protocol=mqtt.MQTTv311
    )

    # MQTT authentication
    client.username_pw_set(
        MQTT_USERNAME,
        MQTT_PASSWORD
    )

    # Register callbacks
    client.on_connect = on_connect
    client.on_subscribe = on_subscribe
    client.on_message = on_message
    client.on_disconnect = on_disconnect

    # Automatic reconnection
    client.reconnect_delay_set(
        min_delay=1,
        max_delay=30
    )

    # --------------------------------------------------------
    # Connect and listen
    # --------------------------------------------------------

    try:

        logger.info(
            "Connecting to broker %s:%s...",
            MQTT_BROKER,
            MQTT_PORT
        )

        client.connect(
            MQTT_BROKER,
            MQTT_PORT,
            KEEPALIVE
        )

        logger.info("Waiting for ESP32 sensor data...")
        client.loop_forever()

    except KeyboardInterrupt:
        logger.info("Stopping subscriber...")

    except Exception:
        logger.exception("MQTT subscriber failed.")
        sys.exit(1)

    finally:
        client.disconnect()
        logger.info("Subscriber stopped.")


# ============================================================
# 10. ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
