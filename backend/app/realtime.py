from collections import defaultdict
from fastapi import WebSocket

class AvailabilityHub:
    def __init__(self):
        self.connections: dict[int, set[WebSocket]] = defaultdict(set)

    async def connect(self, event_id: int, websocket: WebSocket):
        await websocket.accept()
        self.connections[event_id].add(websocket)

    def disconnect(self, event_id: int, websocket: WebSocket):
        self.connections[event_id].discard(websocket)

    async def broadcast(self, event_id: int, available_tickets: int):
        dead = []
        payload = {"event_id": event_id, "available_tickets": available_tickets}
        for ws in list(self.connections[event_id]):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(event_id, ws)

hub = AvailabilityHub()
