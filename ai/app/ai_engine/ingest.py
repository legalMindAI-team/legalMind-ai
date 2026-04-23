"""
ingest.py — PDF Parsing + Chunking + ChromaDB Storage

🍕 Analogy: Yeh file "ingredients prepare karna" hai.
PDF aata hai → text nikalta hai → chhote chunks mein todta hai →
har chunk ke saath metadata lagata hai → ChromaDB mein store karta hai.

Yeh PEHLA kaam hai — jab tak yeh nahi hoga, query/risk/summary kuch nahi chalega.
"""

import os
import re
import tempfile
import fitz  # PyMuPDF — PDF parsing library
import httpx  # HTTP client — URL se PDF download karne ke liye
import chromadb
from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter

# ============================================
# 1. Environment Setup
# ============================================
load_dotenv()

CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_data")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

# ChromaDB client — persistent (data save hoti hai disk pe)
chroma_client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)


# ============================================
# 2. Embedding Function Setup
# ============================================

def get_embedding_function():
    """
    Development mein: sentence-transformers (FREE, local)
    Production mein: OpenAI embeddings (paid, better quality)

    Yeh function ek "embedding machine" return karta hai
    jo text ko numbers (vectors) mein convert karta hai.
    """
    if ENVIRONMENT == "production":
        from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
        return OpenAIEmbeddingFunction(
            api_key=os.getenv("OPENAI_API_KEY"),
            model_name="text-embedding-3-small"
        )
    else:
        from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
        return SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )


# Global embedding function — ek baar load hogi, baar baar use hogi
embedding_fn = get_embedding_function()


# ============================================
# 3. PDF Download from URL (Cloudinary)
# ============================================

def download_pdf_from_url(url: str) -> str:
    """
    Cloudinary URL se PDF download karta hai aur temp file mein save karta hai.

    🍕 Analogy: Swiggy se order aaya → pehle kitchen mein rakh lo → phir cook karo.
    Waise hi URL se PDF aata hai → pehle local temp file mein save karo → phir process karo.

    Input:  Cloudinary URL (e.g., "https://res.cloudinary.com/.../contract.pdf")
    Output: Temp file ka path jahan PDF save hua (e.g., "/tmp/abc123.pdf")

    NOTE: Temp file ko baad mein delete karna padega (ingest_document mein hoga)
    """
    print(f"[DOWNLOAD] Downloading PDF from URL: {url[:80]}...")

    # httpx se PDF download karo (with timeout aur proper headers taaki 403 error na aaye)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    response = httpx.get(url, headers=headers, timeout=60.0, follow_redirects=True)

    # Check if download was successful
    if response.status_code != 200:
        raise ConnectionError(
            f"PDF download failed. Status: {response.status_code}. "
            f"URL sahi hai? Cloudinary link expired toh nahi?"
        )

    # Check if it's actually a PDF (basic check)
    content_type = response.headers.get("content-type", "")
    if "pdf" not in content_type and not url.lower().endswith(".pdf"):
        raise ValueError(
            f"URL se PDF nahi aaya, content-type hai: {content_type}. "
            f"Cloudinary URL check karo — .pdf extension honi chahiye."
        )

    # Temp file mein save karo
    temp_file = tempfile.NamedTemporaryFile(
        suffix=".pdf",
        delete=False,  # Delete=False kyunki hum baad mein manually delete karenge
        dir=tempfile.gettempdir()
    )
    temp_file.write(response.content)
    temp_file.close()

    file_size_kb = len(response.content) / 1024
    print(f"[DOWNLOAD] Downloaded {file_size_kb:.1f} KB - saved to {temp_file.name}")

    return temp_file.name


# ============================================
# 4. PDF Text Extraction
# ============================================

def extract_text_from_pdf(file_path: str) -> list[dict]:
    """
    PDF se text nikalata hai — page by page.

    Input:  PDF file ka path (local path — URL se download ho chuki hogi)
    Output: List of {"page_number": 1, "text": "page ka text"}

    PyMuPDF (fitz) use karte hain kyunki:
    - 10x faster than other libraries
    - Page number automatically milta hai
    - Tables aur multi-column handle karta hai
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"PDF file not found: {file_path}")

    pages = []
    doc = fitz.open(file_path)

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")  # Plain text extract

        # Skip empty pages
        if text.strip():
            pages.append({
                "page_number": page_num + 1,  # 1-indexed (page 1, 2, 3...)
                "text": text.strip()
            })

    doc.close()
    return pages


# ============================================
# 4. Legal Clause Chunking
# ============================================

# Regex pattern — legal sections detect karta hai
# Matches: "1.", "2.", "1.1", "12.3", "CLAUSE 1", "SECTION A", "Article 1"
SECTION_PATTERN = re.compile(
    r'(?:^|\n)\s*'
    r'(?:'
    r'(?:CLAUSE|SECTION|Article|ARTICLE|SCHEDULE)\s+[A-Z0-9]+'  # CLAUSE 1, SECTION A
    r'|'
    r'\d{1,3}(?:\.\d{1,3})*\.?\s+'  # 1. , 1.1 , 12.3
    r')',
    re.IGNORECASE
)

# Risk-related keywords — in chunks ko flag karenge
RISK_KEYWORDS = [
    "terminate", "termination", "penalty", "penalt",
    "non-compete", "non compete", "noncompete",
    "liability", "liable", "indemnify", "indemnification",
    "forfeit", "forfeiture", "waive", "waiver",
    "confidential", "restrictive", "exclusive",
    "arbitration", "jurisdiction", "governing law",
    "intellectual property", "ip rights", "ip assignment",
    "liquidated damages", "breach", "default"
]


def detect_section_title(text: str) -> str:
    """
    Chunk ke pehle line se section title detect karta hai.
    Example: "8. Termination" → returns "8. Termination"
    """
    first_line = text.strip().split('\n')[0].strip()

    # Check if first line looks like a section heading
    if SECTION_PATTERN.match(first_line) and len(first_line) < 100:
        return first_line

    return ""


def detect_clause_number(text: str) -> str:
    """
    Clause number extract karta hai from text.
    Example: "8.1 Either party may..." → returns "8.1"
    """
    match = re.match(r'^\s*(\d{1,3}(?:\.\d{1,3})*)', text.strip())
    if match:
        return match.group(1)
    return ""


def has_risk_keywords(text: str) -> bool:
    """Check karta hai ki chunk mein risky words hain ya nahi"""
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in RISK_KEYWORDS)


def chunk_document(pages: list[dict], chunk_size: int = 800, chunk_overlap: int = 150) -> list[dict]:
    """
    Pages ko chhote chunks mein todta hai with full metadata.

    Strategy:
    1. Pehle sab pages ka text combine karo (with page markers)
    2. RecursiveCharacterTextSplitter se smart splitting karo
    3. Har chunk ke saath metadata attach karo

    chunk_size = 800 characters (ideal for legal docs — ek clause fit ho jaaye)
    chunk_overlap = 150 characters (boundary pe context preserve ho)

    Output: List of {
        "text": "chunk ka text",
        "metadata": {
            "page_number": 12,
            "section_title": "8. Termination",
            "clause_number": "8.1",
            "chunk_index": 23,
            "char_count": 342,
            "has_risk_keywords": True
        }
    }
    """

    # Step 1: Combine all page texts with page markers
    # Page markers help us track which chunk belongs to which page
    full_text = ""
    page_boundaries = []  # [(start_char, end_char, page_number)]

    for page in pages:
        start = len(full_text)
        full_text += page["text"] + "\n\n"
        end = len(full_text)
        page_boundaries.append((start, end, page["page_number"]))

    # Step 2: Split with LangChain's RecursiveCharacterTextSplitter
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=[
            "\n\n\n",   # Triple newline (section break)
            "\n\n",      # Double newline (paragraph break)
            "\n",        # Single newline
            ". ",        # Sentence end
            "; ",        # Semi-colon (common in legal)
            ", ",        # Comma
            " ",         # Space
        ]
    )

    text_chunks = splitter.split_text(full_text)

    # Step 3: Attach metadata to each chunk
    chunks_with_metadata = []

    for idx, chunk_text in enumerate(text_chunks):
        # Find which page this chunk belongs to
        chunk_start = full_text.find(chunk_text)
        page_number = 1  # default

        for start, end, pg_num in page_boundaries:
            if start <= chunk_start < end:
                page_number = pg_num
                break

        # Detect section title and clause number
        section_title = detect_section_title(chunk_text)
        clause_number = detect_clause_number(chunk_text)

        chunks_with_metadata.append({
            "text": chunk_text,
            "metadata": {
                "page_number": page_number,
                "section_title": section_title,
                "clause_number": clause_number,
                "chunk_index": idx,
                "char_count": len(chunk_text),
                "has_risk_keywords": has_risk_keywords(chunk_text)
            }
        })

    return chunks_with_metadata


# ============================================
# 5. Store in ChromaDB
# ============================================

def store_in_chromadb(document_id: str, chunks: list[dict]) -> int:
    """
    Chunks ko ChromaDB mein store karta hai.

    ChromaDB = Vector Database
    Har chunk ke liye:
    - text store hota hai (original)
    - embedding store hoti hai (numbers mein meaning)
    - metadata store hoti hai (page, section, etc.)
    - unique ID hoti hai (document_id + chunk_index)

    Return: number of chunks stored
    """

    # Collection banao ya existing mein add karo
    # "legal_docs" = ek table maano — sab documents isme jaayenge
    collection = chroma_client.get_or_create_collection(
        name="legal_docs",
        embedding_function=embedding_fn,
        metadata={"description": "LegalMind AI document chunks"}
    )

    # Prepare data for ChromaDB
    ids = []
    documents = []
    metadatas = []

    for chunk in chunks:
        # Unique ID: document_id + chunk_index
        chunk_id = f"{document_id}_chunk_{chunk['metadata']['chunk_index']}"
        ids.append(chunk_id)
        documents.append(chunk["text"])

        # ChromaDB metadata mein document_id bhi add karo
        # (filter karne ke kaam aayega — "sirf is document mein search karo")
        meta = chunk["metadata"].copy()
        meta["document_id"] = document_id
        metadatas.append(meta)

    # ChromaDB mein add karo — embeddings automatically ban jaayengi
    # Agar 100+ chunks hain toh batch mein add karo (ChromaDB limit: ~41000 per batch)
    batch_size = 100
    for i in range(0, len(ids), batch_size):
        collection.add(
            ids=ids[i:i + batch_size],
            documents=documents[i:i + batch_size],
            metadatas=metadatas[i:i + batch_size]
        )

    return len(ids)


# ============================================
# 6. Delete from ChromaDB
# ============================================

def delete_from_chromadb(document_id: str) -> int:
    """
    Ek document ke saare chunks ChromaDB se delete karta hai.
    Chandan yeh call karega jab user document delete kare.
    """
    try:
        collection = chroma_client.get_collection(
            name="legal_docs",
            embedding_function=embedding_fn
        )

        # Pehle count karo kitne chunks hain
        results = collection.get(
            where={"document_id": document_id}
        )
        chunk_count = len(results["ids"])

        if chunk_count > 0:
            # Delete by IDs
            collection.delete(ids=results["ids"])

        return chunk_count

    except Exception:
        return 0


# ============================================
# 8. Main Ingest Function (sab ko jodhti hai)
# ============================================

def ingest_document(document_id: str, file_url: str = None, file_path: str = None) -> dict:
    """
    MAIN FUNCTION — PDF se ChromaDB tak ka poora pipeline.

    🍕 Analogy: Full order process:
    PDF aata hai (URL se ya local se) -> text nikalo -> chunks banao -> ChromaDB mein dalo

    Steps:
    1. URL se PDF download karo (ya local path se padho)
    2. PDF se text nikalo (page by page)
    3. Text ko chunks mein todo (with metadata)
    4. Chunks ko ChromaDB mein store karo (with embeddings)
    5. Temp file cleanup karo (agar URL se download kiya tha)

    Input:
      - document_id: Chandan dega (MongoDB ObjectId)
      - file_url: Cloudinary URL (Chandan production mein yeh bhejega)
      - file_path: Local path (sirf testing ke liye)
      Dono mein se ek toh hona chahiye!

    Output: {"document_id": "...", "total_pages": 24, "total_chunks": 47, "status": "ingested"}
    """

    # Validate: URL ya path — kuch toh chahiye
    if not file_url and not file_path:
        raise ValueError("file_url ya file_path mein se ek toh dena padega!")

    temp_file_path = None  # Track karenge — cleanup ke liye

    try:
        # Step 1: PDF file ka path le — URL se download ya local use karo
        if file_url:
            # Cloudinary URL se download karo temp file mein
            local_path = download_pdf_from_url(file_url)
            temp_file_path = local_path  # Baad mein delete karenge
        else:
            # Local path directly use karo (testing ke liye)
            local_path = file_path

        # Step 2: PDF se text nikalo
        print(f"[INGEST] Step 1/3: Extracting text from PDF...")
        pages = extract_text_from_pdf(local_path)
        total_pages = len(pages)
        print(f"[INGEST] Extracted {total_pages} pages")

        if total_pages == 0:
            raise ValueError(
                "PDF mein koi text nahi mila. "
                "Yeh scanned PDF ho sakta hai — OCR ki zaroorat hai."
            )

        # Step 3: Chunks banao
        print(f"[INGEST] Step 2/3: Chunking document...")
        chunks = chunk_document(pages)
        print(f"[INGEST] Created {len(chunks)} chunks")

        # Step 4: ChromaDB mein store karo
        print(f"[INGEST] Step 3/3: Storing in ChromaDB...")
        stored_count = store_in_chromadb(document_id, chunks)
        print(f"[INGEST] Stored {stored_count} chunks in ChromaDB")

        return {
            "document_id": document_id,
            "total_pages": total_pages,
            "total_chunks": stored_count,
            "status": "ingested"
        }

    finally:
        # Step 5: Cleanup — temp file delete karo
        # "finally" = chahe error aaye ya na aaye, yeh zaroor chalega
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
            print(f"[INGEST] Temp file cleaned up: {temp_file_path}")


# ============================================
# Quick Test (Direct run karo toh test hoga)
# ============================================

if __name__ == "__main__":
    """
    Test karne ke liye:
    python ingest.py

    Yeh ek sample document ingest karega aur result dikhayega.
    NOTE: Tujhe ek sample PDF rakhna padega test_data/ folder mein.
    """
    import json

    # Test with a sample PDF (agar hai toh)
    sample_pdf = "./test_data/sample_contract.pdf"

    if os.path.exists(sample_pdf):
        result = ingest_document(
            document_id="test_doc_001",
            file_path=sample_pdf
        )
        print("\n✅ RESULT:")
        print(json.dumps(result, indent=2))
    else:
        print(f"⚠️ Sample PDF not found at: {sample_pdf}")
        print("Create a test_data/ folder and put a sample contract PDF there.")
        print("\nTesting individual functions instead...\n")

        # Test with dummy text
        dummy_pages = [
            {"page_number": 1, "text": """
1. APPOINTMENT AND DUTIES
1.1 The Company hereby appoints the Employee as Software Developer.
1.2 The Employee shall report to the Engineering Manager.

2. COMPENSATION
2.1 The annual CTC shall be Rs. 8,00,000 (Eight Lakhs).
2.2 The salary shall be paid monthly by direct bank transfer.
            """},
            {"page_number": 2, "text": """
3. TERMINATION
3.1 Either party may terminate this agreement by providing 90 days written notice.
3.2 The Company reserves the right to terminate without cause with 7 days payment in lieu.

4. NON-COMPETE
4.1 The Employee agrees to a non-compete period of 24 months across all geographies.
            """}
        ]

        print("Testing chunking...")
        chunks = chunk_document(dummy_pages)
        for i, chunk in enumerate(chunks):
            print(f"\n--- Chunk {i} ---")
            print(f"Text: {chunk['text'][:100]}...")
            print(f"Metadata: {json.dumps(chunk['metadata'], indent=2)}")

        print(f"\n✅ Total chunks created: {len(chunks)}")
        print("✅ Chunking works! Now add a real PDF to test full pipeline.")
