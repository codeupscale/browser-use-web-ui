from pydantic import BaseModel, Field

class AgentRequest(BaseModel):
    query: str = Field(..., description="The query to run the agent on")
    url: str = Field(..., description="The URL to run the agent on")