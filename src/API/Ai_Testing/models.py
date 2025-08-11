from pydantic import BaseModel, Field
from datetime import datetime, timezone
from typing import Optional


class ActionsModel(BaseModel):
    action: dict = Field(..., description="The action taken by the agent")
    
    
class StepsModel(BaseModel):
    step: str = Field(..., description="The step taken by the agent")
    step_no: int = Field(..., description="The step number in the sequence")
    action: list[ActionsModel] = Field(..., description="The action taken in this step")
    created_at: Optional[datetime] = Field(..., description="Timestamp of when the step was created")
    updated_at: Optional[datetime] = Field(..., description="Timestamp of the last update")
    
    
class ResultModel(BaseModel):
   
    final_result: str = Field(..., description="The final result of the agent's task")
    steps: list[StepsModel] = Field(..., description="List of steps taken by the agent")
    
    
    
class AgentModel(BaseModel):
    query: str = Field(..., description="The query to run the agent on")
    url: str = Field(..., description="The URL to run the agent on")
    result: ResultModel = Field(..., description="The result of the agent's task")
    user_id: str = Field(..., description="The ID of the user who initiated the task")
    created_at: datetime = Field(..., description="Timestamp of when the agent was created")
    updated_at: datetime = Field(..., description="Timestamp of the last update")