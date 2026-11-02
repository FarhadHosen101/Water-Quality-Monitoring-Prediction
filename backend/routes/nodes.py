"""
API routes for Sensor Nodes and Locations management.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta

from backend.database import get_db
from backend.models.database import SensorNode, Location, SensorReading
from backend.models.schemas import (
    SensorNodeCreate, SensorNodeResponse,
    LocationCreate, LocationResponse
)

router = APIRouter(prefix="/api/nodes", tags=["Nodes & Locations"])


# ── Location Endpoints ───────────────────────────────────────────
@router.get("/locations", response_model=List[LocationResponse])
def get_locations(db: Session = Depends(get_db)):
    """List all water monitoring locations."""
    return db.query(Location).all()


@router.post("/locations", response_model=LocationResponse, status_code=201)
def create_location(location: LocationCreate, db: Session = Depends(get_db)):
    """Register a new monitoring location (GPS coordinates, body type)."""
    db_loc = Location(
        name=location.name,
        latitude=location.latitude,
        longitude=location.longitude,
        water_body_type=location.water_body_type,
        description=location.description
    )
    db.add(db_loc)
    db.commit()
    db.refresh(db_loc)
    return db_loc


# ── Node Endpoints ───────────────────────────────────────────────
@router.get("")
def get_nodes(db: Session = Depends(get_db)):
    """
    List all sensor nodes with their location information and latest reading/status.
    """
    nodes = db.query(SensorNode).all()
    results = []

    ten_mins_ago = datetime.utcnow() - timedelta(minutes=10)

    for node in nodes:
        latest = (
            db.query(SensorReading)
            .filter(SensorReading.node_id == node.id)
            .order_by(SensorReading.timestamp.desc())
            .first()
        )

        # Node status defaults to active unless explicitly configured otherwise
        current_status = node.status or "active"

        results.append({
            "id": node.id,
            "name": node.name or node.id,
            "status": current_status,
            "last_seen": node.last_seen.isoformat() if node.last_seen else None,
            "location_id": node.location_id,
            "location_name": node.location.name if node.location else "Unassigned",
            "latitude": node.location.latitude if node.location else None,
            "longitude": node.location.longitude if node.location else None,
            "water_body_type": node.location.water_body_type if node.location else "river",
            "latest_wqi": latest.wqi if latest else None,
            "latest_risk": latest.risk_level if latest else None,
            "is_anomaly": latest.is_anomaly if latest else False,
            "latest_reading": {
                "ph": latest.ph,
                "turbidity": latest.turbidity,
                "dissolved_oxygen": latest.dissolved_oxygen,
                "temperature": latest.temperature,
                "tds": latest.tds,
                "timestamp": latest.timestamp.isoformat() if latest and latest.timestamp else None
            } if latest else None
        })

    return results


@router.post("", response_model=SensorNodeResponse, status_code=201)
def create_node(node: SensorNodeCreate, db: Session = Depends(get_db)):
    """Manually register or configure a sensor node."""
    existing = db.query(SensorNode).filter(SensorNode.id == node.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Node ID already exists")

    db_node = SensorNode(
        id=node.id,
        name=node.name or node.id,
        location_id=node.location_id,
        status="active"
    )
    db.add(db_node)
    db.commit()
    db.refresh(db_node)
    return db_node


@router.put("/{node_id}/location")
def assign_node_location(node_id: str, location_id: int, db: Session = Depends(get_db)):
    """Assign or update the physical location of a node."""
    node = db.query(SensorNode).filter(SensorNode.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    loc = db.query(Location).filter(Location.id == location_id).first()
    if not loc:
        raise HTTPException(status_code=404, detail="Location not found")

    node.location_id = location_id
    db.commit()
    return {"message": f"Node {node_id} assigned to {loc.name}"}
