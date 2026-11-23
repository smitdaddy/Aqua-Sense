
import os
from pathlib import Path

from dotenv import dotenv_values
from supabase import create_client


# Load configuration from backend/.env
BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"
CONFIG = dotenv_values(ENV_FILE)


class SupabaseDatabase:
    def __init__(self):
        supabase_url = CONFIG.get("SUPABASE_URL")
        supabase_key = CONFIG.get("SUPABASE_KEY")

        if not supabase_url or not supabase_key:
            raise ValueError("Supabase credentials missing from .env")

        self.client = create_client(supabase_url, supabase_key)
        self.table_name = "sensor_readings"

        print("Supabase database initialized.")

    def insert_sensor_reading(
        self,
        device_id,
        tds,
        turbidity,
        temperature,
        predicted_bod=None,
        shap_values=None,
        prediction_interval=None,
        uncertainty=None,
        confidence=None,
        confidence_tier=None,
        mahalanobis_distance=None,
        ood_factor=None,
        top_shap_drivers=None,
        model_name="xgb_bod_soft_sensor",
    ):
        """
        Insert sensor readings, BOD prediction, explainability,
        and model confidence information.

        Prediction-related fields can be None during model warm-up.
        """

        payload = {
            "device_id": device_id,
            "tds_ppm": float(tds),
            "turbidity_ntu": float(turbidity),
            "temperature_c": float(temperature),
            "predicted_bod": (
                float(predicted_bod) if predicted_bod is not None else None
            ),
            "model_name": model_name,

            # Model uncertainty and confidence
            "prediction_interval": prediction_interval,
            "uncertainty": uncertainty,
            "confidence": confidence,
            "confidence_tier": confidence_tier,

            # Out-of-distribution detection
            "mahalanobis_distance": mahalanobis_distance,
            "ood_factor": ood_factor,

            # Explainability
            "shap_values": shap_values,
            "top_shap_drivers": top_shap_drivers,
        }

        try:
            response = (
                self.client
                .table(self.table_name)
                .insert(payload)
                .execute()
            )

            return response.data

        except Exception as e:
            print(f"Database insert failed: {e}")
            raise

    def test_connection(self):
        """Verify that the database table is accessible."""

        try:
            response = (
                self.client
                .table(self.table_name)
                .select("id")
                .limit(1)
                .execute()
            )

            print("Supabase connection successful!")
            print(f"Table '{self.table_name}' is accessible.")
            return True

        except Exception as e:
            print(f"Supabase connection failed: {e}")
            return False
