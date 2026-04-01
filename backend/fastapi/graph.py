import requests
from typing import TypedDict, List
from langgraph.graph import StateGraph, END
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
import os

# 1. Define the "State" (What data moves between steps)
class GraphState(TypedDict):
    file_url: str
    document_id: str
    chunks: List[str]
    status: str

# 2. Node: Download PDF from Cloudinary
def download_pdf_node(state: GraphState):
    print(f"--- DOWNLOADING PDF FROM CLOUDINARY ---")
    file_url = str(state['file_url'])
    
    # Temporarily save the file to read it
    response = requests.get(file_url, timeout=30)
    response.raise_for_status()
    content_type = response.headers.get("Content-Type", "")
    content_type_lc = content_type.lower()
    allowed_binary_types = ("application/pdf", "application/octet-stream")
    if not any(t in content_type_lc for t in allowed_binary_types):
        raise ValueError(f"Downloaded content is not a supported PDF response. Content-Type: {content_type}")

    # Some providers return application/octet-stream for PDFs, so verify magic bytes.
    if not response.content.startswith(b"%PDF"):
        raise ValueError(
            f"Downloaded file is not a valid PDF binary. Content-Type: {content_type}"
        )

    temp_filename = f"temp_{state['document_id']}.pdf"
    
    with open(temp_filename, "wb") as f:
        f.write(response.content)
    
    return {"status": "downloaded", "file_path": temp_filename}

# 3. Node: Extract Text and Chunk it
def chunking_node(state: GraphState):
    print(f"--- CHUNKING PDF CONTENT ---")
    temp_filename = f"temp_{state['document_id']}.pdf"
    
    loader = PyPDFLoader(temp_filename)
    pages = loader.load()
    
    # Split text into 1000 character pieces
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
    docs = text_splitter.split_documents(pages)
    
    # Cleanup temp file after reading
    if os.path.exists(temp_filename):
        os.remove(temp_filename)
        
    return {"chunks": [d.page_content for d in docs], "status": "chunked"}

# 4. Build the Graph
workflow = StateGraph(GraphState)

workflow.add_node("downloader", download_pdf_node)
workflow.add_node("chunker", chunking_node)

workflow.set_entry_point("downloader")
workflow.add_edge("downloader", "chunker")
workflow.add_edge("chunker", END)

# Compile the graph
rag_app = workflow.compile()