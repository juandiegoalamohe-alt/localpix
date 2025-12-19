import os

class Config:
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    STATIC_FOLDER = os.path.join(BASE_DIR, 'static')
    BRANDING_FOLDER = os.path.join(STATIC_FOLDER, 'branding')
    
    # Database
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(BASE_DIR, 'yaku_pix.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Security
    SECRET_KEY = 'yaku_park_secret_key_v1.4'
    
    # Archival / Backup
    ARCHIVE_FOLDER = os.path.join(BASE_DIR, 'archive') # Local archive
    CLOUD_BACKUP_ENABLED = False # Placeholder for future S3 integration
    
    # Yaku Logic
    WATERMARK_FILE = os.path.join(BRANDING_FOLDER, 'watermark.png')
    MAX_CONTENT_LENGTH = 64 * 1024 * 1024 # 64MB for high-res batches
