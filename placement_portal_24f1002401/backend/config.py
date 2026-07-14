import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

SECRET_KEY = os.environ.get("PPA_SECRET_KEY", "ppa-dev-secret-change-in-production")
JWT_SECRET = os.environ.get("PPA_JWT_SECRET", SECRET_KEY)
JWT_EXPIRY_HOURS = int(os.environ.get("PPA_JWT_EXPIRY_HOURS", "12"))

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
CACHE_TTL_SECONDS = int(os.environ.get("PPA_CACHE_TTL", "60"))

UPLOAD_FOLDER = BASE_DIR / "uploads" / "resumes"
EXPORT_FOLDER = BASE_DIR / "exports"
NOTIFICATIONS_FOLDER = BASE_DIR / "notifications"

# Local-demo friendly: notifications are written to files when SMTP/webhook not set
SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@ppa.com")
GCHAT_WEBHOOK_URL = os.environ.get("GCHAT_WEBHOOK_URL", "")

ALLOWED_RESUME_EXTENSIONS = {".pdf", ".doc", ".docx"}
