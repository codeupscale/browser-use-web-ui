from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from src.webui.components import browser_use_agent_tab
from src.webui.components.browser_use_agent_tab import run_agent_task
from fastapi import HTTPException
from fastapi.staticfiles import StaticFiles
from .schemas import AgentRequest
from ..Users.current_user import get_current_user
from .services import run_agent_work, stop_agent_work

router = APIRouter()

@router.post("/run-agent")
async def run_agent(request: AgentRequest ):
    try:
        # user = current_user
        
        result = await run_agent_work(request.query, request.url, {"sub": "ahmad.ejaz@codeupscale.com"})
        
        return {
            "status": "success",
            
            "final_result": result["final_result"]
        }
    except Exception as e:
        print(f"❌ Agent error: {e}")
        raise HTTPException(status_code=500, detail=str (e))
    
@router.post("/stop-agent")
async def stop_agent():
    try:
        await stop_agent_work()
        return {"status": "success"}
    except Exception as e:
        print(f"❌ Stop agent error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
