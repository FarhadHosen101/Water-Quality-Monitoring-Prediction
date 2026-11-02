"""
WebSocket Connection Manager and real-time broadcasting for AquaAI.
"""

from fastapi import WebSocket, WebSocketDisconnect
from typing import List, Dict, Any
import logging
import asyncio
import json

logger = logging.getLogger("water_quality_ws")


class ConnectionManager:
    """Manages active WebSocket connections from dashboard clients."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket client connected. Total clients: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket client disconnected. Total clients: {len(self.active_connections)}")

    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast JSON message to all connected clients."""
        if not self.active_connections:
            return

        dead_connections = []
        payload = json.dumps(message)

        for connection in self.active_connections:
            try:
                await connection.send_text(payload)
            except Exception as e:
                logger.warning(f"Failed to send to client: {e}")
                dead_connections.append(connection)

        for dead in dead_connections:
            if dead in self.active_connections:
                self.active_connections.remove(dead)

    def broadcast_sync(self, message: Dict[str, Any]):
        """Helper to broadcast from synchronous route handlers."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.broadcast(message))
        except RuntimeError:
            # Fallback if outside event loop
            try:
                asyncio.run(self.broadcast(message))
            except Exception as e:
                logger.error(f"Sync broadcast failed: {e}")


ws_manager = ConnectionManager()
