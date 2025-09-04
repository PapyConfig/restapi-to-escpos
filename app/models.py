from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class PrintJob(BaseModel):
    commands: List[Dict[str, Any]]
    encoding: str = "utf-8"

class PrintResponse(BaseModel):
    success: bool
    message: str
    job_id: Optional[str] = None
