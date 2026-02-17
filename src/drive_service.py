"""Google Drive service for uploading, downloading, and listing files."""

import io
import os
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from google.oauth2 import service_account

from src.config import GOOGLE_SERVICE_ACCOUNT_FILE, SOURCE_FOLDER_ID, DESTINATION_FOLDER_ID

SCOPES = ["https://www.googleapis.com/auth/drive"]


def get_drive_service():
    """Authenticate and return a Google Drive API service instance."""
    credentials = service_account.Credentials.from_service_account_file(
        GOOGLE_SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    return build("drive", "v3", credentials=credentials)


def list_pdf_files(service, folder_id: str) -> list[dict]:
    """List all PDF files in a Google Drive folder."""
    query = f"'{folder_id}' in parents and mimeType='application/pdf' and trashed=false"
    results = service.files().list(
        q=query,
        fields="files(id, name, modifiedTime)",
        orderBy="modifiedTime desc",
    ).execute()
    return results.get("files", [])


def download_file(service, file_id: str, destination_path: str) -> str:
    """Download a file from Google Drive to a local path."""
    request = service.files().get_media(fileId=file_id)
    with open(destination_path, "wb") as f:
        downloader = MediaIoBaseDownload(f, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            if status:
                print(f"  Download progress: {int(status.progress() * 100)}%")
    return destination_path


def upload_file(service, local_path: str, folder_id: str, filename: str = None) -> dict:
    """Upload a file to a Google Drive folder. Returns the file metadata."""
    if filename is None:
        filename = os.path.basename(local_path)

    file_metadata = {
        "name": filename,
        "parents": [folder_id],
    }

    # Determine MIME type
    if local_path.endswith(".pdf"):
        mime_type = "application/pdf"
    else:
        mime_type = "application/octet-stream"

    media = MediaFileUpload(local_path, mimetype=mime_type, resumable=True)
    file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id, name, webViewLink",
    ).execute()

    print(f"  Uploaded: {file.get('name')} (ID: {file.get('id')})")
    return file


def file_exists_in_folder(service, folder_id: str, filename: str) -> bool:
    """Check if a file with the given name already exists in the folder."""
    query = (
        f"'{folder_id}' in parents and name='{filename}' and trashed=false"
    )
    results = service.files().list(q=query, fields="files(id)").execute()
    return len(results.get("files", [])) > 0
