
from fastapi import FastAPI, HTTPException, Query
from statistics import mean
from fastapi.middleware.cors import CORSMiddleware

from database import SupabaseDatabase


# ============================================================
# 1. APP CONFIGURATION
# ============================================================

app = FastAPI(
    title="Smart BOD Soft Sensor API",
    description="API for IoT-based water quality monitoring and BOD prediction",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database connection
database = SupabaseDatabase()


# ============================================================
# 2. FEATURE EXPLANATION MAPPING
# ============================================================

FEATURE_EXPLANATIONS = {
    "Turb_x_Temp": {
        "name": "Turbidity–temperature interaction",
        "description": "The combined effect of turbidity and water temperature on the model prediction."
    },
    "TDS_x_Turb": {
        "name": "TDS–turbidity interaction",
        "description": "How dissolved solids and turbidity together influence the prediction."
    },
    "Log_Turbidity": {
        "name": "Turbidity level",
        "description": "The model's transformed representation of the turbidity measurement."
    },
    "Log_TDS": {
        "name": "Dissolved solids level",
        "description": "The model's transformed representation of TDS."
    },
    "TDS_TempCompensated": {
        "name": "Temperature-adjusted TDS",
        "description": "TDS adjusted by temperature as part of the model's feature engineering."
    },
    "Turb_to_TDS_Ratio": {
        "name": "Turbidity relative to TDS",
        "description": "The relationship between turbidity and dissolved solids."
    },
    "Turb_diff1": {
        "name": "Recent turbidity change",
        "description": "How turbidity has changed compared with a recent reading."
    },
    "Turb_roll_max": {
        "name": "Recent peak turbidity",
        "description": "The maximum turbidity observed within the model's recent history window."
    },
    "TDS_x_Temp": {
        "name": "TDS–temperature interaction",
        "description": "The combined influence of dissolved solids and temperature."
    },
    "Sqrt_Turbidity": {
        "name": "Turbidity trend representation",
        "description": "A square-root transformed turbidity feature used by the model."
    }
}


# ============================================================
# 3. HEALTH & ROOT ENDPOINTS
# ============================================================

@app.get("/")
def root():
    return {
        "message": "Smart BOD Soft Sensor API is running!",
        "status": "healthy",
        "version": "2.0.0"
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "smart-bod-api"
    }


# ============================================================
# 4. LATEST SENSOR READING
# ============================================================

@app.get("/api/readings/latest")
def get_latest_reading():

    try:
        response = (
            database.client
            .table("sensor_readings")
            .select("*")
            .order("recorded_at", desc=True)
            .limit(1)
            .execute()
        )

        if not response.data:
            raise HTTPException(
                status_code=404,
                detail="No sensor readings found."
            )

        return response.data[0]

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch latest reading: {str(e)}"
        )


# ============================================================
# 5. LATEST PREDICTION WITH XAI & CONFIDENCE
# ============================================================

@app.get("/api/prediction/latest")
def get_latest_prediction():

    try:
        response = (
            database.client
            .table("sensor_readings")
            .select("*")
            .order("recorded_at", desc=True)
            .limit(1)
            .execute()
        )

        if not response.data:
            raise HTTPException(
                status_code=404,
                detail="No sensor readings found."
            )

        reading = response.data[0]

        predicted_bod = reading.get("predicted_bod")

        # Warm-up reading: prediction not available yet
        if predicted_bod is None:
            return {
                "ready": False,
                "message": "Model is collecting sensor history.",
                "reading": reading
            }

        # ----------------------------------------------------
        # SHAP explanations
        # ----------------------------------------------------

        shap_values = reading.get("shap_values") or {}
        top_drivers = reading.get("top_shap_drivers") or []

        explanations = []

        for driver in top_drivers:

            feature = driver.get("feature")
            impact = driver.get("impact")

            if feature is None or impact is None:
                continue

            try:
                impact = float(impact)
            except (ValueError, TypeError):
                continue

            feature_info = FEATURE_EXPLANATIONS.get(
                feature,
                {
                    "name": feature.replace("_", " "),
                    "description": (
                        "This model feature contributed to the prediction."
                    )
                }
            )

            if impact > 0:
                direction = "increases"
                interpretation = (
                    "Pushes the predicted BOD higher relative to "
                    "the model's baseline."
                )
            elif impact < 0:
                direction = "decreases"
                interpretation = (
                    "Pushes the predicted BOD lower relative to "
                    "the model's baseline."
                )
            else:
                direction = "neutral"
                interpretation = (
                    "Has negligible influence on this prediction."
                )

            explanations.append({
                "feature": feature,
                "name": feature_info["name"],
                "description": feature_info["description"],
                "impact": impact,
                "direction": direction,
                "interpretation": interpretation
            })

        # ----------------------------------------------------
        # Confidence & uncertainty
        # ----------------------------------------------------

        confidence = reading.get("confidence")
        confidence_tier = reading.get("confidence_tier")
        uncertainty = reading.get("uncertainty")
        prediction_interval = reading.get("prediction_interval")

        # ----------------------------------------------------
        # OOD information
        # ----------------------------------------------------

        mahalanobis_distance = reading.get("mahalanobis_distance")
        ood_factor = reading.get("ood_factor")

        return {
            "ready": True,
            "device_id": reading.get("device_id"),
            "recorded_at": reading.get("recorded_at"),

            "prediction": {
                "predicted_bod": predicted_bod,
                "unit": "mg/L",
                "prediction_interval": prediction_interval,
                "uncertainty": uncertainty
            },

            "confidence": {
                "score": confidence,
                "tier": confidence_tier
            },

            "model_reliability": {
                "mahalanobis_distance": mahalanobis_distance,
                "ood_factor": ood_factor,
                "explanation": (
                    "These metrics describe how unusual the current sensor "
                    "input is relative to the model's training data. "
                    "They should be interpreted alongside confidence and "
                    "the prediction interval."
                )
            },

            "explainability": {
                "shap_values": shap_values,
                "top_drivers": explanations,
                "disclaimer": (
                    "Feature contributions describe how the model arrived "
                    "at its prediction. They do not establish causal "
                    "relationships in the water."
                )
            },

            "sensor_values": {
                "tds_ppm": reading.get("tds_ppm"),
                "turbidity_ntu": reading.get("turbidity_ntu"),
                "temperature_c": reading.get("temperature_c")
            },

            "raw_reading": reading
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch latest prediction: {str(e)}"
        )


# ============================================================
# 6. HISTORICAL SENSOR READINGS
# ============================================================

@app.get("/api/readings/history")
def get_readings_history(
    limit: int = Query(default=50, ge=1, le=500),
    device_id: str = Query(default=None)
):

    try:
        query = (
            database.client
            .table("sensor_readings")
            .select("*")
            .order("recorded_at", desc=True)
            .limit(limit)
        )

        # Optional device filter
        if device_id:
            query = query.eq("device_id", device_id)

        response = query.execute()

        return {
            "count": len(response.data),
            "data": response.data
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch reading history: {str(e)}"
        )


# ============================================================
# 7. STATISTICS ENDPOINT
# ============================================================

@app.get("/api/stats")
def get_statistics(device_id: str = None):

    try:
        # Fetch all readings in batches to avoid API row limits
        all_readings = []
        batch_size = 1000
        start = 0

        while True:

            query = (
                database.client
                .table("sensor_readings")
                .select(
                    "device_id,tds_ppm,turbidity_ntu,temperature_c,"
                    "predicted_bod,recorded_at"
                )
                .order("recorded_at", desc=True)
                .range(start, start + batch_size - 1)
            )

            if device_id:
                query = query.eq("device_id", device_id)

            response = query.execute()
            batch = response.data

            all_readings.extend(batch)

            if len(batch) < batch_size:
                break

            start += batch_size

        if not all_readings:
            raise HTTPException(
                status_code=404,
                detail="No sensor readings found."
            )

        # Latest reading
        latest = all_readings[0]

        # Calculate statistics safely
        def calculate_metrics(column):

            values = [
                float(row[column])
                for row in all_readings
                if row[column] is not None
            ]

            if not values:
                return {
                    "average": None,
                    "minimum": None,
                    "maximum": None
                }

            return {
                "average": round(mean(values), 4),
                "minimum": round(min(values), 4),
                "maximum": round(max(values), 4)
            }

        return {
            "device_id": device_id or "all",
            "total_readings": len(all_readings),
            "predictions_available": sum(
                1 for row in all_readings
                if row["predicted_bod"] is not None
            ),
            "latest": latest,
            "metrics": {
                "tds_ppm": calculate_metrics("tds_ppm"),
                "turbidity_ntu": calculate_metrics("turbidity_ntu"),
                "temperature_c": calculate_metrics("temperature_c"),
                "predicted_bod": calculate_metrics("predicted_bod")
            }
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to calculate statistics: {str(e)}"
        )
