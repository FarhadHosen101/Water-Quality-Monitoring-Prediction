"""
Pydantic schemas for API request/response validation.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# ── Sensor Readings ──────────────────────────────────────────────
class SensorReadingCreate(BaseModel):
    node_id: str
    ph: Optional[float] = None
    turbidity: Optional[float] = None
    do: Optional[float] = Field(None, alias="do")  # dissolved oxygen
    temp: Optional[float] = None
    tds: Optional[float] = None

    class Config:
        populate_by_name = True


class SensorReadingResponse(BaseModel):
    id: int
    node_id: str
    ph: Optional[float]
    turbidity: Optional[float]
    dissolved_oxygen: Optional[float]
    temperature: Optional[float]
    tds: Optional[float]
    wqi: Optional[float]
    risk_level: Optional[str]
    is_anomaly: bool
    timestamp: datetime

    class Config:
        from_attributes = True


# ── Location ─────────────────────────────────────────────────────
class LocationCreate(BaseModel):
    name: str
    latitude: float
    longitude: float
    water_body_type: str = "river"
    description: str = ""


class LocationResponse(BaseModel):
    id: int
    name: str
    latitude: float
    longitude: float
    water_body_type: str
    description: str
    created_at: datetime

    class Config:
        from_attributes = True


# ── Sensor Node ──────────────────────────────────────────────────
class SensorNodeCreate(BaseModel):
    id: str
    location_id: Optional[int] = None
    name: str = ""


class SensorNodeResponse(BaseModel):
    id: str
    location_id: Optional[int]
    name: str
    status: str
    last_seen: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


# ── Predictions ──────────────────────────────────────────────────
class PredictionResponse(BaseModel):
    id: int
    node_id: str
    predicted_wqi: float
    risk_level: str
    predicted_ph: Optional[float]
    predicted_turbidity: Optional[float]
    predicted_do: Optional[float]
    predicted_temp: Optional[float]
    predicted_tds: Optional[float]
    confidence: Optional[float]
    forecast_time: datetime
    created_at: datetime

    class Config:
        from_attributes = True


# ── Alerts ───────────────────────────────────────────────────────
class AlertResponse(BaseModel):
    id: int
    node_id: str
    alert_type: str
    severity: str
    message: str
    parameter: Optional[str]
    value: Optional[float]
    threshold: Optional[float]
    is_read: bool
    timestamp: datetime

    class Config:
        from_attributes = True


# ── Dashboard Summary ────────────────────────────────────────────
class DashboardStats(BaseModel):
    total_nodes: int
    active_nodes: int
    total_readings: int
    readings_today: int
    avg_wqi: Optional[float]
    anomalies_today: int
    unread_alerts: int
    risk_distribution: dict


class NodeSummary(BaseModel):
    node_id: str
    node_name: str
    location_name: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    status: str
    latest_wqi: Optional[float]
    latest_risk: Optional[str]
    last_seen: Optional[datetime]
    is_anomaly: bool
