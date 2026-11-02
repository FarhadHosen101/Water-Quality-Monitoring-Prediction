"""
Background Auto-Simulator Service for AquaAI.
Simulates live streaming telemetry from IoT sensor nodes without requiring external scripts.
Broadcasts newly generated readings directly over WebSockets in real time.
"""

import asyncio
import random
import math
import logging
from datetime import datetime
from typing import Dict, Any

from backend.database import SessionLocal
from backend.models.database import SensorReading, SensorNode, Alert
from backend.models.schemas import SensorReadingCreate
from backend.utils.wqi import compute_wqi, check_thresholds, severity_from_wqi
from backend.ml.engine import anomaly_detector
from backend.websocket import ws_manager

logger = logging.getLogger("simulator_service")

STATIONS = [
    {"id": "node-01", "name": "Buriganga River", "base": {"ph": 6.8, "turb": 38.0, "do": 3.2, "temp": 28.5, "tds": 720.0}},
    {"id": "node-02", "name": "Turag River",     "base": {"ph": 7.1, "turb": 24.0, "do": 4.8, "temp": 27.8, "tds": 490.0}},
    {"id": "node-03", "name": "Dhanmondi Lake",  "base": {"ph": 7.5, "turb": 8.5,  "do": 6.9, "temp": 26.2, "tds": 240.0}},
    {"id": "node-04", "name": "Gulshan Lake",    "base": {"ph": 7.3, "turb": 14.0, "do": 5.5, "temp": 26.8, "tds": 360.0}},
    {"id": "node-05", "name": "Shitalakshya",   "base": {"ph": 6.4, "turb": 42.0, "do": 2.9, "temp": 29.1, "tds": 840.0}},
]


class SimulatorService:
    def __init__(self):
        self.is_running: bool = False
        self.interval: float = 3.5  # seconds between ticks
        self.anomaly_rate: float = 0.08  # 8% chance of synthetic anomaly
        self._task: asyncio.Task = None
        self._step: int = 0

    def get_status(self) -> Dict[str, Any]:
        return {
            "is_running": self.is_running,
            "interval": self.interval,
            "anomaly_rate": self.anomaly_rate,
            "active_stations": len(STATIONS)
        }

    async def start(self, interval: float = 3.5, anomaly_rate: float = 0.08):
        if self.is_running:
            return {"status": "already_running", "message": "Simulation is already streaming."}

        self.interval = max(1.0, float(interval))
        self.anomaly_rate = float(anomaly_rate)
        self.is_running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"Auto-Simulator started with interval {self.interval}s")

        await ws_manager.broadcast({
            "type": "simulator_status",
            "data": self.get_status()
        })
        return {"status": "started", "message": f"Simulation streaming every {self.interval}s."}

    async def stop(self):
        if not self.is_running:
            return {"status": "not_running", "message": "Simulation is not currently running."}

        self.is_running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        logger.info("Auto-Simulator stopped.")

        await ws_manager.broadcast({
            "type": "simulator_status",
            "data": self.get_status()
        })
        return {"status": "stopped", "message": "Simulation paused."}

    async def toggle(self) -> Dict[str, Any]:
        if self.is_running:
            return await self.stop()
        else:
            return await self.start()

    async def generate_single_tick(self) -> Dict[str, Any]:
        """Generate one immediate round of telemetry for all stations (serverless friendly)."""
        self._step += 1
        hour = (datetime.utcnow().hour + self._step / 10.0) % 24
        temp_cycle = math.sin((hour - 8) * math.pi / 12) * 2.5
        do_cycle = math.sin((hour - 10) * math.pi / 12) * 1.0

        for node_info in STATIONS:
            base = node_info["base"]
            ph = round(base["ph"] + random.uniform(-0.15, 0.15), 2)
            turb = round(max(1.0, base["turb"] + random.uniform(-2.5, 2.5)), 1)
            do_val = round(max(0.5, base["do"] + do_cycle + random.uniform(-0.25, 0.25)), 2)
            temp = round(base["temp"] + temp_cycle + random.uniform(-0.35, 0.35), 1)
            tds = round(max(50.0, base["tds"] + random.uniform(-18.0, 18.0)), 0)

            await self._ingest_and_broadcast(
                node_id=node_info["id"],
                ph=ph,
                turbidity=turb,
                do_val=do_val,
                temp=temp,
                tds=tds
            )
        return {"status": "success", "stations_updated": len(STATIONS)}

    async def _run_loop(self):
        """Continuous simulation loop."""
        try:
            while self.is_running:
                self._step += 1
                hour = (datetime.utcnow().hour + self._step / 10.0) % 24
                temp_cycle = math.sin((hour - 8) * math.pi / 12) * 2.5
                do_cycle = math.sin((hour - 10) * math.pi / 12) * 1.0

                # In each tick, generate telemetry for one or all nodes in round-robin
                for node_info in STATIONS:
                    base = node_info["base"]
                    ph = round(base["ph"] + random.uniform(-0.15, 0.15), 2)
                    turb = round(max(1.0, base["turb"] + random.uniform(-2.5, 2.5)), 1)
                    do_val = round(max(0.5, base["do"] + do_cycle + random.uniform(-0.25, 0.25)), 2)
                    temp = round(base["temp"] + temp_cycle + random.uniform(-0.35, 0.35), 1)
                    tds = round(max(50.0, base["tds"] + random.uniform(-18.0, 18.0)), 0)

                    # Trigger occasional realistic anomaly
                    injected_anomaly = False
                    if random.random() < self.anomaly_rate:
                        injected_anomaly = True
                        event = random.choice(["acid", "sludge", "chemical"])
                        if event == "acid":
                            ph = round(random.uniform(4.0, 5.2), 2)
                            turb = round(turb * 1.6, 1)
                        elif event == "sludge":
                            turb = round(random.uniform(130.0, 240.0), 1)
                            do_val = round(random.uniform(0.8, 1.8), 2)
                            tds = round(tds * 1.8, 0)
                        elif event == "chemical":
                            tds = round(random.uniform(1200.0, 1600.0), 0)
                            ph = round(random.uniform(9.2, 10.1), 2)

                    # Ingest and broadcast reading
                    await self._ingest_and_broadcast(
                        node_id=node_info["id"],
                        ph=ph,
                        turbidity=turb,
                        do_val=do_val,
                        temp=temp,
                        tds=tds
                    )
                    # Brief stagger between stations in the same tick
                    await asyncio.sleep(0.4)

                await asyncio.sleep(self.interval)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in simulator loop: {e}", exc_info=True)
            self.is_running = False

    async def _ingest_and_broadcast(self, node_id: str, ph: float, turbidity: float,
                                    do_val: float, temp: float, tds: float):
        """Save to DB, compute WQI, detect anomaly, and broadcast via WebSockets."""
        db = SessionLocal()
        try:
            node = db.query(SensorNode).filter(SensorNode.id == node_id).first()
            if not node:
                node = SensorNode(id=node_id, name=node_id, status="active")
                db.add(node)

            node.last_seen = datetime.utcnow()
            node.status = "active"

            wqi_score, risk_level = compute_wqi(
                ph=ph,
                turbidity=turbidity,
                dissolved_oxygen=do_val,
                temperature=temp,
                tds=tds,
            )

            is_anomaly, anomaly_score = anomaly_detector.predict(
                ph=ph,
                turbidity=turbidity,
                dissolved_oxygen=do_val,
                temperature=temp,
                tds=tds,
            )
            is_anomaly = bool(is_anomaly)

            db_reading = SensorReading(
                node_id=node_id,
                ph=ph,
                turbidity=turbidity,
                dissolved_oxygen=do_val,
                temperature=temp,
                tds=tds,
                wqi=wqi_score,
                risk_level=risk_level,
                is_anomaly=is_anomaly,
                timestamp=datetime.utcnow()
            )
            db.add(db_reading)

            violations = check_thresholds(
                ph=ph,
                turbidity=turbidity,
                dissolved_oxygen=do_val,
                temperature=temp,
                tds=tds,
            )

            new_alerts = []
            for param, direction, val, threshold in violations:
                alert = Alert(
                    node_id=node_id,
                    alert_type="threshold",
                    severity="warning" if direction == "high" else "critical",
                    message=f"{param} is {'above' if direction == 'high' else 'below'} safe limit: {val:.2f} (threshold: {threshold:.2f})",
                    parameter=param,
                    value=val,
                    threshold=threshold,
                )
                db.add(alert)
                new_alerts.append(alert)

            if is_anomaly:
                alert = Alert(
                    node_id=node_id,
                    alert_type="anomaly",
                    severity=severity_from_wqi(wqi_score),
                    message=f"Anomalous reading detected (score: {anomaly_score}). WQI={wqi_score}, Risk={risk_level}",
                    parameter="multiple",
                    value=wqi_score,
                )
                db.add(alert)
                new_alerts.append(alert)

            db.commit()
            db.refresh(db_reading)

            # Broadcast reading over WebSocket
            reading_payload = {
                "id": db_reading.id,
                "node_id": node_id,
                "ph": ph,
                "turbidity": turbidity,
                "dissolved_oxygen": do_val,
                "temperature": temp,
                "tds": tds,
                "wqi": wqi_score,
                "risk_level": risk_level,
                "is_anomaly": is_anomaly,
                "anomaly_score": anomaly_score,
                "timestamp": db_reading.timestamp.isoformat(),
            }

            await ws_manager.broadcast({
                "type": "new_reading",
                "data": reading_payload
            })

            # Broadcast alerts if any
            for a in new_alerts:
                await ws_manager.broadcast({
                    "type": "new_alert",
                    "data": {
                        "id": a.id,
                        "node_id": a.node_id,
                        "alert_type": a.alert_type,
                        "severity": a.severity,
                        "message": a.message,
                        "parameter": a.parameter,
                        "value": a.value,
                        "timestamp": a.timestamp.isoformat()
                    }
                })

        except Exception as e:
            logger.error(f"Error ingesting reading in simulator: {e}", exc_info=True)
            db.rollback()
        finally:
            db.close()


simulator_service = SimulatorService()
