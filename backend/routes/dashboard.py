"""
API routes for Dashboard overview, GIS map markers, and Lab validation comparison.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from typing import Dict, Any

from backend.database import get_db
from backend.models.database import SensorNode, SensorReading, Alert, Location
from backend.utils.wqi import compute_wqi, PARAM_STANDARDS

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/stats")
def get_dashboard_stats(db: Session = Depends(get_db)):
    """Aggregate statistics for the top-level KPI cards."""
    total_nodes = db.query(SensorNode).count()

    # Active stations: count nodes with status == "active", fallback to total_nodes if populated
    active_nodes = (
        db.query(SensorNode)
        .filter(SensorNode.status == "active")
        .count()
    )
    if active_nodes == 0 and total_nodes > 0:
        active_nodes = total_nodes

    total_readings = db.query(SensorReading).count()

    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)

    readings_today = (
        db.query(SensorReading)
        .filter(SensorReading.timestamp >= today_start)
        .count()
    )

    anomalies_today = (
        db.query(SensorReading)
        .filter(
            SensorReading.timestamp >= today_start,
            SensorReading.is_anomaly == True
        )
        .count()
    )
    if anomalies_today == 0:
        # Check last 24 hours or total baseline anomalies
        anomalies_today = (
            db.query(SensorReading)
            .filter(
                SensorReading.timestamp >= twenty_four_hours_ago,
                SensorReading.is_anomaly == True
            )
            .count()
        )
        if anomalies_today == 0:
            anomalies_today = db.query(SensorReading).filter(SensorReading.is_anomaly == True).count()

    unread_alerts = db.query(Alert).filter(Alert.is_read == False).count()

    # Calculate average WQI for today
    avg_wqi_val = (
        db.query(func.avg(SensorReading.wqi))
        .filter(SensorReading.timestamp >= today_start)
        .scalar()
    )
    if avg_wqi_val is None:
        # fallback to overall avg
        avg_wqi_val = db.query(func.avg(SensorReading.wqi)).scalar()

    # Distribution of risk levels across all readings today
    risk_counts = {
        "Good": db.query(SensorReading).filter(SensorReading.timestamp >= today_start, SensorReading.risk_level == "Good").count(),
        "Moderate": db.query(SensorReading).filter(SensorReading.timestamp >= today_start, SensorReading.risk_level == "Moderate").count(),
        "Poor": db.query(SensorReading).filter(SensorReading.timestamp >= today_start, SensorReading.risk_level == "Poor").count(),
        "Critical": db.query(SensorReading).filter(SensorReading.timestamp >= today_start, SensorReading.risk_level == "Critical").count(),
    }

    return {
        "total_nodes": total_nodes,
        "active_nodes": active_nodes,
        "total_readings": total_readings,
        "readings_today": readings_today,
        "avg_wqi": round(avg_wqi_val, 1) if avg_wqi_val else None,
        "anomalies_today": anomalies_today,
        "unread_alerts": unread_alerts,
        "risk_distribution": risk_counts
    }


@router.get("/map-markers")
def get_map_markers(db: Session = Depends(get_db)):
    """
    Return all nodes with GPS coordinates, latest WQI, and risk status for Leaflet map.
    """
    nodes = db.query(SensorNode).all()
    markers = []

    for node in nodes:
        if not node.location:
            continue

        latest = (
            db.query(SensorReading)
            .filter(SensorReading.node_id == node.id)
            .order_by(SensorReading.timestamp.desc())
            .first()
        )

        markers.append({
            "node_id": node.id,
            "name": node.name or node.id,
            "location_name": node.location.name,
            "lat": node.location.latitude,
            "lng": node.location.longitude,
            "water_body_type": node.location.water_body_type,
            "status": node.status,
            "wqi": latest.wqi if latest else None,
            "risk_level": latest.risk_level if latest else "Unknown",
            "is_anomaly": latest.is_anomaly if latest else False,
            "ph": latest.ph if latest else None,
            "turbidity": latest.turbidity if latest else None,
            "do": latest.dissolved_oxygen if latest else None,
            "temp": latest.temperature if latest else None,
            "tds": latest.tds if latest else None,
            "last_seen": node.last_seen.isoformat() if node.last_seen else None
        })

    return markers


@router.get("/lab-benchmark")
def get_lab_benchmark():
    """
    Validation comparison against real water sample types (from project proposal):
      1. Clean Tap Water
      2. Pond Water
      3. Contaminated Water (bucket test)
    """
    samples = [
        {
            "name": "Clean Tap Water (Municipal Supply)",
            "description": "Treated potable municipal tap water",
            "ph": 7.3,
            "turbidity": 1.2,
            "dissolved_oxygen": 7.8,
            "temperature": 24.5,
            "tds": 145.0,
        },
        {
            "name": "Natural Pond Water (Dhanmondi Lake)",
            "description": "Urban recreational water body with organic matter",
            "ph": 7.9,
            "turbidity": 14.5,
            "dissolved_oxygen": 5.4,
            "temperature": 27.2,
            "tds": 380.0,
        },
        {
            "name": "Contaminated Sample (Industrial / Runoff)",
            "description": "Industrial effluent or heavy urban surface runoff",
            "ph": 5.1,
            "turbidity": 85.0,
            "dissolved_oxygen": 1.8,
            "temperature": 31.0,
            "tds": 1150.0,
        }
    ]

    results = []
    for s in samples:
        wqi, risk = compute_wqi(
            ph=s["ph"],
            turbidity=s["turbidity"],
            dissolved_oxygen=s["dissolved_oxygen"],
            temperature=s["temperature"],
            tds=s["tds"]
        )
        results.append({
            **s,
            "wqi": wqi,
            "risk_level": risk,
            "safe_drinking": wqi <= 25,
            "safe_aquatic": wqi <= 50,
        })

    return {
        "standards": PARAM_STANDARDS,
        "samples": results
    }
