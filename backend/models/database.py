"""
Database models for AI Water Quality Monitoring System.
Six tables: users, locations, sensor_nodes, sensor_readings, predictions, alerts
"""

from sqlalchemy import (
    Column, Integer, Float, String, Boolean, DateTime, ForeignKey, Text, Enum
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

Base = declarative_base()


class UserRole(str, enum.Enum):
    admin = "admin"
    authority = "authority"
    public = "public"


class RiskLevel(str, enum.Enum):
    good = "Good"
    moderate = "Moderate"
    poor = "Poor"
    critical = "Critical"


class AlertType(str, enum.Enum):
    anomaly = "anomaly"
    threshold = "threshold"
    forecast = "forecast"
    system = "system"


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), default=UserRole.public.value)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)


class Location(Base):
    __tablename__ = "locations"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    water_body_type = Column(String(50), default="river")  # river, lake, pond, tank, supply
    description = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    nodes = relationship("SensorNode", back_populates="location")


class SensorNode(Base):
    __tablename__ = "sensor_nodes"
    id = Column(String(50), primary_key=True)  # e.g. "node-01"
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=True)
    name = Column(String(100), default="")
    status = Column(String(20), default="active")  # active, offline, maintenance
    last_seen = Column(DateTime, default=datetime.utcnow)
    firmware_version = Column(String(20), default="1.0")
    created_at = Column(DateTime, default=datetime.utcnow)

    location = relationship("Location", back_populates="nodes")
    readings = relationship("SensorReading", back_populates="node")
    predictions = relationship("Prediction", back_populates="node")
    alerts = relationship("Alert", back_populates="node")


class SensorReading(Base):
    __tablename__ = "sensor_readings"
    id = Column(Integer, primary_key=True, autoincrement=True)
    node_id = Column(String(50), ForeignKey("sensor_nodes.id"), nullable=False)
    ph = Column(Float, nullable=True)
    turbidity = Column(Float, nullable=True)       # NTU
    dissolved_oxygen = Column(Float, nullable=True) # mg/L
    temperature = Column(Float, nullable=True)      # °C
    tds = Column(Float, nullable=True)              # ppm
    wqi = Column(Float, nullable=True)              # computed Water Quality Index
    risk_level = Column(String(20), nullable=True)
    is_anomaly = Column(Boolean, default=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    node = relationship("SensorNode", back_populates="readings")


class Prediction(Base):
    __tablename__ = "predictions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    node_id = Column(String(50), ForeignKey("sensor_nodes.id"), nullable=False)
    predicted_wqi = Column(Float, nullable=False)
    risk_level = Column(String(20), nullable=False)
    predicted_ph = Column(Float, nullable=True)
    predicted_turbidity = Column(Float, nullable=True)
    predicted_do = Column(Float, nullable=True)
    predicted_temp = Column(Float, nullable=True)
    predicted_tds = Column(Float, nullable=True)
    confidence = Column(Float, nullable=True)
    forecast_time = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    node = relationship("SensorNode", back_populates="predictions")


class Alert(Base):
    __tablename__ = "alerts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    node_id = Column(String(50), ForeignKey("sensor_nodes.id"), nullable=False)
    alert_type = Column(String(20), nullable=False)
    severity = Column(String(20), default="warning")  # info, warning, critical
    message = Column(Text, nullable=False)
    parameter = Column(String(30), nullable=True)  # which parameter triggered it
    value = Column(Float, nullable=True)
    threshold = Column(Float, nullable=True)
    sent_to = Column(Text, default="")
    is_read = Column(Boolean, default=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    node = relationship("SensorNode", back_populates="alerts")
