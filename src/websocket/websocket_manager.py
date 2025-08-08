from fastapi import WebSocket, logger
from typing import List
import asyncio

class WebSocketManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"✅ WebSocket connected. Total clients: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            print(f"⚠️ WebSocket disconnected. Total clients: {len(self.active_connections)}")

    async def send_message(self, message: str):
        print(f"📤 Sending message to {len(self.active_connections)} clients: {message}")
        if not self.active_connections:
            print("⚠️ No active WebSocket connections")
            return
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                print(f"❌ Error sending message: {e}")

# Helper function
import inspect

def send_ws_message(message_callback, message: str):
    """Send WebSocket message safely, handling both async and sync callbacks."""
    print(f"📤 Sending WebSocket message: {message}")
    if message_callback:
        if inspect.iscoroutinefunction(message_callback):
            try:
                asyncio.create_task(message_callback(message)) 
            except Exception as e:
                logger.error(f"Error sending async message: {e}")
        else:
            try:
                message_callback(message)  # Call sync
            except Exception as e:
                logger.error(f"Error sending sync message: {e}")