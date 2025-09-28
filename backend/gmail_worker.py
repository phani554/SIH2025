# gmail_worker.py
import os, time, base64, hashlib
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
import requests
from datetime import datetime
from email.utils import parsedate_to_datetime

from db import get_all_users, get_user_by_id, save_processed_message, processed_sha_exists, processed_message_exists
from utils import save_bytes_to_file, sha256_bytes, ensure_upload_dir
from dotenv import load_dotenv
load_dotenv()

CLIENT_ID = os.getenv("GCLIENT_ID")
CLIENT_SECRET = os.getenv("GCLIENT_SECRET")
TOKEN_URI = "https://oauth2.googleapis.com/token"
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./uploads")
LABEL_NAME = os.getenv("KMRL_LABEL_NAME", "KMRL_Processed")
SELF_EMAIL = "vksmp07@gmail.com"

ensure_upload_dir(UPLOAD_DIR)

def build_service_from_user_record(user_rec):
    user_id, email, refresh_token, access_token, token_expiry = user_rec
    creds = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri=TOKEN_URI,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        scopes=["https://www.googleapis.com/auth/gmail.modify"]
    )
    if not creds.valid and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    
    return build("gmail", "v1", credentials=creds)

def ensure_label(service):
    """Ensure LABEL_NAME exists in the user's Gmail labels. Return label id."""
    try:
        labels_resp = service.users().labels().list(userId="me").execute()
        labels = labels_resp.get("labels", [])
        for l in labels:
            if l.get("name") == LABEL_NAME:
                return l.get("id")
        # create
        body = {"name": LABEL_NAME, "labelListVisibility": "labelShow", "messageListVisibility": "show"}
        lab = service.users().labels().create(userId='me', body=body).execute()
        return lab.get("id")
    except Exception as e:
        print("Error ensuring label:", e)
        return None

def get_message_details(service, message_id):
    """Get full message details including subject, timestamp, and body"""
    try:
        message = service.users().messages().get(userId="me", id=message_id, format="full").execute()
        headers = message.get("payload", {}).get("headers", [])
        
        # Extract headers
        subject = next((h["value"] for h in headers if h["name"].lower() == "subject"), "No Subject")
        date_str = next((h["value"] for h in headers if h["name"].lower() == "date"), None)
        from_email = next((h["value"] for h in headers if h["name"].lower() == "from"), "")
        
        if date_str:
            timestamp = parsedate_to_datetime(date_str).isoformat()
        else:
            timestamp = datetime.fromtimestamp(int(message["internalDate"])/1000).isoformat()

        # Extract body
        body = ""
        if "parts" in message.get("payload", {}):
            for part in message["payload"]["parts"]:
                if part.get("mimeType") == "text/plain":
                    body_data = part.get("body", {}).get("data", "")
                    if body_data:
                        body += base64.urlsafe_b64decode(body_data.encode("utf-8")).decode("utf-8")

        return {
            "subject": subject,
            "timestamp": timestamp,
            "from": from_email,
            "body": body,
            "snippet": message.get("snippet", "")
        }
    except Exception as e:
        print(f"Error getting message details: {e}")
        return None

def is_document(filename, mime_type):
    """Check if the file is a document (not an image)"""
    document_extensions = {'.pdf', '.doc', '.docx', '.txt', '.rtf', '.odt', '.xls', '.xlsx', '.ppt', '.pptx'}
    ignored_types = {'image/jpeg', 'image/png', 'image/gif', 'image/bmp', 'image/webp'}
    
    return (any(filename.lower().endswith(ext) for ext in document_extensions) or 
            (mime_type and not any(ignored in mime_type.lower() for ignored in ignored_types)))

def walk_parts(parts, acc):
    """Recursively collect parts that look like document attachments"""
    if not parts:
        return acc
    for p in parts:
        filename = p.get("filename")
        mimeType = p.get("mimeType")
        body = p.get("body", {})
        
        if filename and body.get("attachmentId") and is_document(filename, mimeType):
            acc.append((filename, body["attachmentId"], mimeType))
        if p.get("parts"):
            walk_parts(p.get("parts"), acc)
    return acc

def download_attachment_bytes(service, message_id, attachment_id):
    att = service.users().messages().attachments().get(userId="me", messageId=message_id, id=attachment_id).execute()
    data = att.get("data")
    if not data:
        return None
    return base64.urlsafe_b64decode(data.encode("utf-8"))

def process_user(user_rec):
    """Process user's Gmail messages and store documents"""
    user_id = user_rec[0]
    print("Processing user:", user_id)
    
    service = build_service_from_user_record(user_rec)
    if not service:
        print("Could not build service for user", user_id)
        return

    label_id = ensure_label(service)

    try:
        # Query for unread messages from LeetCode
        query = f'from:{SELF_EMAIL} has:attachment is:unread'
        resp = service.users().messages().list(userId='me', q=query, maxResults=50).execute()
    except Exception as e:
        print("Error listing messages for user", user_id, ":", e)
        return

    messages = resp.get("messages", [])
    print(f"Found {len(messages)} messages from yourself with attachments for {user_id}")
    
    for m in messages:
        mid = m.get("id")
        if processed_message_exists(mid):
            continue
            
        try:
            message = service.users().messages().get(userId="me", id=mid, format="full").execute()
            message_details = get_message_details(service, mid)
            
            if not message_details or SELF_EMAIL not in message_details["from"]:
                continue
                
            parts = []
            if "parts" in message.get("payload", {}):
                walk_parts(message["payload"]["parts"], parts)
            
            for filename, attachment_id, mime_type in parts:
                att_bytes = download_attachment_bytes(service, mid, attachment_id)
                if not att_bytes:
                    continue
                    
                sha = sha256_bytes(att_bytes)
                if processed_sha_exists(sha):
                    continue
                
                # Create a folder with email timestamp
                email_date = datetime.fromisoformat(message_details["timestamp"]).strftime("%Y%m%d_%H%M%S")
                folder_name = f"self_{email_date}"
                folder_path = os.path.join(UPLOAD_DIR, folder_name)
                ensure_upload_dir(folder_path)
                
                # Save file with metadata
                saved_path = save_bytes_to_file(folder_path, filename, att_bytes)
                
                # Save email details
                email_info = f"""
Email Details:
From: {message_details['from']}
Date: {message_details['timestamp']}
Subject: {message_details['subject']}

Body:
{message_details['body']}
"""
                with open(os.path.join(folder_path, "email_details.txt"), "w", encoding="utf-8") as f:
                    f.write(email_info)
                
                save_processed_message(mid, attachment_id, sha, saved_path)
                
                # Add label to mark as processed
                if label_id:
                    service.users().messages().modify(
                        userId="me",
                        id=mid,
                        body={"addLabelIds": [label_id]}
                    ).execute()
                    
            print(f"Processed message {mid} - Subject: {message_details['subject']}")
            
        except Exception as e:
            print(f"Error processing message {mid}: {e}")

def main_loop_once():
    users = get_all_users()
    for u in users:
        process_user(u)

if __name__ == "__main__":
    print("Gmail worker starting. Will run once and exit. For periodic behavior, run this in cron or use a process manager.")
    main_loop_once()
    print("Worker done.")