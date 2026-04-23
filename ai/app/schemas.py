"""
models.py — Pydantic Models (Response ka format define karta hai)

Yeh file define karti hai ki har endpoint se EXACTLY kya format mein data jaayega.
Jaise restaurant mein menu card hota hai — ussi tarah yeh "menu card" hai
response ka. Chandan ko pata hoga ki kya expect karna hai.
"""

from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


# ============================================
# Common / Shared Models
# ============================================

class RiskLevel(str, Enum):
    """Risk severity levels — Critical se Low tak"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ============================================
# Ingest (PDF Processing) Models
# ============================================

class IngestRequest(BaseModel):
    """Chandan yeh bhejega jab PDF process karna ho"""
    document_id: str = Field(..., description="MongoDB ObjectId from Chandan's DB")
    file_url: str = Field(..., description="Cloudinary URL of the uploaded PDF")
    file_path: Optional[str] = Field(default=None, description="Local path (optional — sirf local testing ke liye)")


class IngestResponse(BaseModel):
    """Tu yeh lautaayega jab PDF process ho jaaye"""
    document_id: str
    total_pages: int
    total_chunks: int
    status: str = "ingested"


# ============================================
# Query (Sawaal-Jawab) Models
# ============================================

class ChatMessage(BaseModel):
    """Ek chat message — user ya assistant ki"""
    role: str = Field(..., description="'user' ya 'assistant'")
    content: str


class QueryRequest(BaseModel):
    """Chandan yeh bhejega jab user sawaal pooche"""
    question: str = Field(..., description="User ka sawaal")
    document_id: str = Field(..., description="Kis document mein search karna hai")
    chat_history: list[ChatMessage] = Field(
        default_factory=list,
        description="Pichli baatein (follow-up questions ke liye)"
    )


class SourceChunk(BaseModel):
    """Ek source reference — answer kahan se aaya"""
    text: str = Field(..., description="Chunk ka actual text")
    page_number: int = Field(..., description="Page number PDF mein")
    section_title: str = Field(default="", description="Section ka title, e.g., '8. Termination'")
    clause_number: str = Field(default="", description="Clause number, e.g., '8.1'")
    relevance_score: float = Field(..., description="Kitna relevant hai (0 to 1)")


class QueryResponse(BaseModel):
    """Tu yeh lautaayega jab sawaal ka jawab de"""
    answer: str = Field(..., description="LLM ka generated answer")
    sources: list[SourceChunk] = Field(default_factory=list, description="Kahan se aaya answer")
    confidence: str = Field(default="medium", description="'high', 'medium', ya 'low'")
    confidence_score: float = Field(default=0.0, description="0.0 to 1.0")


# ============================================
# Risk Analysis Models
# ============================================

class AnalyzeRequest(BaseModel):
    """Chandan yeh bhejega jab risk analysis karna ho"""
    document_id: str


class RiskFinding(BaseModel):
    """Ek risky clause ki detail"""
    clause_text: str = Field(..., description="Risky clause ka text")
    page_number: int
    section_title: str = Field(default="")
    clause_number: str = Field(default="")
    risk_level: RiskLevel
    risk_type: str = Field(default="", description="e.g., 'unfair_termination', 'restrictive_non_compete'")
    explanation: str = Field(..., description="Kyun risky hai — simple words mein")
    recommendation: str = Field(..., description="Kya karna chahiye — negotiate tip")


class RiskSummary(BaseModel):
    """Risk count by severity"""
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    safe: int = 0


class AnalyzeResponse(BaseModel):
    """Tu yeh lautaayega jab risk analysis complete ho"""
    document_id: str
    overall_score: int = Field(..., description="0-100, higher = safer")
    total_clauses_scanned: int
    summary: RiskSummary
    risks: list[RiskFinding] = Field(default_factory=list)


# ============================================
# Similar Cases Models
# ============================================

class SimilarRequest(BaseModel):
    """Chandan yeh bhejega jab similar cases dhoondne ho"""
    case_facts: str = Field(..., description="User ne case ka description diya")
    top_k: int = Field(default=10, description="Kitne results chahiye")


class SimilarCase(BaseModel):
    """Ek similar case/clause"""
    document_id: str
    document_name: str = Field(default="")
    clause_text: str
    page_number: int
    section_title: str = Field(default="")
    similarity_score: float
    relevance_explanation: str = Field(default="")


class SimilarResponse(BaseModel):
    """Tu yeh lautaayega jab similar cases mil jaayein"""
    query: str
    similar_cases: list[SimilarCase] = Field(default_factory=list)
    total_results: int = 0


# ============================================
# Summary Models
# ============================================

class SummaryRequest(BaseModel):
    """Chandan yeh bhejega jab summary chahiye"""
    document_id: str


class Party(BaseModel):
    """Document mein involved party"""
    role: str = Field(..., description="e.g., 'Employer', 'Employee'")
    name: str


class SectionSummary(BaseModel):
    """Ek section ka summary"""
    section: str = Field(..., description="e.g., '8. Termination'")
    summary: str


class SummaryResponse(BaseModel):
    """Tu yeh lautaayega jab summary ready ho"""
    document_id: str
    filename: str = Field(default="")
    document_type: str = Field(default="", description="e.g., 'Employment Contract'")
    parties: list[Party] = Field(default_factory=list)
    effective_date: str = Field(default="")
    governing_law: str = Field(default="")
    key_terms: dict = Field(default_factory=dict)
    section_summaries: list[SectionSummary] = Field(default_factory=list)
    risk_summary: str = Field(default="")
    recommendations: list[str] = Field(default_factory=list)


# ============================================
# Delete Document Model
# ============================================

class DeleteResponse(BaseModel):
    """Jab document ChromaDB se delete ho"""
    document_id: str
    chunks_deleted: int
    status: str = "deleted"
