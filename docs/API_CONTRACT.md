# API Contract — LegalMind AI
# Ritik (AI) aur Chandan (Backend) ke beech agreement

## POST /api/ai/upload
PDF ingestion trigger karna

Request Body:
{
  "document_id": "string",
  "file_path": "string", 
  "document_name": "string"
}

Response:
{
  "status": "success",
  "chunks_created": 47,
  "pages_processed": 12
}

---

## POST /api/ai/query
Question poochna document se

Request Body:
{
  "document_id": "string",
  "question": "string",
  "session_id": "string"
}

Response:
{
  "answer": "string",
  "sources": [
    {
      "page_number": 8,
      "section_title": "11. Termination",
      "clause_text": "string"
    }
  ],
  "confidence": "high"
}

---

## GET /api/ai/risk-summary
Document ke risky clauses

Query Param: ?document_id=xxx

Response:
{
  "total_risks": 5,
  "critical": 2,
  "high": 1,
  "medium": 2,
  "findings": [
    {
      "clause_text": "string",
      "page_number": 3,
      "risk_level": "Critical",
      "explanation": "string"
    }
  ]
}