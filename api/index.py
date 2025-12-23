"""
Vercel Serverless Function Entry Point for FastAPI
"""

from app.main import app

# Vercel Python runtime automatically detects FastAPI/ASGI apps
# Export the app instance - Vercel will handle routing
__all__ = ["app"]

