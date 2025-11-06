"""
Application configuration and environment variables
"""

from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from typing import Optional
import os
from pathlib import Path
from dotenv import load_dotenv

# Get the project root directory (parent of 'app' folder)
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env file from project root explicitly
env_path = BASE_DIR / ".env"
load_dotenv(dotenv_path=env_path, override=True)


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # API Configuration
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "Skill Capital AI Learning Platform"
    VERSION: str = "1.0.0"
    
    # Supabase Configuration
    SUPABASE_URL: str = "https://your-project.supabase.co"
    SUPABASE_KEY: str = "your-supabase-anon-key"
    SUPABASE_SERVICE_KEY: Optional[str] = None
    
    # OpenAI Configuration
    OPENAI_API_KEY: str = "your-openai-api-key"
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    
    # Vimeo Configuration (Optional)
    VIMEO_ACCESS_TOKEN: Optional[str] = None
    
    # JWT Configuration
    JWT_SECRET: Optional[str] = None
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24
    
    # PDF Configuration
    PDF_STORAGE_BUCKET: str = "assessment-reports"
    PDF_REPORT_TEMPLATE: str = "default"
    
    # LangChain Configuration
    LANGCHAIN_TRACING_V2: bool = False
    LANGCHAIN_ENDPOINT: Optional[str] = None
    LANGCHAIN_API_KEY: Optional[str] = None
    
    # Application Settings
    DEBUG: bool = True  # Default to True for development (set to False for production)
    # FIX 2: Add frontend port (5173) to CORS origins to allow frontend requests
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173,http://localhost:5174,http://localhost:5176,http://localhost:8000,http://127.0.0.1:5173,http://127.0.0.1:5174,http://127.0.0.1:5176,https://skillcapital.ai"
    
    # Question Generation Defaults
    DEFAULT_QUESTION_COUNT: int = 10
    DEFAULT_DIFFICULTY: str = "medium"
    DEFAULT_QUESTION_TYPE: str = "mcq"
    
    @field_validator('CORS_ORIGINS')
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse comma-separated CORS origins string into list"""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(',') if origin.strip()]
        return v
    
    @property
    def cors_origins_list(self) -> list[str]:
        """Get CORS origins as a list"""
        if isinstance(self.CORS_ORIGINS, str):
            return [origin.strip() for origin in self.CORS_ORIGINS.split(',') if origin.strip()]
        return self.CORS_ORIGINS if isinstance(self.CORS_ORIGINS, list) else []
    
    model_config = {
        "env_file": str(BASE_DIR / ".env"),  # Use absolute path to ensure it's found
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore"  # Ignore extra fields in .env file (like FRONTEND_URL)
    }


# Global settings instance
try:
    settings = Settings()
    
    # Validate and warn about placeholder values
    import warnings
    if settings.SUPABASE_URL == "https://your-project.supabase.co" or "your-project" in settings.SUPABASE_URL:
        warnings.warn(
            "[WARN] SUPABASE_URL is not configured. Please set it in your .env file.",
            UserWarning
        )
    if settings.SUPABASE_KEY == "your-supabase-anon-key" or "your-supabase" in settings.SUPABASE_KEY:
        warnings.warn(
            "[WARN] SUPABASE_KEY is not configured. Please set it in your .env file.",
            UserWarning
        )
    if settings.OPENAI_API_KEY == "your-openai-api-key" or "your-openai" in settings.OPENAI_API_KEY:
        warnings.warn(
            "[WARN] OPENAI_API_KEY is not configured. Please set it in your .env file.",
            UserWarning
        )
except Exception as e:
    import sys
    print(f"[ERROR] Error loading configuration: {e}", file=sys.stderr)
    print("Please check your .env file or create one with required variables.", file=sys.stderr)
    raise

