"""
AI-Based Water Quality Monitoring & Pollution Prediction System.
Main FastAPI application entry point.
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import logging

from backend.database import engine
from backend.models.database import Base
from backend.routes import readings, nodes, predictions, alerts, dashboard
from backend.utils.seed_data import seed_database_if_empty

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("water_quality_api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup & shutdown events."""
    logger.info("Initializing database and models...")
    Base.metadata.create_all(bind=engine)
    # Seed sample stations & historical data if database is empty
    seed_database_if_empty()
    logger.info("Water Quality Monitoring System ready!")
    yield
    logger.info("Shutting down Water Quality Monitoring System...")


app = FastAPI(
    title="AI Water Quality Monitoring & Pollution Prediction API",
    description="IoT telemetry, Anomaly Detection (Isolation Forest), WQI computation, and Predictive Forecasting (Random Forest)",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for all local and remote web clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(readings.router)
app.include_router(nodes.router)
app.include_router(predictions.router)
app.include_router(alerts.router)
app.include_router(dashboard.router)


# ── Quick simulation endpoints for interactive UI testing ─────────
@app.post("/api/simulate/anomaly/{node_id}")
def simulate_anomaly_event(node_id: str, anomaly_type: str = "acid"):
    """Trigger a simulated anomaly for real-time demonstration from UI."""
    from backend.database import SessionLocal
    from backend.routes.readings import create_reading
    from backend.models.schemas import SensorReadingCreate

    presets = {
        "acid": {"ph": 4.1, "turbidity": 48.0, "do": 3.8, "temp": 28.0, "tds": 790.0},
        "sludge": {"ph": 7.4, "turbidity": 185.0, "do": 1.5, "temp": 31.0, "tds": 1420.0},
        "chemical": {"ph": 9.6, "turbidity": 62.0, "do": 2.2, "temp": 29.5, "tds": 1680.0},
        "normal": {"ph": 7.4, "turbidity": 6.5, "do": 7.2, "temp": 26.0, "tds": 190.0},
    }
    preset = presets.get(anomaly_type, presets["acid"])

    db = SessionLocal()
    try:
        reading_payload = SensorReadingCreate(
            node_id=node_id,
            ph=preset["ph"],
            turbidity=preset["turbidity"],
            do=preset["do"],
            temp=preset["temp"],
            tds=preset["tds"]
        )
        result = create_reading(reading=reading_payload, db=db, auth=True)
        return {
            "status": "success",
            "message": f"Injected simulated {anomaly_type} event into {node_id}",
            "result": result
        }
    finally:
        db.close()


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "AI Water Quality Platform"}


# ── Mount Frontend Static Files ───────────────────────────────────
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/")
    def serve_frontend_index():
        index_path = os.path.join(FRONTEND_DIR, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        return {"message": "Frontend index.html not yet built."}
