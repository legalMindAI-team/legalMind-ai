"""
app/main.py — FastAPI Application Setup
Is file me server config aur routing hoti hai.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import router as api_router

def create_app() -> FastAPI:
    app = FastAPI(
        title="LegalMind AI Service",
        description="AI Engine for legal document analysis — modular structure built by Ritik",
        version="1.0.0",
    )

    # CORS settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Health check endpoint
    @app.get("/")
    def health_check():
        return {
            "service": "LegalMind AI Engine",
            "status": "online",
            "version": "1.0.0"
        }

    # Include all API routes from app/api.py
    # Purane main.py me `/ai/ingest` the, toh hum yahan prefix de denge `/ai`
    app.include_router(api_router, prefix="/ai", tags=["AI Engine"])

    return app

app = create_app()
