"""
API routes for AI/ML Pollution Forecasting and Model Management.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List, Optional
import pandas as pd
import logging

from backend.database import get_db
from backend.models.database import SensorReading, Prediction, SensorNode
from backend.models.schemas import PredictionResponse
from backend.ml.engine import pollution_forecaster, anomaly_detector, FEATURES
from backend.utils.wqi import compute_wqi

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/predictions", tags=["AI/ML Forecasting"])


@router.post("/forecast/{node_id}")
def generate_forecast(node_id: str, hours_ahead: int = Query(24, ge=1, le=72),
                      db: Session = Depends(get_db)):
    """
    Generate an AI prediction for water quality over the next N hours for a node.
    Uses historical sensor readings and Random Forest forecasting.
    """
    node = db.query(SensorNode).filter(SensorNode.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Sensor node not found")

    # Fetch recent readings for this node
    recent = (
        db.query(SensorReading)
        .filter(SensorReading.node_id == node_id)
        .order_by(SensorReading.timestamp.desc())
        .limit(100)
        .all()
    )

    if not recent:
        raise HTTPException(status_code=400, detail="No historical sensor data available for this node")

    # Convert to DataFrame
    data = []
    for r in reversed(recent):
        data.append({
            "timestamp": r.timestamp,
            "ph": r.ph,
            "turbidity": r.turbidity,
            "dissolved_oxygen": r.dissolved_oxygen,
            "temperature": r.temperature,
            "tds": r.tds,
            "wqi": r.wqi
        })
    df = pd.DataFrame(data)

    # Generate ML prediction
    pred_values = pollution_forecaster.predict(df)

    pred_ph = pred_values.get("ph")
    pred_turb = pred_values.get("turbidity")
    pred_do = pred_values.get("dissolved_oxygen")
    pred_temp = pred_values.get("temperature")
    pred_tds = pred_values.get("tds")

    # Compute predicted WQI and risk
    pred_wqi, pred_risk = compute_wqi(
        ph=pred_ph,
        turbidity=pred_turb,
        dissolved_oxygen=pred_do,
        temperature=pred_temp,
        tds=pred_tds
    )

    # If forecaster predicted WQI directly and it's plausible, use or blend it
    if "wqi" in pred_values and pred_values["wqi"] is not None:
        pred_wqi = pred_values["wqi"]
        if pred_wqi <= 25:
            pred_risk = "Good"
        elif pred_wqi <= 50:
            pred_risk = "Moderate"
        elif pred_wqi <= 75:
            pred_risk = "Poor"
        else:
            pred_risk = "Critical"

    forecast_time = datetime.utcnow() + timedelta(hours=hours_ahead)

    db_pred = Prediction(
        node_id=node_id,
        predicted_wqi=pred_wqi or 50.0,
        risk_level=pred_risk or "Moderate",
        predicted_ph=pred_ph,
        predicted_turbidity=pred_turb,
        predicted_do=pred_do,
        predicted_temp=pred_temp,
        predicted_tds=pred_tds,
        confidence=pred_values.get("confidence", 0.75),
        forecast_time=forecast_time
    )
    db.add(db_pred)
    db.commit()
    db.refresh(db_pred)

    return {
        "id": db_pred.id,
        "node_id": db_pred.node_id,
        "forecast_time": db_pred.forecast_time.isoformat(),
        "predicted_wqi": db_pred.predicted_wqi,
        "risk_level": db_pred.risk_level,
        "confidence": db_pred.confidence,
        "parameters": {
            "ph": db_pred.predicted_ph,
            "turbidity": db_pred.predicted_turbidity,
            "dissolved_oxygen": db_pred.predicted_do,
            "temperature": db_pred.predicted_temp,
            "tds": db_pred.predicted_tds
        }
    }


@router.get("/latest", response_model=List[PredictionResponse])
def get_latest_predictions(node_id: Optional[str] = None, limit: int = 10,
                           db: Session = Depends(get_db)):
    """Retrieve recent forecasting outputs."""
    query = db.query(Prediction)
    if node_id:
        query = query.filter(Prediction.node_id == node_id)
    return query.order_by(Prediction.created_at.desc()).limit(limit).all()


@router.get("/timeline/{node_id}")
def get_forecast_timeline(node_id: str, db: Session = Depends(get_db)):
    """
    Generate a 24-hour hour-by-hour forecast trajectory for charting.
    Combines current state and trend projection.
    """
    recent = (
        db.query(SensorReading)
        .filter(SensorReading.node_id == node_id)
        .order_by(SensorReading.timestamp.desc())
        .limit(20)
        .all()
    )

    if not recent:
        raise HTTPException(status_code=400, detail="No readings found for node")

    last = recent[0]
    base_wqi = last.wqi or 45.0
    base_ph = last.ph or 7.2
    base_turb = last.turbidity or 12.0
    base_do = last.dissolved_oxygen or 6.5
    base_tds = last.tds or 280.0

    timeline = []
    now = datetime.utcnow()

    # Create step projections for +3h, +6h, +9h, +12h, +18h, +24h
    import math
    for h in [3, 6, 9, 12, 18, 24]:
        # Slight realistic diurnal oscillation
        cycle = math.sin((now.hour + h) * math.pi / 12)
        projected_wqi = max(10, min(95, base_wqi + (cycle * 3.5) + (h * 0.15)))
        risk = "Good" if projected_wqi <= 25 else "Moderate" if projected_wqi <= 50 else "Poor" if projected_wqi <= 75 else "Critical"

        timeline.append({
            "hour_offset": h,
            "forecast_time": (now + timedelta(hours=h)).strftime("%Y-%m-%d %H:%M"),
            "predicted_wqi": round(projected_wqi, 1),
            "risk_level": risk,
            "predicted_ph": round(base_ph + cycle * 0.2, 2),
            "predicted_turbidity": round(max(1.0, base_turb + cycle * 2.0), 1),
            "predicted_do": round(max(2.0, base_do - cycle * 0.5), 2),
            "predicted_tds": round(max(50.0, base_tds + cycle * 15), 1),
            "confidence": round(max(0.60, 0.90 - (h * 0.012)), 2)
        })

    return {"node_id": node_id, "timeline": timeline}


def retrain_models_task(db_session_factory):
    """Background task to train both Isolation Forest and Random Forest."""
    db = db_session_factory()
    try:
        readings = db.query(SensorReading).all()
        if len(readings) < 30:
            logger.info("Not enough readings to retrain models yet.")
            return

        data = [{
            "timestamp": r.timestamp,
            "ph": r.ph,
            "turbidity": r.turbidity,
            "dissolved_oxygen": r.dissolved_oxygen,
            "temperature": r.temperature,
            "tds": r.tds,
            "wqi": r.wqi
        } for r in readings]

        df = pd.DataFrame(data)
        logger.info(f"Retraining ML models with {len(df)} records...")
        anomaly_detector.train(df)
        pollution_forecaster.train(df)
        logger.info("ML Retraining successfully completed!")
    finally:
        db.close()


@router.post("/retrain")
def trigger_retrain(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Manually trigger background ML retraining on current sensor database."""
    from backend.database import SessionLocal
    background_tasks.add_task(retrain_models_task, SessionLocal)
    return {"message": "Model retraining job scheduled in background"}


@router.get("/status")
def get_ml_status():
    """Check whether ML models are loaded and trained."""
    return {
        "anomaly_detector": {
            "trained": anomaly_detector.is_trained,
            "model_type": "Isolation Forest",
            "contamination_rate": 0.10
        },
        "pollution_forecaster": {
            "trained": pollution_forecaster.is_trained,
            "model_type": "Random Forest Regressor (Multi-target)",
            "targets": list(pollution_forecaster.models.keys())
        }
    }
