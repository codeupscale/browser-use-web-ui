from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException
from pydantic import BaseModel
from src.webui.components import browser_use_agent_tab
from src.webui.components.browser_use_agent_tab import run_agent_task
from fastapi.staticfiles import StaticFiles
from .schemas import AgentRequest
from ..Users.current_user import get_current_user
from ..Users.models import UserModel
from ..db.db_connection import get_db
from ..Users.services import find_user_by_email  
from datetime import datetime, timezone
from .models import AgentModel
from src.websocket.websocket_manager import WebSocketManager

# Get the WebSocket manager from the main app
manager = None

def set_websocket_manager(ws_manager):
    global manager
    manager = ws_manager

async def run_agent_work(query,url, user):
    try:
        db= get_db()
        
        user = find_user_by_email(user["sub"])
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        agent = AgentModel(
            query=query,
            url=url,
            result={"final_result": "PENDING",
                        "steps": [
                        {
                            "step": "PENDING",
                            "step_no": 0,
                            "action": [
                            {
                                "action": {
                                
                                }
                            }
                            ],
                            "created_at": "2025-08-07T12:00:00Z",
                            "updated_at": "2025-08-07T12:00:00Z"
                        }
                        ]
                    },
        # Simulate run,
            user_id=str(user["_id"]),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        # Here you would typically save the agent to the database
        try:
            i_id = db["agent_tasks"].insert_one(agent.model_dump())
            
        except Exception as e:
            print(f"❌ DB Insertion  error: {e}")
            raise HTTPException(status_code=500, detail=str(e))
        

        async def message_callback(message: str):
            if manager:
                await manager.send_message(message)

        result = await run_agent_task(query,url, message_callback=message_callback)
        print(result)  
        # Simulate running the agent task
       # db["agent_tasks"].update_one({"_id": i_id.inserted_id}, {"$set": {"result": result , "updated_at": datetime.now(timezone.utc)}})

        return result
    except Exception as e:
        print(f"❌ Agent error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def stop_agent_work():
    try:
        print("Stopping agent work")
    except Exception as e:
        print(f"❌ Stop agent error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    

# WebSocket endpoint removed - now handled in main.py

