import operator 
from typing import Annotated, Any, Dict, List, Optional, TypedDict

## Define the schema for a single compliance result

class ComplianceIssue(TypedDict):
    description: str   # Specific detail of violation
    severity: str      # CRITICAL | WARNING
    category: str
    timestamp: Optional[str]

## Define the global graph state
# This defines the state that gets passed around in the agentic workflow
class VideoAuditState(TypedDict):
    """
    Defines the data schema for langgraph execution content.
    It holds all the information about the audit right from the initial URL to the final report.
    """
    # Input parameters
    video_id: str
    video_url: str

    # Ingestion and extraction data
    local_file_path: Optional[str]
    video_metadata: Dict[str, Any]   # {"duration": 15, "resolution": "1920x1080", ...}
    transcript: Optional[str]        # Fully extracted speech-to-text
    ocr_text: List[str]

    # Analysis output
    # Stores the list of all the violations found by AI, which will be used to generate the final report card.
    compliance_results: Annotated[List[ComplianceIssue], operator.add]

    # Final  deliverables:
    final_status: str  # PASS | FAIL
    final_report: str  # Markdown format

    # System observability
    # Stores the list of system level errors encountered during the entire workflow
    errors: Annotated[List[str], operator.add]  # List of error messages encountered during processing
