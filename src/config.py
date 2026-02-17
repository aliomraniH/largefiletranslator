import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
SOURCE_FOLDER_ID = os.getenv("SOURCE_FOLDER_ID", "1XBs5PdhcUSgFr2oBsrpt5UQgwHkfefAo")
DESTINATION_FOLDER_ID = os.getenv("DESTINATION_FOLDER_ID", "1kUsgJwhunnz6V85blXnyBKAvKKTRnU0c")
GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json")
TARGET_LANGUAGE = os.getenv("TARGET_LANGUAGE", "English")
SOURCE_LANGUAGE = os.getenv("SOURCE_LANGUAGE", "French")

# Claude model to use
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")

# Temp directory for downloaded/generated files
TEMP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "temp")
os.makedirs(TEMP_DIR, exist_ok=True)
