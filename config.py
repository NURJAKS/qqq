import os
from typing import List
from pydantic import BaseSettings, validator
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Settings(BaseSettings):
    # Application Settings
    app_name: str = "Alumni Club Connect"
    debug: bool = False
    environment: str = "production"
    
    # Security Settings
    secret_key: str = "your_super_secret_key_here_minimum_32_characters_long"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    password_min_length: int = 8
    
    # Database Configuration
    database_url: str = "sqlite:///./data/alumni_club.db"
    db_echo: bool = False
    
    # Email Configuration
    smtp_server: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_use_tls: bool = True
    email_user: str = ""
    email_password: str = ""
    email_from_name: str = "Alumni Club Connect"
    
    # File Upload Settings
    max_file_size_mb: int = 10
    allowed_image_extensions: List[str] = ["png", "jpg", "jpeg", "gif"]
    
    # Rate Limiting
    rate_limit_requests: int = 100
    rate_limit_window_minutes: int = 15
    
    # CORS Settings
    allowed_origins: List[str] = ["http://localhost:8501", "http://127.0.0.1:8501"]
    
    # Certificate Settings
    certificate_hours_threshold: int = 300
    auto_send_certificates: bool = True
    
    @validator('secret_key')
    def validate_secret_key(cls, v):
        if len(v) < 32:
            raise ValueError('Secret key must be at least 32 characters long')
        return v
    
    @validator('password_min_length')
    def validate_password_length(cls, v):
        if v < 8:
            raise ValueError('Password minimum length must be at least 8')
        return v
    
    @validator('allowed_origins')
    def validate_origins(cls, v):
        if isinstance(v, str):
            return v.split(',')
        return v
    
    @validator('allowed_image_extensions')
    def validate_extensions(cls, v):
        if isinstance(v, str):
            return v.split(',')
        return v
    
    class Config:
        env_file = ".env"
        case_sensitive = False

# Create settings instance
settings = Settings()

# Create data directory if it doesn't exist
os.makedirs(os.path.dirname(settings.database_url.replace("sqlite:///", "")), exist_ok=True)
