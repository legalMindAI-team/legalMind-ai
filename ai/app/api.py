from fastapi import APIRouter, HTTPException
from app.schemas import (
    IngestRequest, IngestResponse,
    QueryRequest, QueryResponse,
    AnalyzeRequest, AnalyzeResponse,
    SimilarRequest, SimilarResponse,
    SummaryRequest, SummaryResponse,
    DeleteResponse,
)
from app.ai_engine.ingest import ingest_document, delete_from_chromadb
from app.ai_engine.query import query_document

# Define APIRouter instead of app
router = APIRouter()

# ============================================
# ENDPOINT 1: PDF Ingest (Process karo)
# ============================================

@router.post("/ingest", response_model=IngestResponse)
def api_ingest(request: IngestRequest):
    """
    PDF ko process karo — text nikalo, chunks banao, ChromaDB mein daalo.
    """
    try:
        result = ingest_document(
            document_id=request.document_id,
            file_url=request.file_url,
            file_path=request.file_path
        )
        return IngestResponse(**result)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ConnectionError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingest failed: {str(e)}")


# ============================================
# ENDPOINT 2: Query (Sawaal ka jawab do)
# ============================================

@router.post("/query", response_model=QueryResponse)
def api_query(request: QueryRequest):
    """
    User ka sawaal lo -> document mein search karo -> LLM se answer do.
    """
    try:
        chat_history = [
            {"role": msg.role, "content": msg.content}
            for msg in request.chat_history
        ]
        result = query_document(
            question=request.question,
            document_id=request.document_id,
            chat_history=chat_history
        )
        return QueryResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


# ============================================
# ENDPOINT 3: Risk Analysis
# ============================================

@router.post("/analyze", response_model=AnalyzeResponse)
def api_analyze(request: AnalyzeRequest):
    raise HTTPException(
        status_code=501,
        detail="Risk analyzer abhi build nahi hua. Phase 4 mein aayega."
    )


# ============================================
# ENDPOINT 4: Similar Cases
# ============================================

@router.post("/similar", response_model=SimilarResponse)
def api_similar(request: SimilarRequest):
    raise HTTPException(
        status_code=501,
        detail="Similar search abhi build nahi hua. Phase 5 mein aayega."
    )


# ============================================
# ENDPOINT 5: Summary
# ============================================

@router.post("/summary", response_model=SummaryResponse)
def api_summary(request: SummaryRequest):
    raise HTTPException(
        status_code=501,
        detail="Summary generator abhi build nahi hua. Phase 5 mein aayega."
    )


# ============================================
# ENDPOINT 6: Delete Document from ChromaDB
# ============================================

@router.delete("/documents/{document_id}", response_model=DeleteResponse)
def api_delete_document(document_id: str):
    try:
        chunks_deleted = delete_from_chromadb(document_id)
        return DeleteResponse(
            document_id=document_id,
            chunks_deleted=chunks_deleted
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")
