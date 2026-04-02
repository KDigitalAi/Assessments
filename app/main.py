"""
FastAPI main application entry point with improved security and error handling
"""

from fastapi import FastAPI, Request, status, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
import time
import os
import uuid
import asyncio
from pathlib import Path

from app.config import settings
from app.utils.logger import setup_logger, logger
from app.utils.error_handler import (
    global_exception_handler,
    app_exception_handler,
    http_exception_handler,
    validation_exception_handler,
    AppException
)
from app.utils.rate_limit import rate_limit_middleware
from app.utils.cache import cache

# Initialize logger BEFORE using it
# This ensures logger is properly configured before any log statements
setup_logger("skill_assessment")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    
    # Warn about placeholder credentials
    if "your-project" in settings.SUPABASE_URL or "your-supabase" in settings.SUPABASE_KEY:
        logger.warning("[WARN] Supabase credentials appear to be placeholders. Some features may not work.")
    if "your-openai" in settings.OPENAI_API_KEY:
        logger.warning("[WARN] OpenAI API key appears to be a placeholder. AI features will not work.")
    
    # Ensure default test user exists
    # NOTE: On Vercel serverless, database calls at startup can timeout
    # This is disabled for serverless deployments to prevent cold start failures
    if not os.getenv("VERCEL"):
        try:
            from app.services.profile_service import get_test_user_id
            
            get_test_user_id()
        except Exception as e:
            logger.warning(f"Error checking/creating test user: {str(e)}")
            # Don't fail startup if profile creation fails
    else:
        logger.info("Skipping test user creation on Vercel serverless (will be created on first use)")
    
    # PDF Processing Note:
    # PDF processing has been moved to a separate script to ensure fast server startup.
    # Heavy processing (PDF extraction, chunking, embedding generation, question generation)
    # should NOT run during web server startup as it causes 10-15 minute delays.
    #
    # To process PDFs, run the standalone script:
    #   python scripts/process_uploads.py
    #
    # This ensures:
    # - Fast server startup (seconds, not minutes)
    # - Separation of concerns (web server vs. background processing)
    # - Production-safe architecture
    # - No blocking operations during startup
    logger.info("FastAPI server started. PDF processing is handled by external script: python scripts/process_uploads.py")
    
    # Start cache cleanup task
    async def cache_cleanup_loop():
        while True:
            await asyncio.sleep(300)  # Run every 5 minutes
            await cache.cleanup_expired()
    
    cleanup_task = asyncio.create_task(cache_cleanup_loop())
    
    try:
        yield
    except asyncio.CancelledError:
        # Handle cancellation during hot reload gracefully
        # This is expected when uvicorn reloads on file changes
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass
        # Don't re-raise - allow graceful shutdown during reload
    
    # Shutdown
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    


# Create FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="""
    Skill Assessment Builder API
    
    An AI-assisted platform for creating, delivering, and evaluating skill assessments.
    
    Features:
    - AI-powered question generation using LangChain and OpenAI
    - Automated scoring for MCQ and descriptive answers
    - PDF report generation
    - Supabase integration for data storage
    """,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS Middleware - Configured for Edify frontend integration
# CORS ENABLED: Edify frontend integration
is_localhost = os.getenv("HOST", "127.0.0.1") in ("127.0.0.1", "localhost", "0.0.0.0")
is_vercel = os.getenv("VERCEL") == "1" or "vercel.app" in os.getenv("VERCEL_URL", "")
debug_mode = (settings.DEBUG or os.getenv("DEBUG", "True").lower() in ("true", "1", "yes") or is_localhost) and not is_vercel

# Edify frontend domains
EDIFY_FRONTEND_ORIGINS = [
    "https://edify.com",
    "https://www.edify.com",
    "https://app.edify.com",  # If Edify uses app subdomain
    "http://localhost:3000",  # Local development
    "http://localhost:5173",  # Vite dev server
    "http://localhost:8080",
    "https://enterprise.digitaledify.ai",
    "https://edify-enterprise-web-app-git-dev-tech-kdigitalais-projects.vercel.app/",  # Common dev port
]

if debug_mode or is_localhost:
    # Development: Allow all origins for local testing
    cors_origins = ["*"]
    cors_allow_credentials = False
else:
    # Production: Only allow Edify domains
    cors_origins = EDIFY_FRONTEND_ORIGINS
    cors_allow_credentials = True

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,  # Allow all for local development, specific origins for production
    allow_credentials=cors_allow_credentials,  # False when using ["*"], True for specific origins
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request ID and timing middleware
@app.middleware("http")
async def request_id_and_timing_middleware(request: Request, call_next):
    """Add request ID and track processing time"""
    # Generate request ID
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    
    # Add request ID to logger context
    start_time = time.time()
    
    # Process request
    response = await call_next(request)
    
    # Calculate processing time
    process_time = (time.time() - start_time) * 1000  # Convert to milliseconds
    
    # Add headers
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = f"{process_time:.2f}ms"
    
    # Log only errors
    if response.status_code >= 400:
        logger.error(
            f"{request.method} {request.url.path} - {response.status_code}",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": process_time
            }
        )
    
    return response


# Rate limiting middleware
@app.middleware("http")
async def rate_limit_middleware_wrapper(request: Request, call_next):
    """Apply rate limiting"""
    return await rate_limit_middleware(request, call_next)


# Exception handlers
app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint with system status
    
    Returns:
        Health status and system information
    """
    try:
        # Check Supabase connection
        from app.services.supabase_service import supabase_service
        client = supabase_service.get_client()
        supabase_status = "unavailable"
        supabase_test = None
        
        if client:
            try:
                # Test connection with a simple query
                _ = client.table("assessment_profiles").select("id").limit(0).execute()
                supabase_status = "connected"
                supabase_test = "Connection successful"
            except Exception as test_error:
                error_msg = str(test_error).lower()
                if "does not exist" in error_msg or "relation" in error_msg:
                    supabase_status = "connected"
                    supabase_test = "Connected but tables may not exist"
                else:
                    supabase_status = "error"
                    supabase_test = f"Connection test failed: {str(test_error)[:100]}"
        else:
            supabase_test = "Client not initialized - check credentials"
        
        # Check cache status
        cache_stats = cache.stats()
        
        # Check OpenAI availability (if configured)
        openai_status = "configured" if settings.OPENAI_API_KEY and "your-openai" not in settings.OPENAI_API_KEY else "not_configured"
        
        # Run system validation if in debug mode
        validation = None
        if settings.DEBUG:
            try:
                from app.utils.validation import system_validator
                validation = system_validator.full_validation()
            except Exception as e:
                logger.warning(f"Validation check failed: {str(e)}")
        
        # Check environment (Vercel vs local) - reuse is_vercel from above
        environment = "vercel" if is_vercel else "local"
        
        response = {
            "status": "healthy",
            "version": settings.VERSION,
            "service": settings.PROJECT_NAME,
            "environment": environment,
            "checks": {
                "supabase": {
                    "status": supabase_status,
                    "test": supabase_test,
                    "url_configured": bool(settings.SUPABASE_URL and "your-project" not in settings.SUPABASE_URL),
                    "key_configured": bool(settings.SUPABASE_KEY and "your-supabase" not in settings.SUPABASE_KEY),
                    "url_preview": settings.SUPABASE_URL[:30] + "..." if settings.SUPABASE_URL and len(settings.SUPABASE_URL) > 30 else (settings.SUPABASE_URL or "NOT SET")
                },
                "openai": openai_status,
                "cache": cache_stats
            },
            "timestamp": time.time()
        }
        
        if validation:
            response["validation"] = validation
        
        return response
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "error": str(e) if settings.DEBUG else "Service check failed"
            }
        )


@app.get("/", tags=["Root"])
async def root():
    """API status at site root."""
    return {
        "message": "Assessment API is running",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/api-info", tags=["Root"])
async def api_info():
    """JSON discovery for tools / integrations."""
    return JSONResponse(
        {
            "message": "Skill Assessment Platform API",
            "version": settings.VERSION,
            "docs": "/docs",
            "health": "/health",
            "api_prefix": "/api",
            "auth_prefix": "/auth",
        }
    )


# Include routers
from app.routes import dashboard
from app.routes import pdf_upload
from app.routes import assessments as assessment_routes
from app.routes import folder_upload
from app.routes import auth

# Register routers
app.include_router(dashboard.router)
app.include_router(assessment_routes.router)
app.include_router(pdf_upload.router)
app.include_router(folder_upload.router)
app.include_router(auth.router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )

