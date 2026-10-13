
import re
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timedelta
from typing import Tuple, Optional
from pathlib import Path
import os

try:
    import magic
    HAS_MAGIC = True
except ImportError:
    HAS_MAGIC = False
    print("⚠️  python-magic not installed. File validation will be limited.")

# ============================================================
# LOGGING
# ============================================================

def setup_logging():
    """Configure application logging"""
    os.makedirs("logs", exist_ok=True)
    
    logger = logging.getLogger("chat_app")
    logger.setLevel(logging.DEBUG)
    
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(formatter)
    
    file_handler = RotatingFileHandler(
        "logs/chat_app.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    
    logger.addHandler(console)
    logger.addHandler(file_handler)
    
    return logger

logger = setup_logging()

ALLOWED_MIME_TYPES = {
    "image/jpeg", "image/png", "image/gif", "image/webp", "image/svg+xml",
    "application/pdf", "text/plain", "text/csv", "application/json",
    "video/mp4", "audio/mpeg", "audio/wav",
    "application/zip", "application/x-zip-compressed",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document", # .docx
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",      # .xlsx
    "application/vnd.openxmlformats-officedocument.presentationml.presentation" # .pptx
}

def validate_file_content(contents: bytes, filename: str) -> tuple[bool, str, str]:
    """
    Validate file by inspecting actual content, not just extension.
    
    This prevents attacks like:
    - Renaming malware.exe to innocent.jpg
    - Uploading PHP shells as images
    - Double extensions (image.jpg.exe)
    
    Args:
        contents: Raw file bytes
        filename: Original filename
        
    Returns:
        (is_valid, detected_mime_type, error_message)
    """
    if not HAS_MAGIC:
        logger.warning("python-magic not available, using extension-based validation")
        ext = Path(filename).suffix.lower()
        ext_to_mime = {
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".png": "image/png", ".gif": "image/gif",
            ".webp": "image/webp", ".pdf": "application/pdf",
            ".txt": "text/plain", ".mp4": "video/mp4",
            ".mp3": "audio/mpeg", ".zip": "application/zip",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            ".json": "application/json",
            ".csv": "text/csv",
            ".wav": "audio/wav",
        }
        guessed_mime = ext_to_mime.get(ext, "application/octet-stream")
        if guessed_mime not in ALLOWED_MIME_TYPES and guessed_mime != "application/octet-stream":
            return False, guessed_mime, f"File type not allowed"
        return True, guessed_mime, ""
    
    # Normal validation with python-magic
    try:
        detected_mime = magic.from_buffer(contents, mime=True)
        logger.debug(f"File '{filename}' detected as: {detected_mime}")
        
        if detected_mime not in ALLOWED_MIME_TYPES:
            logger.warning(f"Rejected '{filename}': type '{detected_mime}' not allowed")
            return False, detected_mime, f"File type '{detected_mime}' not allowed"
        
        return True, detected_mime, ""
        
    except Exception as e:
        logger.error(f"File validation error for '{filename}': {e}")
        return False, "unknown", f"Could not validate file: {str(e)}"