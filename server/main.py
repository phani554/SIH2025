import os
import uuid
from datetime import datetime, timezone
from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict
import uvicorn

from pipeline import process_document

app = FastAPI()

# --- In-Memory Storage ---
# This dictionary acts as our temporary, in-memory database.
tasks_db: Dict[str, Dict] = {}


# --- CORS Configuration ---
origins = [
    "http://localhost:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    """Create a mock task when the server starts up for demonstration."""
    print("Creating initial mock data...")
    task_id = "example-task-1"
    if task_id not in tasks_db:
        tasks_db[task_id] = {
            "id": task_id,
            "filename": "example_invoice.pdf",
            "status": "completed",
            "summary": "This is a sample summary for an initial invoice document.",
            "keyPoints": ["Initial amount due: $1500", "Vendor: Acme Corp"],
            "departmentSuggestion": {"department": "Finance", "confidence": 0.95, "reasoning": "Contains financial keywords."},
            "timestamp": datetime.now(timezone.utc).isoformat()  # Added timestamp for consistency
        }

@app.get("/tasks", response_model=List[Dict])
def get_all_tasks():
    """Endpoint to get all tasks."""
    return list(tasks_db.values())

@app.post("/upload")
async def upload_documents(background_tasks: BackgroundTasks, files: List[UploadFile] = File(...)):
    """
    Endpoint to upload one or more new documents and start processing for each.
    Handles multiple files by iterating through them.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files were sent.")

    upload_folder = "uploads"
    os.makedirs(upload_folder, exist_ok=True)
    
    processed_files = []

    for file in files:
        if not file.filename:
            continue

        file_extension = os.path.splitext(file.filename)[1]
        # Expanded supported file types, align with frontend `accept` prop if needed
        if file_extension.lower() not in [".pdf", ".doc", ".docx", ".txt", ".md"]:
            print(f"Skipping unsupported file: {file.filename}")
            continue

        task_id = str(uuid.uuid4())
        file_path = os.path.join(upload_folder, f"{task_id}_{file.filename}")

        try:
            with open(file_path, "wb") as buffer:
                buffer.write(await file.read())

            # Create the initial task record
            tasks_db[task_id] = {
                "id": task_id,
                "filename": file.filename,
                "status": "processing",
                "timestamp": datetime.now(timezone.utc).isoformat() # CRITICAL: Add timestamp on creation
            }
            # Add the processing task to the background
            background_tasks.add_task(process_document, task_id, file_path, tasks_db)
            processed_files.append(file.filename)
        
        except Exception as e:
            print(f"Failed to process file {file.filename}: {e}")


    return {"message": f"{len(processed_files)} file(s) uploaded successfully, processing started."}

# To run this app: uvicorn main:app --reload
