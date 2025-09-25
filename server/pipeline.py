import os
import time
from typing import Dict
from dotenv import load_dotenv
from openai import OpenAI
from pypdf import PdfReader

# --- CONFIGURATION ---
# The cSpell warning for "dotenv" is a spell-checker issue in your editor,
# not a code error. You can add "dotenv" to your editor's dictionary.
# The code itself is correct.
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# --- AI PIPELINE FUNCTION ---
def process_document(task_id: str, file_path: str, tasks_db: Dict):
    """
    Reads a PDF, sends its text to OpenAI for summarization,
    and updates the task in the database.
    """
    print(f"Starting AI pipeline for task: {task_id}")
    task = tasks_db.get(task_id)
    if not task:
        print(f"Error: Task {task_id} not found in database.")
        return

    try:
        # 1. Read text from the PDF file
        print(f"Reading text from {file_path}...")
        reader = PdfReader(file_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        
        if not text:
            raise ValueError("Could not extract text from PDF.")

        # 2. Call OpenAI API for summarization
        print("Sending text to OpenAI for summarization...")
        prompt = f"Summarize the following document in a concise paragraph. Then, provide 3-5 key bullet points. Document content:\n\n{text}"
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        
        summary = response.choices[0].message.content or "No summary generated."
        print("Summary received from OpenAI.")

        # 3. Update the task with the results (and mock data for other fields)
        task["summary"] = summary
        task["status"] = "completed"
        task["keyPoints"] = ["Review financial statements.", "Check for compliance issues."] # Mock data
        task["departmentSuggestion"] = {"department": "Finance", "confidence": 0.88, "reasoning": "Contains financial data."} # Mock data

    except Exception as e:
        print(f"Error during AI processing for task {task_id}: {e}")
        task["status"] = "failed"
        task["summary"] = f"An error occurred during processing: {e}"
    finally:
        # 4. Clean up the temporary file
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"Cleaned up temporary file: {file_path}")

    print(f"Processing complete for task: {task_id}")
