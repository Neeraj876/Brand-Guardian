import uuid
import json
import logging
from pprint import pprint

from dotenv import load_dotenv
load_dotenv(override=True)

from backend.src.graph.workflow import app

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger('brand-guardian-runner')

def run():
    """
    This function orchestrates the entire audit process:
    - creates a unique session ID
    - prepares the video URL and metadata
    - Runs the AI workflow
    - Displays the compliance results
    """

    # STEP 1: Generate the session ID
    session_id = str(uuid.uuid4())
    logger.info(f"Starting Audit Session: {session_id}")

    # STEP 2: Define the initial state
    initial_inputs = {
        "video_url": "https:youtu.be/dT7S5eYhcQ",
        "video_id": f"vid_{session_id[:8]}",
        "compliance_results": [],
        "errors": []
    }

    print("-----Initializing workflow------")
    print(f"Input Payload: {json.dumps(initial_inputs, indent=2)}")

    try:
        # app.invoke() triggers the LangGraph workflow and returns the final sttate with all results
        final_state = app.invoke(initial_inputs)
        print("\n-----Workflow execution is complete-----")
        print("\n-----COMPLIANCE AUDIT REPORT------")
        print(f"Video ID: {final_state.get('video_id')}")
        print(f"Status: {final_state.get('final_status')}")
        print("\n [VIOLATIONS DETECTED]")
        # Return the list of compliance violations
        results = final_state.get("compliance_results", [])
        if results:
            # Each issue is a dict with: severity, category, description
            for issue in results:
                print(f"- [{issue.get('severity')}] [{issue.get('category')}]: [{issue.get('description')}]")
        else:
            print("No violations detected")
        print("\n[FINAL_SUMMARY]")
        print(final_state.get('final_report'))
    except Exception as e:
        logger.error(f"Workflow Execution Failed: {str(e)}")
        raise e
    
if __name__ == "main":
    run()






if __name__ == "__main__":
    main()
