"""
query.py — Hybrid Search + LLM Answer Generation

🍕 Analogy: Yeh file "order process karna" hai.
Customer (user) ne sawaal poocha → Chef (tu) ingredients dhoondega (search)
→ best ingredients select karega (rerank) → khaana banayega (LLM answer)
→ plate mein serve karega (structured response with sources).

FULL PIPELINE:
Question aaya → BM25 search (keyword) + ChromaDB search (semantic)
→ dono combine (Ensemble) → Cohere Rerank (best select)
→ LLM se answer generate → sources ke saath return

This is the HEART of LegalMind AI.
"""

import os
import chromadb
from dotenv import load_dotenv
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from app.ai_engine.prompts import QUERY_SYSTEM_PROMPT

# ============================================
# 1. Environment Setup
# ============================================
load_dotenv()

CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_data")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
COHERE_API_KEY = os.getenv("COHERE_API_KEY", "")

# ChromaDB client
chroma_client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)


# ============================================
# 2. Embedding Function (same as ingest.py)
# ============================================

def get_embedding_function():
    """Same embedding function as ingest.py — consistency zaroori hai"""
    if ENVIRONMENT == "production":
        from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
        return OpenAIEmbeddingFunction(
            api_key=OPENAI_API_KEY,
            model_name="text-embedding-3-small"
        )
    else:
        from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
        return SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )


embedding_fn = get_embedding_function()


# ============================================
# 3. LLM Setup (Groq for dev, OpenAI for prod)
# ============================================

def get_llm():
    """
    Development: Groq (FREE — llama-3.3-70b-versatile)
    Production: OpenAI GPT-4o (paid, better quality)

    LLM = Large Language Model = jo actually answer generate karta hai
    """
    if ENVIRONMENT == "production" and OPENAI_API_KEY:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model="gpt-4o",
            api_key=OPENAI_API_KEY,
            temperature=0.1,  # Low temperature = factual, less creative
        )
    else:
        from langchain_groq import ChatGroq
        return ChatGroq(
            model="llama-3.3-70b-versatile",
            api_key=GROQ_API_KEY,
            temperature=0.1,
        )


# ============================================
# 4. Semantic Search (ChromaDB)
# ============================================

def semantic_search(query: str, document_id: str, top_k: int = 10) -> list[dict]:
    """
    ChromaDB mein semantic search — meaning ke basis pe dhoondta hai.

    🍕 Analogy: Tu bolta hai "notice period kitna hai?"
    Yeh function aise chunks dhoondhega jo MEANING mein similar hain —
    chahe exact words match na karein.

    "How many days before resignation?" bhi match karega
    kyunki MEANING same hai (semantic similarity).
    """
    try:
        collection = chroma_client.get_collection(
            name="legal_docs",
            embedding_function=embedding_fn
        )

        results = collection.query(
            query_texts=[query],
            n_results=top_k,
            where={"document_id": document_id}  # Sirf is document mein search
        )

        # Convert ChromaDB results to our format
        chunks = []
        if results and results["documents"] and results["documents"][0]:
            for i in range(len(results["documents"][0])):
                chunks.append({
                    "text": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i],
                    "score": 1 - results["distances"][0][i]  # Distance → similarity convert
                })

        return chunks

    except Exception as e:
        print(f"[SEARCH] Semantic search error: {e}")
        return []


# ============================================
# 5. BM25 Keyword Search
# ============================================

def bm25_search(query: str, document_id: str, top_k: int = 10) -> list[dict]:
    """
    BM25 = Keyword-based search — exact words match karta hai.

    🍕 Analogy: Old-school Google search.
    Tu type kare "Section 15.4" ya "force majeure" →
    yeh EXACTLY wahi words dhoondhega document mein.

    Semantic search yeh miss kar sakta hai kyunki
    "force majeure" ka koi "similar meaning" nahi hota —
    yeh ek specific legal term hai.

    BM25 + Semantic = Best of both worlds (Hybrid Search)
    """
    try:
        collection = chroma_client.get_collection(
            name="legal_docs",
            embedding_function=embedding_fn
        )

        # Get ALL chunks for this document
        results = collection.get(
            where={"document_id": document_id}
        )

        if not results["documents"]:
            return []

        # Convert to LangChain Document format (BM25Retriever needs this)
        documents = []
        for i in range(len(results["documents"])):
            documents.append(
                Document(
                    page_content=results["documents"][i],
                    metadata=results["metadatas"][i]
                )
            )

        # BM25 Retriever banao
        bm25_retriever = BM25Retriever.from_documents(
            documents,
            k=top_k
        )

        # Search karo
        bm25_results = bm25_retriever.invoke(query)

        # Convert to our format
        chunks = []
        for i, doc in enumerate(bm25_results):
            chunks.append({
                "text": doc.page_content,
                "metadata": doc.metadata,
                "score": 1.0 - (i * 0.05)  # Rank-based score (1st = 1.0, 2nd = 0.95, etc.)
            })

        return chunks

    except Exception as e:
        print(f"[SEARCH] BM25 search error: {e}")
        return []


# ============================================
# 6. Hybrid Search (BM25 + Semantic Combined)
# ============================================

def reciprocal_rank_fusion(results_list: list[list[dict]], k: int = 60) -> list[dict]:
    """
    Reciprocal Rank Fusion (RRF) — do ranked lists ko combine karta hai.

    Formula: score = sum(1 / (rank + k)) for each list

    🍕 Analogy: Soch do judges hain — ek taste (semantic) dekhta hai,
    ek presentation (keyword) dekhta hai. RRF dono ki ranking combine
    karke ek final ranking banata hai. K=60 is standard.
    """
    # Track scores for each chunk (by text as key)
    fused_scores = {}  # text → {"score": float, "chunk": dict}

    for results in results_list:
        for rank, chunk in enumerate(results):
            text = chunk["text"]
            rrf_score = 1.0 / (rank + k)

            if text in fused_scores:
                fused_scores[text]["score"] += rrf_score
            else:
                fused_scores[text] = {
                    "score": rrf_score,
                    "chunk": chunk
                }

    # Sort by fused score (highest first)
    sorted_results = sorted(
        fused_scores.values(),
        key=lambda x: x["score"],
        reverse=True
    )

    # Return chunks with updated scores
    final = []
    for item in sorted_results:
        chunk = item["chunk"].copy()
        chunk["score"] = item["score"]
        final.append(chunk)

    return final


def hybrid_search(query: str, document_id: str, top_k: int = 5) -> list[dict]:
    """
    MAIN SEARCH — BM25 + Semantic combined with RRF.

    Steps:
    1. BM25 se top-10 nikalo (keyword match)
    2. ChromaDB se top-10 nikalo (semantic match)
    3. RRF se combine karo
    4. (Optional) Cohere Rerank se re-score karo
    5. Top-k return karo

    Yeh function query.py ka CORE hai.
    """
    print(f"[SEARCH] Hybrid search for: '{query[:50]}...' in doc: {document_id}")

    # Step 1: BM25 keyword search
    bm25_results = bm25_search(query, document_id, top_k=10)
    print(f"[SEARCH] BM25 returned {len(bm25_results)} results")

    # Step 2: Semantic search
    semantic_results = semantic_search(query, document_id, top_k=10)
    print(f"[SEARCH] Semantic returned {len(semantic_results)} results")

    # Step 3: Combine with RRF
    if bm25_results and semantic_results:
        combined = reciprocal_rank_fusion([bm25_results, semantic_results])
    elif semantic_results:
        combined = semantic_results
    elif bm25_results:
        combined = bm25_results
    else:
        print("[SEARCH] No results found!")
        return []

    print(f"[SEARCH] Combined: {len(combined)} unique chunks")

    # Step 4: Cohere Rerank (optional — agar API key hai toh)
    if COHERE_API_KEY:
        try:
            combined = cohere_rerank(query, combined, top_k=top_k)
            print(f"[SEARCH] Reranked to top {len(combined)}")
        except Exception as e:
            print(f"[SEARCH] Rerank failed (using RRF results): {e}")
            combined = combined[:top_k]
    else:
        print("[SEARCH] No Cohere key — skipping rerank, using RRF results")
        combined = combined[:top_k]

    return combined


# ============================================
# 7. Cohere Reranking (Optional but Powerful)
# ============================================

def cohere_rerank(query: str, chunks: list[dict], top_k: int = 5) -> list[dict]:
    """
    Cohere Rerank — combined results ko re-score karta hai.

    RRF ke baad bhi kuch irrelevant chunks aa sakte hain.
    Cohere ek aur baar dekhta hai: "yeh chunk ACTUALLY relevant hai kya?"
    Improves answer quality by 20-30%.

    Free tier: 1000 calls/month — development ke liye kaafi hai.
    """
    import cohere

    co = cohere.Client(api_key=COHERE_API_KEY)

    # Cohere ko chunks ka text do
    texts = [chunk["text"] for chunk in chunks]

    response = co.rerank(
        model="rerank-v3.5",
        query=query,
        documents=texts,
        top_n=top_k
    )

    # Reranked results build karo
    reranked = []
    for result in response.results:
        chunk = chunks[result.index].copy()
        chunk["score"] = result.relevance_score
        reranked.append(chunk)

    return reranked


# ============================================
# 8. Build Context for LLM
# ============================================

def build_context(chunks: list[dict]) -> str:
    """
    Retrieved chunks ko ek formatted string mein banata hai
    jo LLM ko diya jaayega.

    Each chunk ke saath page number aur section title bhi jaata hai
    taaki LLM citation de sake.
    """
    context_parts = []

    for i, chunk in enumerate(chunks):
        meta = chunk["metadata"]
        page = meta.get("page_number", "?")
        section = meta.get("section_title", "")
        clause = meta.get("clause_number", "")

        header = f"[Source {i+1} | Page {page}"
        if section:
            header += f" | {section}"
        if clause:
            header += f" | Clause {clause}"
        header += "]"

        context_parts.append(f"{header}\n{chunk['text']}")

    return "\n\n---\n\n".join(context_parts)


def build_chat_history_text(chat_history: list[dict]) -> str:
    """Chat history ko text format mein convert karta hai"""
    if not chat_history:
        return "No previous conversation."

    parts = []
    for msg in chat_history[-6:]:  # Last 6 messages tak hi history rakho
        role = msg.get("role", "user")
        content = msg.get("content", "")
        parts.append(f"{role.upper()}: {content}")

    return "\n".join(parts)


# ============================================
# 9. Determine Confidence
# ============================================

def calculate_confidence(chunks: list[dict]) -> tuple[str, float]:
    """
    Answer ki confidence calculate karta hai based on:
    - Top chunk ka score
    - Kitne chunks relevant mile

    High: top score > 0.7 and 3+ good chunks
    Medium: top score > 0.4 or 2+ chunks
    Low: below that
    """
    if not chunks:
        return "low", 0.0

    top_score = chunks[0].get("score", 0.0)

    # Normalize score (different sources give different ranges)
    if top_score > 1.0:
        top_score = min(top_score / 2.0, 1.0)

    good_chunks = sum(1 for c in chunks if c.get("score", 0) > 0.3)

    if top_score > 0.7 and good_chunks >= 3:
        return "high", round(top_score, 2)
    elif top_score > 0.4 or good_chunks >= 2:
        return "medium", round(top_score, 2)
    else:
        return "low", round(top_score, 2)


# ============================================
# 10. MAIN QUERY FUNCTION
# ============================================

def query_document(
    question: str,
    document_id: str,
    chat_history: list[dict] = None
) -> dict:
    """
    MAIN FUNCTION — Sawaal aaya, jawab do!

    🍕 Full Order Process:
    1. Document mein search karo (hybrid: BM25 + semantic)
    2. Best chunks select karo (rerank)
    3. Context banao (chunks + page numbers)
    4. LLM se answer generate karo (with citation prompt)
    5. Confidence calculate karo
    6. Structured response return karo

    Input:
      - question: User ka sawaal ("Notice period kitna hai?")
      - document_id: Kis document mein dekhna hai
      - chat_history: Pichli baatein (follow-up ke liye)

    Output: {
      "answer": "Notice period 90 din hai...",
      "sources": [{"text": "...", "page_number": 12, ...}],
      "confidence": "high",
      "confidence_score": 0.94
    }
    """
    print(f"\n{'='*60}")
    print(f"[QUERY] Question: {question}")
    print(f"[QUERY] Document: {document_id}")
    print(f"{'='*60}")

    # Step 1: Hybrid Search
    chunks = hybrid_search(question, document_id, top_k=5)

    if not chunks:
        return {
            "answer": "Is document mein aapke sawaal se related koi information nahi mili. "
                      "Kripya apna sawaal dobaara check karein ya alag tarike se poochein.",
            "sources": [],
            "confidence": "low",
            "confidence_score": 0.0
        }

    # Step 2: Build context for LLM
    context = build_context(chunks)
    chat_history_text = build_chat_history_text(chat_history or [])

    # Step 3: Build the prompt
    prompt = QUERY_SYSTEM_PROMPT.format(
        context=context,
        chat_history=chat_history_text,
        question=question
    )

    # Step 4: Generate answer with LLM
    print("[QUERY] Generating answer with LLM...")
    llm = get_llm()
    response = llm.invoke(prompt)
    answer = response.content
    print(f"[QUERY] Answer generated ({len(answer)} chars)")

    # Step 5: Calculate confidence
    confidence, confidence_score = calculate_confidence(chunks)

    # Step 6: Build sources list
    sources = []
    for chunk in chunks:
        meta = chunk["metadata"]
        sources.append({
            "text": chunk["text"][:300],  # Truncate long chunks for response
            "page_number": meta.get("page_number", 0),
            "section_title": meta.get("section_title", ""),
            "clause_number": meta.get("clause_number", ""),
            "relevance_score": round(chunk.get("score", 0.0), 4)
        })

    return {
        "answer": answer,
        "sources": sources,
        "confidence": confidence,
        "confidence_score": confidence_score
    }


# ============================================
# Quick Test
# ============================================

if __name__ == "__main__":
    """
    Test karne ke liye:
    1. Pehle ingest.py se ek document ingest karo
    2. Phir: python query.py
    """
    import json

    test_doc_id = "test_doc_001"
    test_question = "What is the notice period for termination?"

    print(f"Testing query: '{test_question}'")
    print(f"Document: {test_doc_id}")
    print()

    try:
        result = query_document(test_question, test_doc_id)
        print("\n✅ RESULT:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nMake sure:")
        print("1. You have ingested a document first (python ingest.py)")
        print("2. GROQ_API_KEY is set in .env file")
        print("3. Document ID matches what you ingested")
