from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.ws_manager import ws_manager

router = APIRouter(tags=["websocket"])


@router.websocket("/api/solar-system/{user_id}/ws")
async def solar_system_ws(user_id: UUID, websocket: WebSocket):
    """
    WebSocket endpoint for real-time solar system updates.

    Events sent to clients:
    - person_added, person_removed, person_moved, person_tag_changed
    - bulk_update, theme_updated

    Event format: {"event_type": "...", "data": {...}, "timestamp": "..."}
    """
    await ws_manager.connect(user_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(user_id, websocket)
