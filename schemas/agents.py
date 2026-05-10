from pydantic import BaseModel 

class AgentRunRequest(BaseModel):
    query: str 
    model: str 
    summarize_model: str = "google/gemini-3.1-flash-lite-preview"