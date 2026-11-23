from pathlib import Path
import json

import numpy as np
import pandas as pd
import xgboost as xgb
import shap

from scipy.spatial.distance import mahalanobis
from feature_engineering import FeatureEngineer


BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = BASE_DIR / "models"
METADATA_PATH = MODEL_DIR / "bod_metadata.json"


class BODPredictor:
    def __init__(self):
        print("Loading BOD XAI + Confidence models...")

        with open(METADATA_PATH, "r") as file:
            self.metadata = json.load(file)

        self.selected_features = self.metadata["selected_features"]
        self.raw_sensors = self.metadata["raw_sensors"]
        self.window_steps = self.metadata["window_steps"]
        self.confidence_config = self.metadata["confidence_config"]

        # Main BOD model
        self.model = xgb.XGBRegressor()
        self.model.load_model(str(MODEL_DIR / "bod_xgb.json"))

        # Quantile models
        lower_path = MODEL_DIR / self.confidence_config["lower_model_file"]
        upper_path = MODEL_DIR / self.confidence_config["upper_model_file"]

        self.lower_model = xgb.XGBRegressor()
        self.lower_model.load_model(str(lower_path))

        self.upper_model = xgb.XGBRegressor()
        self.upper_model.load_model(str(upper_path))

        # Confidence calibration parameters
        self.alpha = self.confidence_config["alpha"]
        self.conformal_q_hat = self.confidence_config["conformal_q_hat"]
        self.maha_95_threshold = self.confidence_config["maha_95_threshold"]

        self.train_feature_mean = np.array(
            self.confidence_config["train_feature_mean"]
        )

        self.train_feature_cov_inv = np.array(
            self.confidence_config["train_feature_cov_inv"]
        )

        # Feature engineering
        self.feature_engineer = FeatureEngineer(
            window_steps=self.window_steps
        )

        # SHAP explanation engine
        self.explainer = shap.TreeExplainer(self.model)

        print("All BOD models loaded successfully.")
        print(f"Selected features: {len(self.selected_features)}")
        print(f"Window size: {self.window_steps}")
        print(f"Target interval: {(1 - self.alpha) * 100:.0f}%")

    def predict_from_reading(self, tds, turbidity, temperature):

        # 1. Generate features
        features = self.feature_engineer.add_reading(
            tds=tds,
            turbidity=turbidity,
            temperature=temperature
        )

        # Warm-up handling
        if features is None:
            return {
                "ready": False,
                "message": "Waiting for sufficient sensor history",
                "readings_collected": self.feature_engineer.get_history_size()
            }

        missing_features = [
            f for f in self.selected_features if f not in features
        ]

        if missing_features:
            raise ValueError(f"Missing features: {missing_features}")

        # 2. Arrange feature order exactly as training
        X = pd.DataFrame(
            [[features[f] for f in self.selected_features]],
            columns=self.selected_features
        )

        X_np = X.to_numpy(dtype=float)

        # 3. Main prediction
        prediction = float(self.model.predict(X)[0])

        # 4. Conformalized prediction interval
        lower_raw = float(self.lower_model.predict(X)[0])
        upper_raw = float(self.upper_model.predict(X)[0])

        low = max(0.0, lower_raw - self.conformal_q_hat)
        high = max(
            prediction + 0.05,
            upper_raw + self.conformal_q_hat
        )

        low = min(low, prediction)
        half_width = (high - low) / 2.0

        # 5. Confidence from interval sharpness
        rel_uncertainty = half_width / max(prediction, 3.0)
        interval_conf = np.exp(-0.85 * rel_uncertainty)

        # 6. Mahalanobis OOD distance
        maha_dist = float(
            mahalanobis(
                X_np[0],
                self.train_feature_mean,
                self.train_feature_cov_inv
            )
        )

        # Penalize readings outside training distribution
        ood_factor = np.clip(
            1.0 - 0.25 * max(
                0.0,
                (maha_dist - self.maha_95_threshold)
                / self.maha_95_threshold
            ),
            0.50,
            1.0
        )

        confidence_pct = float(
            np.clip(interval_conf * ood_factor * 100.0, 5.0, 99.9)
        )

        if confidence_pct >= 80.0:
            confidence_tier = "High"
        elif confidence_pct >= 60.0:
            confidence_tier = "Medium"
        else:
            confidence_tier = "Low"

        # 7. Local SHAP explanation
        shap_values = self.explainer.shap_values(X)

        shap_row = np.asarray(shap_values)[0]

        top_indices = np.argsort(np.abs(shap_row))[::-1][:3]

        top_drivers = [
            {
                "feature": self.selected_features[int(idx)],
                "impact": round(float(shap_row[idx]), 4)
            }
            for idx in top_indices
        ]

        # 8. Final result
        return {
            "ready": True,
            "predicted_bod": prediction,
            "prediction_interval": {
                "low": float(low),
                "high": float(high),
                "level": int((1 - self.alpha) * 100)
            },
            "uncertainty": float(half_width),
            "confidence": confidence_pct,
            "confidence_tier": confidence_tier,
            "mahalanobis_distance": maha_dist,
            "ood_factor": float(ood_factor),
            "shap_values": {
                feature: round(float(value), 4)
                for feature, value in zip(
                    self.selected_features, shap_row
                )
            },
            "top_shap_drivers": top_drivers,
            "unit": "mg/L",
            "sensor_values": {
                "tds": float(tds),
                "turbidity": float(turbidity),
                "temperature": float(temperature)
            }
        }

    def reset_history(self):
        self.feature_engineer.reset()


if __name__ == "__main__":
    predictor = BODPredictor()

    test_readings = [
        (105, 900, 24.8),
        (108, 910, 24.9),
        (106, 920, 25.0),
        (110, 915, 25.1),
        (112, 930, 25.2),
        (109, 940, 25.2),
    ]

    for i, (tds, turbidity, temperature) in enumerate(
        test_readings, start=1
    ):
        result = predictor.predict_from_reading(
            tds=tds,
            turbidity=turbidity,
            temperature=temperature
        )

        print(f"\nPacket {i}")

        if not result["ready"]:
            print(result["message"])
            print("Readings collected:", result["readings_collected"])
        else:
            print(f"BOD: {result['predicted_bod']:.4f} mg/L")
            print(f"Interval: {result['prediction_interval']}")
            print(f"Uncertainty: ±{result['uncertainty']:.4f}")
            print(f"Confidence: {result['confidence']:.1f}%")
            print(f"Tier: {result['confidence_tier']}")
            print(f"Top SHAP drivers: {result['top_shap_drivers']}")