from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path
import os

from src.webui.components.browser_use_agent_tab import run_agent_task
from src.websocket.websocket_manager import WebSocketManager

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
manager = WebSocketManager()

# Mount static files
app.mount("/static", StaticFiles(directory=os.getcwd()), name="static")

# Set display environment for Docker (headless)
if not os.getenv("DISPLAY"):
    os.environ["DISPLAY"] = ":99"


# 🧠 Request body model
class AgentRequest(BaseModel):
    query: str
    url: str


# 🎯 Run agent task and send logs via WebSocket
@app.post("/run-agent")

async def run_agent(request: AgentRequest):
    try:
        print(f"🔄 Starting agent with DISPLAY={os.getenv('DISPLAY')}")

        async def message_callback(message: str):
            await manager.send_message(message)

        result = await run_agent_task(request.query, request.url, message_callback=message_callback)

        return {
            "status": "success",
            "task_id": result["task_id"],
            "final_result": result["final_result"]
        }
    except Exception as e:
        print(f"❌ Agent error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ⛔ Optional Stop Agent
@app.post("/stop-agent")
def stop_agent():
    return {"status": "stopped"}


# 🌐 Serve frontend
@app.get("/")
async def serve_frontend():
    return FileResponse("static/index.html")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # keep alive
    except:
        manager.disconnect(websocket)
