from fastapi import APIRouter
from .schemas import AgentRequest
from .services import run_agent_work

router = APIRouter()

@router.post("/run-agent")
async def run_agent(request: AgentRequest):    
    return await run_agent_work(request.query, request.url, {"sub": "ahmad.ejaz@codeupscale.com"})
        