import requests
import json
import time

# Wait for FastAPI server to start
time.sleep(5)

# A real Legal Document: Non-Disclosure Agreement from SEC Archives
sample_pdf_url = "https://www.sec.gov/Archives/edgar/data/1029199/000102919921000003/exhibit101nda.pdf"
document_id = "nda_sample_123"

url = "http://localhost:8001/ai/ingest"
payload = {
    "document_id": document_id,
    "file_url": sample_pdf_url
}
headers = {
    "Content-Type": "application/json"
}

print(f"Testing ingestion with Real Contract PDF URL:\n{sample_pdf_url}")

try:
    response = requests.post(url, json=payload, headers=headers)
    print("\nAPI Status Code:", response.status_code)
    print("\nAPI Response:")
    print(json.dumps(response.json(), indent=2))
except requests.exceptions.ConnectionError:
    print("Error: FastAPI Server is not running. Please start it with 'python main.py'")

# Also let's test a simple query!
if response.status_code == 200:
    print("\n--- NOW TESTING QUERY ENGINE ---")
    query_url = "http://localhost:8001/ai/query"
    query_payload = {
        "document_id": document_id,
        "question": "What is the term or duration of this NDA? Is there any specific time frame?",
        "chat_history": []
    }
    
    print("Testing question:", query_payload["question"])
    
    q_response = requests.post(query_url, json=query_payload, headers=headers)
    print("\nQuery API Status Code:", q_response.status_code)
    if q_response.status_code == 200:
        data = q_response.json()
        print("\nAnswer Generator (LLM) Response:")
        print(data.get("answer", "No answer found"))
        print("\nSources Referenced:")
        for s in data.get("sources", []):
            print(f"- Page {s['page_number']}: {s['text'][:100]}...")
    else:
        print("\nQuery failed:", q_response.text)

