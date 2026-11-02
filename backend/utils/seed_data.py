"""
Database seeder: generates realistic water monitoring stations and historical data.
Trains baseline ML models on initial setup so the AI system works out-of-the-box.
"""

import math
import random
from datetime import datetime, timedelta
import pandas as pd
import logging

from backend.database import SessionLocal, engine
from backend.models.database import Base, User, Location, SensorNode, SensorReading, Alert, Prediction
from backend.utils.wqi import compute_wqi, check_thresholds
from backend.ml.engine import anomaly_detector, pollution_forecaster

logger = logging.getLogger(__name__)


MONITORING_LOCATIONS = [
    {
        "name": "Buriganga River - Sadarghat Station",
        "latitude": 23.7045,
        "longitude": 90.4125,
        "water_body_type": "river",
        "description": "High industrial & ferry traffic zone; critical monitoring zone.",
        "node_id": "node-01",
        "node_name": "Node Alpha (Buriganga)",
        "base": {"ph": 6.8, "turb": 38.0, "do": 3.2, "temp": 28.5, "tds": 720.0}
    },
    {
        "name": "Turag River - Gabtoli Point",
        "latitude": 23.7845,
        "longitude": 90.3440,
        "water_body_type": "river",
        "description": "Upstream commercial runoff with sand dredging activity.",
        "node_id": "node-02",
        "node_name": "Node Beta (Turag)",
        "base": {"ph": 7.1, "turb": 24.0, "do": 4.8, "temp": 27.8, "tds": 490.0}
    },
    {
        "name": "Dhanmondi Lake - South Bank",
        "latitude": 23.7460,
        "longitude": 90.3760,
        "water_body_type": "lake",
        "description": "Urban recreational lake, vulnerable to seasonal algae blooms.",
        "node_id": "node-03",
        "node_name": "Node Gamma (Dhanmondi)",
        "base": {"ph": 7.5, "turb": 8.5, "do": 6.9, "temp": 26.2, "tds": 240.0}
    },
    {
        "name": "Gulshan-Baridhara Lake - North Bridge",
        "latitude": 23.7925,
        "longitude": 90.4160,
        "water_body_type": "lake",
        "description": "Residential stormwater retention and municipal discharge point.",
        "node_id": "node-04",
        "node_name": "Node Delta (Gulshan)",
        "base": {"ph": 7.3, "turb": 14.0, "do": 5.5, "temp": 26.8, "tds": 360.0}
    },
    {
        "name": "Shitalakshya River - Demra Ghat",
        "latitude": 23.7120,
        "longitude": 90.4980,
        "water_body_type": "river",
        "description": "Industrial zone with dye factories and riverine transport.",
        "node_id": "node-05",
        "node_name": "Node Epsilon (Shitalakshya)",
        "base": {"ph": 6.4, "turb": 42.0, "do": 2.9, "temp": 29.1, "tds": 840.0}
    }
]


def seed_database_if_empty():
    """Seeds locations, nodes, and 7 days of realistic readings if database is unpopulated."""
    # Ensure tables exist
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        existing_count = db.query(SensorNode).count()
        if existing_count > 0:
            logger.info(f"Database already has {existing_count} nodes. Skipping seed.")
            return

        logger.info("Initializing database with realistic water quality stations and data...")

        # 1. Add Default Admin User
        admin_user = User(
            name="System Admin",
            email="admin@waterquality.org",
            password_hash="admin123",  # For demonstration
            role="admin"
        )
        db.add(admin_user)

        # 2. Add Locations and Nodes
        created_nodes = []
        for loc_data in MONITORING_LOCATIONS:
            loc = Location(
                name=loc_data["name"],
                latitude=loc_data["latitude"],
                longitude=loc_data["longitude"],
                water_body_type=loc_data["water_body_type"],
                description=loc_data["description"]
            )
            db.add(loc)
            db.flush()

            node = SensorNode(
                id=loc_data["node_id"],
                name=loc_data["node_name"],
                location_id=loc.id,
                status="active",
                last_seen=datetime.utcnow()
            )
            db.add(node)
            created_nodes.append((node, loc_data["base"]))

        db.commit()

        # 3. Generate 5 days of simulated historical readings (hourly steps)
        now = datetime.utcnow()
        all_readings = []

        total_hours = 5 * 24  # 120 hourly points per node
        for node, base in created_nodes:
            for step in range(total_hours, -1, -1):
                timestamp = now - timedelta(hours=step)
                hour = timestamp.hour

                # Natural diurnal temperature cycle (cool at dawn, warm at 2 PM)
                temp_cycle = math.sin((hour - 8) * math.pi / 12) * 3.0
                curr_temp = round(base["temp"] + temp_cycle + random.uniform(-0.4, 0.4), 2)

                # Dissolved oxygen usually higher during afternoon photosynthesis
                do_cycle = math.sin((hour - 10) * math.pi / 12) * 1.2
                curr_do = round(max(0.5, base["do"] + do_cycle + random.uniform(-0.3, 0.3)), 2)

                # pH slightly fluctuates
                curr_ph = round(base["ph"] + random.uniform(-0.15, 0.15), 2)

                # Turbidity & TDS
                curr_turb = round(max(1.0, base["turb"] + random.uniform(-3.0, 3.0)), 1)
                curr_tds = round(max(50.0, base["tds"] + random.uniform(-20.0, 20.0)), 1)

                # Inject occasional realistic pollution anomalies (e.g. chemical discharge event)
                is_anomaly_event = False
                if random.random() < 0.04:  # 4% chance of anomaly
                    is_anomaly_event = True
                    anomaly_type = random.choice(["acid_spill", "sludge_dump", "heavy_metals"])
                    if anomaly_type == "acid_spill":
                        curr_ph = round(random.uniform(4.0, 5.2), 2)
                        curr_turb = round(curr_turb * 1.8, 1)
                    elif anomaly_type == "sludge_dump":
                        curr_turb = round(random.uniform(120.0, 260.0), 1)
                        curr_do = round(random.uniform(0.8, 2.0), 2)
                        curr_tds = round(curr_tds * 2.2, 1)
                    elif anomaly_type == "heavy_metals":
                        curr_tds = round(random.uniform(1100.0, 1650.0), 1)

                wqi_score, risk_level = compute_wqi(
                    ph=curr_ph,
                    turbidity=curr_turb,
                    dissolved_oxygen=curr_do,
                    temperature=curr_temp,
                    tds=curr_tds
                )

                reading = SensorReading(
                    node_id=node.id,
                    ph=curr_ph,
                    turbidity=curr_turb,
                    dissolved_oxygen=curr_do,
                    temperature=curr_temp,
                    tds=curr_tds,
                    wqi=wqi_score,
                    risk_level=risk_level,
                    is_anomaly=is_anomaly_event,
                    timestamp=timestamp
                )
                db.add(reading)
                all_readings.append(reading)

                # Create alerts for threshold violations or anomalies in the last 24 hours
                if step <= 24:
                    violations = check_thresholds(
                        ph=curr_ph, turbidity=curr_turb, dissolved_oxygen=curr_do,
                        temperature=curr_temp, tds=curr_tds
                    )
                    for param, direction, val, thresh in violations:
                        db.add(Alert(
                            node_id=node.id,
                            alert_type="threshold",
                            severity="warning" if direction == "high" else "critical",
                            message=f"{param.capitalize()} exceeded safety envelope ({val:.1f} vs limit {thresh})",
                            parameter=param,
                            value=val,
                            threshold=thresh,
                            is_read=random.choice([True, False]),
                            timestamp=timestamp
                        ))
                    if is_anomaly_event:
                        db.add(Alert(
                            node_id=node.id,
                            alert_type="anomaly",
                            severity="critical" if wqi_score > 60 else "warning",
                            message=f"Critical AI anomaly detected at {node.name}! High contamination spike.",
                            parameter="multiple",
                            value=wqi_score,
                            is_read=False,
                            timestamp=timestamp
                        ))

        db.commit()
        logger.info(f"Generated {len(all_readings)} historical sensor readings.")

        # 4. Train the ML models on this rich seeded dataset!
        logger.info("Training initial Isolation Forest and Random Forest models on baseline dataset...")
        df_train = pd.DataFrame([{
            "timestamp": r.timestamp,
            "ph": r.ph,
            "turbidity": r.turbidity,
            "dissolved_oxygen": r.dissolved_oxygen,
            "temperature": r.temperature,
            "tds": r.tds,
            "wqi": r.wqi
        } for r in all_readings])

        anomaly_detector.train(df_train)
        pollution_forecaster.train(df_train)
        logger.info("Baseline ML models successfully trained and persisted!")

    except Exception as e:
        logger.error(f"Error seeding database: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    seed_database_if_empty()
