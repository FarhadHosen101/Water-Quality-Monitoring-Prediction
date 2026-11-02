"""
API routes for sensor readings — the primary data ingestion endpoint.
ESP32 nodes POST readings here; the dashboard GETs them.
"""

from fastapi import APIRouter, Depends, HTTPException, Header, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from datetime import datetime, timedelta
from typing import Optional, List

from backend.database import get_db
from backend.models.database import SensorReading, SensorNode, Alert
from backend.models.schemas import SensorReadingCreate, SensorReadingResponse
from backend.utils.wqi import compute_wqi, check_thresholds, severity_from_wqi
from backend.ml.engine import anomaly_detector

import os
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/readings", tags=["Sensor Readings"])

API_KEY = os.getenv("API_KEY", "CHANGE_ME")


def verify_api_key(x_api_key: Optional[str] = Header(None)):
    """Simple API key verification for ESP32 nodes."""
    expected_key = os.getenv("API_KEY", "CHANGE_ME")
    if expected_key and expected_key != "CHANGE_ME":
        if x_api_key != expected_key:
            raise HTTPException(status_code=401, detail="Invalid API key")
    return True


@router.post("", status_code=201)
def create_reading(reading: SensorReadingCreate, db: Session = Depends(get_db),
                   auth: bool = Depends(verify_api_key)):
    """
    Receive a sensor reading from an ESP32 node.
    Computes WQI, runs anomaly detection, and creates alerts if needed.
    """
    # Auto-register unknown nodes
    node = db.query(SensorNode).filter(SensorNode.id == reading.node_id).first()
    if not node:
        node = SensorNode(id=reading.node_id, name=reading.node_id, status="active")
        db.add(node)
        logger.info(f"Auto-registered new node: {reading.node_id}")

    # Update node last_seen
    node.last_seen = datetime.utcnow()
    node.status = "active"

    # Compute WQI
    wqi_score, risk_level = compute_wqi(
        ph=reading.ph,
        turbidity=reading.turbidity,
        dissolved_oxygen=reading.do,
        temperature=reading.temp,
        tds=reading.tds,
    )

    # Run anomaly detection
    is_anomaly, anomaly_score = anomaly_detector.predict(
        ph=reading.ph,
        turbidity=reading.turbidity,
        dissolved_oxygen=reading.do,
        temperature=reading.temp,
        tds=reading.tds,
    )
    is_anomaly = bool(is_anomaly)

    # Store the reading
    db_reading = SensorReading(
        node_id=reading.node_id,
        ph=reading.ph,
        turbidity=reading.turbidity,
        dissolved_oxygen=reading.do,
        temperature=reading.temp,
        tds=reading.tds,
        wqi=wqi_score,
        risk_level=risk_level,
        is_anomaly=is_anomaly,
    )
    db.add(db_reading)

    # Check thresholds and create alerts
    violations = check_thresholds(
        ph=reading.ph,
        turbidity=reading.turbidity,
        dissolved_oxygen=reading.do,
        temperature=reading.temp,
        tds=reading.tds,
    )

    for param, direction, value, threshold in violations:
        alert = Alert(
            node_id=reading.node_id,
            alert_type="threshold",
            severity="warning" if direction == "high" else "critical",
            message=f"{param} is {'above' if direction == 'high' else 'below'} safe limit: {value:.2f} (threshold: {threshold:.2f})",
            parameter=param,
            value=value,
            threshold=threshold,
        )
        db.add(alert)

    if is_anomaly:
        alert = Alert(
            node_id=reading.node_id,
            alert_type="anomaly",
            severity=severity_from_wqi(wqi_score),
            message=f"Anomalous reading detected (score: {anomaly_score}). WQI={wqi_score}, Risk={risk_level}",
            parameter="multiple",
            value=wqi_score,
        )
        db.add(alert)

    db.commit()
    db.refresh(db_reading)

    return {
        "id": db_reading.id,
        "wqi": wqi_score,
        "risk_level": risk_level,
        "is_anomaly": is_anomaly,
        "anomaly_score": anomaly_score,
        "alerts": len(violations) + (1 if is_anomaly else 0),
    }


@router.get("", response_model=List[SensorReadingResponse])
def get_readings(
    node_id: Optional[str] = None,
    hours: int = Query(24, ge=1, le=720),
    limit: int = Query(500, ge=1, le=5000),
    anomalies_only: bool = False,
    db: Session = Depends(get_db),
):
    """Get sensor readings with optional filters."""
    query = db.query(SensorReading)

    if node_id:
        query = query.filter(SensorReading.node_id == node_id)

    since = datetime.utcnow() - timedelta(hours=hours)
    query = query.filter(SensorReading.timestamp >= since)

    if anomalies_only:
        query = query.filter(SensorReading.is_anomaly == True)

    readings = query.order_by(desc(SensorReading.timestamp)).limit(limit).all()
    return readings


@router.get("/latest")
def get_latest_readings(db: Session = Depends(get_db)):
    """Get the most recent reading for each node."""
    subq = (
        db.query(
            SensorReading.node_id,
            func.max(SensorReading.id).label("max_id")
        )
        .group_by(SensorReading.node_id)
        .subquery()
    )

    readings = (
        db.query(SensorReading)
        .join(subq, SensorReading.id == subq.c.max_id)
        .all()
    )

    results = []
    for r in readings:
        results.append({
            "node_id": r.node_id,
            "ph": r.ph,
            "turbidity": r.turbidity,
            "dissolved_oxygen": r.dissolved_oxygen,
            "temperature": r.temperature,
            "tds": r.tds,
            "wqi": r.wqi,
            "risk_level": r.risk_level,
            "is_anomaly": r.is_anomaly,
            "timestamp": r.timestamp.isoformat() if r.timestamp else None,
        })

    return results


@router.get("/stats")
def get_reading_stats(node_id: Optional[str] = None, hours: int = 24,
                      db: Session = Depends(get_db)):
    """Get aggregated statistics for readings."""
    since = datetime.utcnow() - timedelta(hours=hours)
    query = db.query(SensorReading).filter(SensorReading.timestamp >= since)

    if node_id:
        query = query.filter(SensorReading.node_id == node_id)

    readings = query.all()

    if not readings:
        return {"count": 0, "averages": {}, "min": {}, "max": {}}

    import numpy as np
    params = ["ph", "turbidity", "dissolved_oxygen", "temperature", "tds", "wqi"]
    stats = {"count": len(readings), "averages": {}, "min": {}, "max": {}}

    for param in params:
        values = [getattr(r, param) for r in readings if getattr(r, param) is not None]
        if values:
            stats["averages"][param] = round(np.mean(values), 2)
            stats["min"][param] = round(min(values), 2)
            stats["max"][param] = round(max(values), 2)

    return stats
