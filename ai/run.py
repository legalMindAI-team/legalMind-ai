import uvicorn

if __name__ == "__main__":
    # Server chalane ka naya gateway
    # Note: Ab 'app.main:app' use kar rahe hain kyuki humne code 'app/' folder me move kiya hai
    print("🚀 Starting Modular LegalMind AI Engine...")
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8001,
        reload=True
    )
