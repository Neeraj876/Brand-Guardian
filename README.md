# Azure Multi-Modal Compliance QA Pipeline

This is an end-to-end compliance RAG solution designed to audit video advertisements for brand and platform compliance. The system combines video ingestion, transcript and OCR extraction, policy retrieval, reranking, and LLM-based reasoning to generate structured compliance reports. It is built as a practical applied AI workflow that connects Azure Video Indexer, Azure AI Search, Azure OpenAI, and LangGraph into a single runtime pipeline.

## Introduction

Compliance review for creative assets is often manual, inconsistent, and hard to scale. This project automates that workflow by analyzing YouTube videos against a policy knowledge base. The system downloads a video, extracts speech and on-screen text, retrieves relevant policy evidence, and generates an audit report with issues, severity, and final PASS or FAIL status.

The project is designed as a workflow-based RAG system rather than a simple prompt wrapper. It includes offline knowledge-base ingestion, claim-focused retrieval, hybrid search, cross-encoder reranking, and offline evaluation with RAGAS. The pipeline is multi-modal in the sense that it audits both spoken content and on-screen text extracted from video.

## Architecture
![Architecture Placeholder](PLACEHOLDER_architecture.png)

## Tech Stack

| Category | Tools/Technologies | Description |
|----------|---------------------|-------------|
| API Layer | FastAPI | Exposes audit and health endpoints |
| Orchestration | LangGraph | Manages the Indexer -> Auditor runtime flow |
| Retrieval | Azure AI Search | Stores and retrieves indexed policy chunks |
| LLM | Azure OpenAI | Used for claim extraction, compliance audit generation, and evaluation |
| Embeddings | Azure OpenAI Embeddings | Generates vector embeddings for policy documents and retrieval queries |
| Video Intelligence | Azure Video Indexer | Extracts transcript and OCR from uploaded video content |
| File Storage | Azure Blob Storage | Temporarily stores downloaded videos and provides SAS URLs |
| Download Layer | yt-dlp | Downloads YouTube videos before ingestion |
| Reranking | Sentence Transformers CrossEncoder | Reranks retrieved chunks before final prompting |
| Evaluation | RAGAS, datasets | Runs offline quality evaluation over saved test cases |
| Observability | Azure Application Insights | Optionally tracks runtime telemetry when configured |

# Project Highlights

## RAG Pipeline & Evaluation

- **End-to-End Compliance RAG Pipeline**  
  The project covers the full path from video ingestion to final compliance report generation.

- **Transcript + OCR Based Analysis**  
  The system uses both spoken and on-screen text extracted from video, so the audit does not depend only on transcript content.

- **Claim-Focused Retrieval**  
  Instead of embedding the entire transcript as one query, the auditor extracts compliance-relevant claims and retrieves policy evidence for those claims.

- **Hybrid Search for Better Recall**  
  Azure AI Search is used in hybrid mode to combine lexical and vector signals during retrieval.

- **Cross-Encoder Reranking**  
  Retrieved policy chunks are reranked using a sentence-transformers cross-encoder before being passed to the final audit model.

- **Offline RAG Evaluation**  
  The project includes a lightweight evaluation runner that measures faithfulness, answer relevancy, LLM context precision without reference, latency, and error rate.

## Infrastructure & Deployment

- **Azure-Native Processing Stack**  
  The system integrates Azure Blob Storage, Azure Video Indexer, Azure AI Search, Azure OpenAI, and Application Insights.

- **Workflow-Based Backend Design**  
  LangGraph orchestrates a fixed Indexer -> Auditor execution flow with clear separation of responsibilities.

- **API-Ready Service Layer**  
  The project is exposed through FastAPI, making it easy to integrate with a future frontend or external system.

- **Policy Knowledge Base Ingestion**  
  PDF policy documents are indexed into Azure AI Search through a dedicated ingestion script.

## Search, Retrieval & Quality

- **Knowledge Base Indexing**  
  Policy PDFs are chunked, embedded, and stored in Azure AI Search with retrieval metadata.

- **Hybrid + Rerank Retrieval Stack**  
  The runtime retrieval path combines hybrid search with custom reranking for higher quality final context.

- **Evaluation-Driven Iteration**  
  The project includes an offline eval runner so retrieval and prompting improvements can be measured instead of guessed.

## Components

### 1. API Layer (FastAPI)
FastAPI exposes the main runtime interfaces of the system.

- `POST /audit`
- `GET /health`

### 2. Runtime Workflow (LangGraph)
The runtime execution is organized as a two-node graph:

- **Indexer Node**
  - downloads video using `yt-dlp`
  - uploads it to Azure Blob Storage
  - creates a SAS URL
  - sends the video to Azure Video Indexer
  - extracts transcript and OCR text

- **Compliance Auditor Node**
  - extracts compliance-relevant claims
  - retrieves policy evidence from Azure AI Search
  - reranks candidate chunks with a cross-encoder
  - generates the final compliance report with Azure OpenAI

### 3. Knowledge Base Ingestion
Policy documents are processed through `backend/scripts/index_documents.py`.

- PDFs are loaded from `backend/data`
- chunks are created with `RecursiveCharacterTextSplitter`
- embeddings are generated with Azure OpenAI
- chunks are stored in Azure AI Search with metadata such as:
  - `source`
  - `page`
  - `chunk_index`
  - `evidence_id`

### 4. Retrieval and Reranking
The retrieval pipeline is designed to improve evidence quality before final prompting.

- **Claim Extraction**
  - transcript and OCR content are converted into focused compliance claims

- **Hybrid Retrieval**
  - Azure AI Search returns lexical + vector candidates

- **Cross-Encoder Reranking**
  - a sentence-transformers reranker reorders those candidates by relevance

### 5. Offline Evaluation
The project includes an offline evaluation pipeline in `backend/evals/run_eval.py`.

- loads evaluation cases from `backend/evals/data/eval_set.jsonl`
- runs the auditor for each case
- computes:
  - `faithfulness`
  - `answer_relevancy`
  - `llm_context_precision_without_reference`
  - `avg_latency_ms`
  - `error_rate`
- writes JSON reports to `backend/evals/reports`

---

## How to Run the Project

This section provides a step-by-step guide on how to set up and run the Compliance QA Pipeline locally.

### Installation

1. **Clone the Repository:**
   ```bash
   git clone <your-repo-url>
   cd ComplianceQAPipeline
   ```

2. **Install Dependencies:**
   Using `uv`:
   ```bash
   uv sync
   ```

   Using `venv` and `pip`:
   ```bash
   python -m venv .venv
   .venv/Scripts/activate
   pip install -e .
   ```

### Local Setup

1. **Configure Environment Variables:**
   Add a `.env` file in the project root with:

   - `AZURE_OPENAI_ENDPOINT`
   - `AZURE_OPENAI_API_KEY`
   - `AZURE_OPENAI_API_VERSION`
   - `AZURE_OPENAI_CHAT_DEPLOYMENT`
   - `AZURE_OPENAI_EMBEDDING_DEPLOYMENT`
   - `AZURE_SEARCH_ENDPOINT`
   - `AZURE_SEARCH_KEY`
   - `AZURE_SEARCH_INDEX`
   - `AZURE_VI_ACCOUNT_ID`
   - `AZURE_VI_LOCATION`
   - `AZURE_SUBSCRIPTION_ID`
   - `AZURE_RESOURCE_GROUP`
   - `AZURE_VI_NAME`
   - `AZURE_STORAGE_ACCOUNT_NAME`
   - `AZURE_STORAGE_CONTAINER_NAME`
   - `APPLICATIONINSIGHTS_CONNECTION_STRING` (optional)

2. **Index Policy Documents:**
   ```bash
   python backend/scripts/index_documents.py
   ```

3. **Run the FastAPI Backend:**
   ```bash
   uvicorn backend.src.api.server:app --reload --port 8000
   ```

4. **Trigger an Audit Request:**
   ```bash
   curl -X POST "http://localhost:8000/audit" \
     -H "Content-Type: application/json" \
     -d "{\"video_url\":\"https://youtu.be/dT7S5eYhcQ\"}"
   ```

### Evaluation

1. **Run Offline Evaluation:**
   ```bash
   python -m backend.evals.run_eval --tag baseline
   ```

2. **Run a Quick Smoke Check:**
   ```bash
   python -m backend.evals.run_eval --tag smoke --max-cases 2
   ```

3. **Review Generated Reports:**
   Reports are saved under:
   ```text
   backend/evals/reports/
   ```

---

## Notes

- The current evaluation setup is a practical hiring-focused silver eval using RAGAS.
- Strict benchmark-style retrieval metrics such as `Precision@K` and `Recall@K` can be added later with labeled relevance judgments.
- The current system is best described as a workflow-based multi-modal compliance pipeline with RAG, not a fully autonomous agent loop.
