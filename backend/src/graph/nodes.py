import os
import re
import json
import logging
from typing import List, Dict, Any

from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings
from langchain_community.vectorstores import AzureSearch
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage

# import state schema
from backend.src.graph.state import VideoAuditState, ComplianceIssue

# import services
from backend.src.services.video_indexer import VideoIndexerService
from backend.src.services.blob_storage import BlobStorageService

logger = logging.getLogger("brand-guardian")
logging.basicConfig(level=logging.INFO)

# Node 1: Indexer
def index_video_node(state: VideoAuditState) -> VideoAuditState:
    """
    This function is responsible for converting video to text. First, it downloads the youtube video from the url, uploads to the azure video indexer, then extracts the metadata and transcript from the video and updates the state.
    """

    video_url = state.get('video_url')
    video_id_input = state.get('video_id', 'vid_demo')

    logger.info(f"----[Node:Indexer] Processing: {video_url}")

    local_filename = "temp_audit_video.mp4"

    blob_name = f"{video_id_input}.mp4"

    try:
        vi_service = VideoIndexerService()
        blob_service = BlobStorageService()

        # Step 1: Download the video locally
        if "youtube.com" in video_url or "youtu.be" in video_url:
            local_path = vi_service.download_youtube_video(video_url, output_path=local_filename)
        else:
            raise Exception("Please provide a valid YouTube URL.")

        # Step 2: Upload local file to Azure Blob Storage
        blob_service.upload(local_path, blob_name)

        # Step 3: Generate a SAS URL for Video Indexer to fetch the video
        sas_url = blob_service.generate_sas_url(blob_name)

        # Step 4: Submit the SAS URL to Azure Video Indexer and get the video ID
        azure_video_id = vi_service.upload_video(sas_url, video_name=video_id_input)
        logger.info(f"Video submitted to Azure Video Indexer with ID: {azure_video_id}")

        # Step 5: Clean up the local video file
        if os.path.exists(local_path):
            os.remove(local_path)

        # Step 6: Clean up the blob from storage
        blob_service.delete(blob_name)

        # Step 7: Poll until processing is complete and get insights
        raw_insights = vi_service.get_video_insights(azure_video_id)

        # Step 8: Extract relevant data from the insights
        clean_data = vi_service.extract_data(raw_insights)

        logger.info(f"----[Node:Indexer] Extracted Complete")
        return clean_data 

    except Exception as e:
        logger.error(f"Video Indexer failed: {str(e)}")
        # state['errors'].append(f"Indexer error: {str(e)}")
        return {
            "errors": [str(e)],
            "final_status": "FAIL",
            "transcript": "",
            "ocr_text": []
        }
    
# Node 2: Compliance Auditor
def compliance_audit_node(state: VideoAuditState) -> Dict[str, Any]:
    """
    This node performs retrieval augmented generation to audit the content of the video for compliance issues. 
    """
    logger.info(f"----[Node: Compliance Auditor] querying knowledge base & LLM")

    transcript = state.get('transcript', '')
    if not transcript:
        logger.warning("No transcript available. Skipping audit......")
        return {
            "final_status" : "FAIL",
            "final_report" : "Audit skipped because video processing failed (No Transcript)"
        }
    
    # Initialize clients

    llm = AzureChatOpenAI(
        azure_deplyment= os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT"),
        openai_api_version= os.getenv("AZURE_OPENAI_API_VERSION"),
        temperature=0.0
    )

    embeddings = AzureOpenAIEmbeddings(
        azure_deployment="text-embedding-3-small",
        openai_api_version= os.getenv("AZURE_OPENAI_API_VERSION"),
    )

    vector_store = AzureSearch(
        azure_search_endpoint=os.getenv("AZURE_SEARCH_ENDPOINT"),  
        azure_search_key=os.getenv("AZURE_SEARCH_KEY"),
        index_name=os.getenv("AZURE_SEARCH_INDEX"),
        embedding_function=embeddings.embed_query
    )

    # RAG Retrieval

    ocr_text = state.get('ocr_text', [])
    query_text = f"{transcript} {''.join(ocr_text)}"

    # Perform similarity search in the vector store to retrieve relevant documents based on the transcript and OCR text. K=3 means we want to retrieve the top 3 most relevant documents.
    docs = vector_store.similarity_search(query_text, k=3)

    # We extract the page content from the retrieved documents and concatenate them into a single string, separated by two newlines for better readability. This string will be used as context for the LLM to generate the compliance audit report.
    retrieved_rules = "\n\n".join([doc.page_content for doc in docs])

    system_prompt = f"""
    You are a senior brand compliance auditor.
    OFFICIAL REGULATORY RULES:
    {retrieved_rules}
    INSTRUCTIONS:
    1. Analyze the Transcript and OCT text below.
    2. Identify ANY violations of the rules.
    3. Return strictly JSON in the following format:
    {{
    "compliance_results": [
        {{
        "category": "Claim Validation",
        "severity": "CRITICAL",
        "description": "Explanation of the violation..."
        }}
    ],
    "status": "FAIL",
    "final_report": "Summary of findings..."
    }}

    If no violations are found, set "status" to "PASS" and "compliance_results" to [].
    """

    user_message = f"""
    VIDEO_METADATA : {state.get('video_metadata',{})}
    TRANSCRIPT : {transcript}
    ON-SCREEN TEXT (OCR) : {ocr_text}
    """

    try:
        response = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=user_message)])
        content = response.content

        # The LLM might return the JSON wrapped in markdown code blocks, so we need to extract the JSON string from the response content before parsing it.
        if "```" in content:
            content = re.search(r"```(?:json)?(.?)```", content, re.DOTALL).group(1)

        audit_data = json.loads(content.strip())
        return {
            "compliance_results": audit_data.get("compliance_results", []),
            "final_status": audit_data.get("status", "FAIL"),
            "final_report": audit_data.get("final_report", "")
        }
    except Exception as e:
        logger.error(f"System Error in auditor node: {str(e)}")
        # logging the raw response
        logger.error(f"Raw LLM response: {response.content if 'response' in locals() else 'None'}")
        return {
            "errors": [str(e)],
            "final_status": "FAIL",
        }