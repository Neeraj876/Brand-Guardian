import uuid        
import logging     
from fastapi import FastAPI, HTTPException  

from pydantic import BaseModel  
from typing import List, Optional

from dotenv import load_dotenv
load_dotenv(override=True)  

# Initialize the telemetry
from backend.src.api.telemetry import setup_telemetry
setup_telemetry()

# Import workflow graph
from backend.src.graph.workflow import app as compliance_graph

# Congigure logging
logging.basicConfig(level=logging.INFO)

logger = logging.getLogger("api-server")

app = FastAPI()

class AuditRequest(BaseModel):
    """
    Defines the expected structure of incoming API requests.
    
    Pydantic validates that:
    - The request contains a 'video_url' field
    - The value is a string (not int, list, etc.)
    """
    video_url: str  

class ComplianceIssue(BaseModel):
    category: str
    severity: str
    description: str

class AuditResponse(BaseModel):
    session_id: str
    video_id: str
    status: str
    final_report: str
    compliance_results: List[ComplianceIssue]

@app.post("/audit", response_model=AuditResponse)
async def audit_video(request: AuditRequest):
    """
    This endpoint triggers the 
    Process:
    1. Generate unique session ID
    2. Prepare input for LangGraph workflow
    3. Invoke the graph (Indexer → Auditor)
    4. Return formatted results
    """ 
    session_id = str(uuid.uuid4())
    video_id_short = f"vid_{session_id[:8]}"
    logger.info(f"Received the Audit Request: {request.video_url} {Session: {session_id}}")

    initial_inputs = {
        "video_url": request.video_url,
        "video_id": video_id_short,
        "compliance_results": [],
        'errors': []
    }  

    try:
        final_state = compliance_graph.invoke(initial_inputs)
        return AuditResponse(
            session_id=session_id,
            video_id = final_state.get("video_id"),
            status = final_state.get("final_status", "UNKNOWN"),
            final_report = final_state.get("final_report", "No report generated"),
            compliance_results = final_state
        )
    except Exception as e:
        logger.error(F"Audit Failed: {str(e)}")
        raise HTTPException(
            status_code = 500,
            detail = f"Workflow Execution Failed: {str(e)}"
        )

@app.get("/health")
def health_check():
    """
    Endpoint to verify the API is running.
    """
    return {"status": "healthy", "service": "Brand Guardian AI"}