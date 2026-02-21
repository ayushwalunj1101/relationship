import json
from datetime import datetime, timezone
from uuid import UUID

from fastapi import WebSocket


class ConnectionManager:
    """Manages WebSocket connections grouped by user_id."""

    def __init__(self):
        self._connections: dict[UUID, list[WebSocket]] = {}

    async def connect(self, user_id: UUID, websocket: WebSocket):
        await websocket.accept()
        if user_id not in self._connections:
            self._connections[user_id] = []
        self._connections[user_id].append(websocket)

    def disconnect(self, user_id: UUID, websocket: WebSocket):
        if user_id in self._connections:
            self._connections[user_id].remove(websocket)
            if not self._connections[user_id]:
                del self._connections[user_id]

    async def broadcast_to_user(self, user_id: UUID, event_type: str, data: dict):
        """Send an event to all WebSocket connections for a given user."""
        if user_id not in self._connections:
            return

        message = json.dumps(
            {
                "event_type": event_type,
                "data": data,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            default=str,
        )

        stale = []
        for ws in self._connections[user_id]:
            try:
                await ws.send_text(message)
            except Exception:
                stale.append(ws)

        for ws in stale:
            self.disconnect(user_id, ws)


ws_manager = ConnectionManager()
