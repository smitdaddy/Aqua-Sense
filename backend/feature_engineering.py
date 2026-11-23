import math
from collections import deque


class FeatureEngineer:
    """
    Reproduces the selected domain and temporal features from the
    BOD_SoftSensor_3Feature_Pipeline_XAI_Confidence notebook.

    Input sensors:
        TDS (ppm)
        Turbidity (NTU)
        Temperature (cel)

    Prediction warm-up:
        Requires 4 readings to support lag-3 features.

    Rolling window:
        6 readings.
    """

    def __init__(self, window_steps=6):
        self.window_steps = window_steps
        self.history = deque(maxlen=window_steps)

        self.selected_features = [
            "Log_Turbidity",
            "Turb_x_Temp",
            "Turbidity (NTU)",
            "Sqrt_Turbidity",
            "TDS_x_Turb",
            "Turb_to_TDS_Ratio",
            "Turb_diff1",
            "Log_TDS",
            "TDS_x_Temp",
            "TDS (ppm)",
            "TDS_TempCompensated",
            "Turb_roll_max",
        ]

    def reset(self):
        """Reset history when starting a new device/session."""
        self.history.clear()
        
    def get_history_size(self):
     return len(self.history)

    def add_reading(self, tds, turbidity, temperature):
        """
        Add one sensor reading.

        Returns:
            None during warm-up.
            dict containing the selected model features once ready.
        """

        reading = {
            "TDS (ppm)": float(tds),
            "Turbidity (NTU)": float(turbidity),
            "Temperature (cel)": float(temperature),
        }

        # Reject invalid values
        if not all(math.isfinite(v) for v in reading.values()):
            raise ValueError("Sensor values must be finite numbers.")

        if reading["TDS (ppm)"] < 0:
            raise ValueError("TDS cannot be negative.")

        if reading["Turbidity (NTU)"] < 0:
            raise ValueError("Turbidity cannot be negative.")

        # Add current reading to rolling history
        self.history.append(reading)

        # Notebook drops rows missing lag-3 features.
        # This means at least 4 readings are needed.
        if len(self.history) < 4:
            return None

        readings = list(self.history)

        current = readings[-1]
        previous = readings[-2]

        tds = current["TDS (ppm)"]
        turb = current["Turbidity (NTU)"]
        temp = current["Temperature (cel)"]

        previous_turb = previous["Turbidity (NTU)"]

        # ----------------------------------
        # Domain / nonlinear features
        # ----------------------------------

        log_turbidity = math.log1p(turb)
        sqrt_turbidity = math.sqrt(turb)

        tds_x_temp = tds * temp
        turb_x_temp = turb * temp
        tds_x_turb = tds * turb

        temp_comp_factor = 1.0 + 0.02 * (temp - 25.0)

        # Avoid invalid compensation divisor
        if temp_comp_factor <= 0:
            raise ValueError("Invalid temperature compensation factor.")

        tds_temp_compensated = tds / temp_comp_factor

        turb_to_tds_ratio = turb / (tds + 1.0)

        # ----------------------------------
        # Temporal features
        # ----------------------------------

        turb_diff1 = turb - previous_turb

        # Equivalent to pandas rolling(window=6, min_periods=1).max()
        turb_roll_max = max(
            r["Turbidity (NTU)"] for r in readings
        )

        # ----------------------------------
        # Build model input
        # ----------------------------------

        features = {
            "Log_Turbidity": log_turbidity,
            "Turb_x_Temp": turb_x_temp,
            "Turbidity (NTU)": turb,
            "Sqrt_Turbidity": sqrt_turbidity,
            "TDS_x_Turb": tds_x_turb,
            "Turb_to_TDS_Ratio": turb_to_tds_ratio,
            "Turb_diff1": turb_diff1,
            "Log_TDS": math.log1p(tds),
            "TDS_x_Temp": tds_x_temp,
            "TDS (ppm)": tds,
            "TDS_TempCompensated": tds_temp_compensated,
            "Turb_roll_max": turb_roll_max,
        }

        # Preserve exact metadata/model feature order
        return {
            feature: features[feature]
            for feature in self.selected_features
        }