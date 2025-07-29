from fastapi import FastAPI
from pydantic import BaseModel
from src.webui.components import browser_use_agent_tab
from src.webui.components.browser_use_agent_tab import run_agent_task
from fastapi import HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os


app = FastAPI()


# Mount the static files
app.mount("/static", StaticFiles(directory=os.getcwd()), name="static")

# Set display environment for Docker
if not os.getenv("DISPLAY"):
    os.environ["DISPLAY"] = ":99"



class AgentRequest(BaseModel):
    query: str
    url: str

@app.post("/run-agent")
async def run_agent(request: AgentRequest):
    try:
        print(f"🔄 Starting agent with DISPLAY={os.getenv('DISPLAY')}")
        result = await run_agent_task(request.query, request.url)
        
        return {
            "status": "success",
            "task_id": result["task_id"],
            "final_result": result["final_result"]
        }
    except Exception as e:
        print(f"❌ Agent error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/stop-agent")
def stop_agent():
    # call stop_wrapper or shutdown browser/session
    return {"status": "stopped"}

# Serve index.html at /
@app.get("/")
async def serve_frontend():
    return FileResponse("static/index.html")



