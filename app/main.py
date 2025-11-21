"""
FastAPI main application entry point with improved security and error handling
"""

from fastapi import FastAPI, Request, status, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
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
    try:
        from app.services.profile_service import get_test_user_id, TEST_USER_EMAIL
        
        get_test_user_id()
    except Exception as e:
        logger.warning(f"Error checking/creating test user: {str(e)}")
        # Don't fail startup if profile creation fails
    
    # Check if assessments exist, if not generate them automatically
    try:
        from app.services.supabase_service import supabase_service
        from app.services.assessment_generator import assessment_generator
        
        client = supabase_service.get_client()
        if client:
            # Check if any published assessments exist
            assessments_response = client.table("assessments")\
                .select("id", count="exact")\
                .eq("status", "published")\
                .execute()
            
            assessment_count = assessments_response.count if hasattr(assessments_response, 'count') else 0
            
            if assessment_count == 0:
                asyncio.create_task(asyncio.to_thread(assessment_generator.generate_all_assessments))
        else:
            logger.warning("Supabase client not available. Cannot check for existing assessments.")
    except Exception as e:
        logger.warning(f"Error checking/generating assessments on startup: {str(e)}")
        # Don't fail startup if assessment generation fails
    
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

# CORS Middleware
# For development, allow all origins. For production, use specific origins.
# Note: When allow_origins=["*"], allow_credentials must be False
# Always allow all origins in development (check DEBUG env var or default to permissive for local dev)
# Force development mode if running on localhost/127.0.0.1
is_localhost = os.getenv("HOST", "127.0.0.1") in ("127.0.0.1", "localhost", "0.0.0.0")
# Check if running on Vercel (production)
is_vercel = os.getenv("VERCEL") == "1" or "vercel.app" in os.getenv("VERCEL_URL", "")
debug_mode = (settings.DEBUG or os.getenv("DEBUG", "True").lower() in ("true", "1", "yes") or is_localhost) and not is_vercel

# In development mode or on Vercel, allow all origins for easier frontend-backend communication
# On Vercel, frontend and backend are same-origin, but allow all for flexibility
if debug_mode or is_vercel:
    # In development or Vercel, always allow all origins for maximum compatibility
    # Use wildcard "*" which works best with Vite proxy and Vercel deployments
    cors_origins = ["*"]
    cors_allow_credentials = False
else:
    # In production (non-Vercel), use settings but ensure common frontend ports are included
    cors_origins = settings.cors_origins_list.copy() if settings.cors_origins_list else []
    # Always include common frontend ports for compatibility
    common_origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5176",
        "http://127.0.0.1:5176",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "file://",  # Allow file:// protocol for direct HTML file access
    ]
    for origin in common_origins:
        if origin not in cors_origins:
            cors_origins.append(origin)
    cors_allow_credentials = True if cors_origins else False

# Log CORS configuration for debugging

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
                _ = client.table("profiles").select("id").limit(0).execute()
                supabase_status = "connected"
                supabase_test = "✅ Connection successful"
            except Exception as test_error:
                error_msg = str(test_error).lower()
                if "does not exist" in error_msg or "relation" in error_msg:
                    supabase_status = "connected"
                    supabase_test = "⚠️ Connected but tables may not exist"
                else:
                    supabase_status = "error"
                    supabase_test = f"❌ Connection test failed: {str(test_error)[:100]}"
        else:
            supabase_test = "❌ Client not initialized - check credentials"
        
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
        
        # Check environment (Vercel vs local)
        is_vercel_env = os.getenv("VERCEL") == "1" or "vercel.app" in os.getenv("VERCEL_URL", "")
        environment = "vercel" if is_vercel_env else "local"
        
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


# Setup static files serving for frontend
# Get the project root directory (parent of 'app' folder)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"

# Mount static files from frontend directory
if FRONTEND_DIR.exists():
    try:
        app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
    except Exception as e:
        logger.warning(f"Could not mount frontend directory: {str(e)}")
else:
    logger.warning(f"Frontend directory does not exist: {FRONTEND_DIR}")

# Root endpoint - Serve frontend HTML page
@app.get("/", tags=["Root"], response_class=HTMLResponse)
async def root():
    """Root endpoint - Returns frontend assessment page"""
    try:
        html_file = FRONTEND_DIR / "index.html"
        if html_file.exists():
            return FileResponse(html_file)
        else:
            logger.warning(f"Frontend index.html not found: {html_file}")
            # Fallback to JSON if HTML file doesn't exist
            return JSONResponse({
                "message": "Welcome to Skill Assessment Platform",
                "version": settings.VERSION,
                "docs": "/docs",
                "health": "/health",
                "note": "Frontend index.html not found. Please ensure frontend/index.html exists."
            })
    except Exception as e:
        logger.error(f"Error serving frontend: {str(e)}", exc_info=True)
        # Fallback to JSON on error
        return JSONResponse({
            "message": "Welcome to Skill Assessment Platform",
            "version": settings.VERSION,
            "docs": "/docs",
            "health": "/health",
            "error": str(e) if settings.DEBUG else "Frontend error"
        })


# Assessment page endpoint
@app.get("/static/assessment.html", tags=["Frontend"], response_class=HTMLResponse)
async def assessment_page():
    """Serve assessment page"""
    try:
        html_file = FRONTEND_DIR / "assessment.html"
        if html_file.exists():
            return FileResponse(html_file)
        else:
            return JSONResponse({"error": "Assessment page not found"}, status_code=404)
    except Exception as e:
        logger.error(f"Error serving assessment page: {str(e)}", exc_info=True)
        return JSONResponse({"error": "Failed to load assessment page"}, status_code=500)


# Results page endpoint
@app.get("/static/results.html", tags=["Frontend"], response_class=HTMLResponse)
async def results_page():
    """Serve results page"""
    try:
        html_file = FRONTEND_DIR / "results.html"
        if html_file.exists():
            return FileResponse(html_file)
        else:
            return JSONResponse({"error": "Results page not found"}, status_code=404)
    except Exception as e:
        logger.error(f"Error serving results page: {str(e)}", exc_info=True)
        return JSONResponse({"error": "Failed to load results page"}, status_code=500)


# Assessments page endpoint (course-specific assessments)
@app.get("/static/assessments.html", tags=["Frontend"], response_class=HTMLResponse)
async def assessments_page():
    """Serve assessments page for a specific course"""
    try:
        html_file = FRONTEND_DIR / "assessments.html"
        if html_file.exists():
            return FileResponse(html_file)
        else:
            return JSONResponse({"error": "Assessments page not found"}, status_code=404)
    except Exception as e:
        logger.error(f"Error serving assessments page: {str(e)}", exc_info=True)
        return JSONResponse({"error": "Failed to load assessments page"}, status_code=500)


# Include routers
# Dashboard router (unified API - main endpoints)
from app.routes import dashboard
app.include_router(dashboard.router)

# Assessment generation router
from app.routes import assessments as assessment_routes
app.include_router(assessment_routes.router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )

