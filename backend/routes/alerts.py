"""
API routes for Alerts and Notifications.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from datetime import datetime, timedelta
from typing import List, Optional
import io
import csv

from backend.database import get_db
from backend.models.database import Alert, SensorReading
from backend.models.schemas import AlertResponse

router = APIRouter(prefix="/api/alerts", tags=["Alerts"])


@router.get("", response_model=List[AlertResponse])
def get_alerts(
    node_id: Optional[str] = None,
    severity: Optional[str] = None,
    unread_only: bool = False,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """Retrieve system alerts with optional filters."""
    query = db.query(Alert)

    if node_id:
        query = query.filter(Alert.node_id == node_id)
    if severity:
        query = query.filter(Alert.severity == severity)
    if unread_only:
        query = query.filter(Alert.is_read == False)

    return query.order_by(desc(Alert.timestamp)).limit(limit).all()


@router.put("/{alert_id}/read")
def mark_alert_read(alert_id: int, db: Session = Depends(get_db)):
    """Mark an alert as acknowledged / read."""
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.is_read = True
    db.commit()
    return {"message": "Alert marked as read", "alert_id": alert_id}


@router.put("/mark-all-read")
def mark_all_alerts_read(db: Session = Depends(get_db)):
    """Mark all active alerts as read."""
    count = db.query(Alert).filter(Alert.is_read == False).update({Alert.is_read: True})
    db.commit()
    return {"message": f"Marked {count} alerts as read"}


@router.get("/summary")
def get_alerts_summary(db: Session = Depends(get_db)):
    """Get alert counts grouped by severity and read status."""
    total = db.query(Alert).count()
    unread = db.query(Alert).filter(Alert.is_read == False).count()
    critical = db.query(Alert).filter(Alert.severity == "critical").count()
    warning = db.query(Alert).filter(Alert.severity == "warning").count()
    info = db.query(Alert).filter(Alert.severity == "info").count()

    return {
        "total": total,
        "unread": unread,
        "critical": critical,
        "warning": warning,
        "info": info
    }


@router.get("/export/csv")
def export_readings_csv(node_id: Optional[str] = None, days: int = 7,
                        db: Session = Depends(get_db)):
    """Export historical sensor readings as downloadable CSV file."""
    since = datetime.utcnow() - timedelta(days=days)
    query = db.query(SensorReading).filter(SensorReading.timestamp >= since)
    if node_id:
        query = query.filter(SensorReading.node_id == node_id)

    readings = query.order_by(SensorReading.timestamp.asc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID", "Timestamp (UTC)", "Node ID", "pH", "Turbidity (NTU)",
        "Dissolved Oxygen (mg/L)", "Temperature (°C)", "TDS (ppm)",
        "WQI Score", "Risk Level", "Is Anomaly"
    ])

    for r in readings:
        writer.writerow([
            r.id,
            r.timestamp.strftime("%Y-%m-%d %H:%M:%S") if r.timestamp else "",
            r.node_id,
            r.ph,
            r.turbidity,
            r.dissolved_oxygen,
            r.temperature,
            r.tds,
            r.wqi,
            r.risk_level,
            "YES" if r.is_anomaly else "NO"
        ])

    output.seek(0)
    filename = f"water_quality_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
