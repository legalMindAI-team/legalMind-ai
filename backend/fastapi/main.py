from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl
from fastapi.middleware.cors import CORSMiddleware 
from graph import rag_app

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, change this to your Node server IP
    allow_methods=["*"],
    allow_headers=["*"],
)


class IngestRequest(BaseModel):
    document_id: str
    file_url: HttpUrl


@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.post("/ai/ingest")
def ingest_document(payload: IngestRequest):
    try:
        # 1. Inputs ko yahan define karna zaroori hai
        graph_inputs = {
            "document_id": payload.document_id,
            "file_url": str(payload.file_url)
        }
        
        print("Bhai, Graph start ho raha hai...") 
        
        # 2. graph_inputs pass kijiye (inputs nahi)
        result = rag_app.invoke(graph_inputs) 
        
        print("Bhai, Graph khatam ho gaya!")

        return {
            "ok": True,
            "message": "AI Processing Complete",
            "chunks_count": len(result.get("chunks", [])),
            "status": result.get("status")
        }
        
    except Exception as exc:
        print(f"ERROR: {exc}") # Isse terminal mein error dikhega
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {exc}")


@app.get("/items/{item_id}")
def read_item(item_id: int, q: str | None = None):
    return {"item_id": item_id, "q": q}