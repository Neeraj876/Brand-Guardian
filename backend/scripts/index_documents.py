import os
import glob
import logging
from dotenv import load_dotenv
load_dotenv(override=True)

# Document loaders and splitters
from langchain_components.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from langchain_openai import AzureOpenAIEmbeddings
from langchain_community.vectorstores import AzureSearch

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger("indexer")

def index_docs():
    """
    Read the PDFs, split them into chunks, generate embeddings, and then upload them to Azure AI Searxh.
    """

    # look for data folder
    current_dir = os.path.dirname(os.path.abspath(__file__))
    data_folder = os.path.join(current_dir, "../../backend/data")

    logger.info("="*60)
    logger.info("Environment Configuration Check: ")
    logger.info(f"AZURE_OPENAI_ENDPOINT: {os.getenv("AZURE_OPENAI_ENDPOINT")}")
    logger.info(f"AZURE_OPENAI_API_VERSION: {os.getenv("AZURE_OPENAI_API_VERSION")}")
    logger.info(f"Embedding Deployment: {os.getenv('AZURE_OPENAI_EMBEDDING_DEPLOYMENT', 'text-embedding-3-small')}")
    logger.info(f"AZURE_SEARCH_ENDPOINT: {os.getenv('AZURE_SEARCH_ENDPOINT')}")
    logger.info(f"AZURE_SEARCH_INDEX_NAME: {os.getenv('AZURE_SEARCH_INDEX_NAME')}")
    logger.info("="*60)

    # Validate the required environment variables
    required_env_vars = [
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_API_VERSION",
        "AZURE_OPENAI_EMBEDDING_DEPLOYMENT",
        "AZURE_SEARCH_ENDPOINT",
        "AZURE_SEARCH_KEY",
        "AZURE_SEARCH_INDEX"
    ]

    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        logger.error("Please check your .env file and ensure all the variables are set")
        return

    # Initialize the embedding model
    try:
        logger.info("Initializing Azure Open AI Embeddings.....")
        embeddings = AzureOpenAIEmbeddings(
            azure_deplyment = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", 'text-embedding-3-small'),
            azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key = os.getenv("AZURE_OPENAI_API_KEY"),
            openai_api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01"),
        )

        logger.info("Embeddings model initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize embeddings: {e}")
        logger.error("Please verify your Azure OpenAI deployment name and endpoint.")
        return
    
    # Initialize the Azure Search
    try:
        logger.info("Initializing Azure AI Search Vector Store.....")
        vector_store = AzureSearch(
            azure_search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT"),
            azure_search_key = os.getenv("AZURE_SEARCH_API_KEY"),
            index_name = os.getenv("AZURE_SEARCH_INDEX_NAME"),
            embedding_function = embeddings.embed_query,
        )

        logger.info("Vector Store initialized for index: {index_name}")
    except Exception as e:
        logger.error(f"Failed to initialize Azure AI Search: {e}")
        logger.error("Please verify your Azure Search Endpoint, API key and index name.")
        return

    # Step 1: Load documents
    pdf_files = glob.glob(os.path.join(data_folder, "*.pdf"))
    if not pdf_files:
        logger.warning("No PDFs found in {data_folder}. Please add files.")
    logger.info(f"Found {len(pdf_files)} PSfs to process: {[os.path.basename(f) for f in pdf_files]}")

    all_chunks = []

    # Process each pdf
    for pdf_file in pdf_files:
        try:
            logger.info(f"Loading: {os.path.basename(pdf_file)}")
            loader = PyPDFLoader(pdf_file)
            raw_docs = loader.load()

            # Step 2: Split documents into chunks (Chunking strategy)
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
            chunks = text_splitter.split_documents(raw_docs)
            for chunk in chunks:
                chunk.metadata["source"] = os.path.basename(pdf_file)

            all_chunks.extend(chunks)
            logger.info(f"Split into {len(chunks)} chunks.")
        
        except Exception as e:
            logger.error(f"Failed to process {pdf_file}: {e}")

        # Upload to Azure
        if all_chunks:
            logger.info(f"Uploading {len(all_chunks)} chunks to Azure AI Search Index '{index_name}'")
            try:
                # Azure search accepts batches automatically via this method
                vector_store.add_documents(documents = all_chunks)
                logger.info("="*60)
                logger.info("Indexing Complete! Knowdge Base is ready...")
                logger.info(f"Total chunks indexed: {len(all_chunks)}")
                logger.info("="*60)
            except Exception as e:
                logger.error(f"Failed to upload the documents to Azure Search: {e}")
                logger.error("Please check the Azure Search configuration and try again")
        else:
            logger.warning("No documents were processed")

if __name__ == "__main__":
    index_docs()
         




    



