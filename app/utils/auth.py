"""
Authentication and authorization utilities with improved JWT validation
"""

from fastapi import Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from supabase import create_client, Client
from datetime import datetime, timedelta, timezone
import uuid

from app.config import settings
from app.utils.error_handler import UnauthorizedError, ForbiddenError
from app.utils.logger import logger


security = HTTPBearer(auto_error=False)


# Cache client to avoid recreation - optimized
_cached_client: Optional[Client] = None

def get_supabase_client() -> Optional[Client]:
    """Create and return Supabase client - optimized with caching"""
    global _cached_client
    
    if _cached_client is not None:
        return _cached_client
    
    try:
        if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
            logger.warning("Supabase credentials not configured")
            return None
        if "your-project" in settings.SUPABASE_URL or "your-supabase" in settings.SUPABASE_KEY:
            logger.warning("Supabase credentials appear to be placeholders")
            return None
        _cached_client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
        return _cached_client
    except Exception as e:
        logger.error(f"Failed to create Supabase client: {str(e)}")
        return None


def verify_jwt_token(token: str) -> Optional[dict]:
    """
    Verify JWT token and extract user information
    
    Args:
        token: JWT token string
        
    Returns:
        User information dictionary or None if invalid
    """
    try:
        supabase = get_supabase_client()
        if not supabase:
            return None
        
        # Verify token with Supabase Auth
        user_response = supabase.auth.get_user(token)
        
        if user_response and user_response.user:
            user = user_response.user
            
            # Extract token metadata if available
            token_metadata = getattr(user_response, 'token_metadata', {}) or {}
            exp = token_metadata.get('exp')
            
            # Check token expiration if available - optimized datetime reuse
            if exp:
                exp_time = datetime.fromtimestamp(exp, tz=timezone.utc)
                now = datetime.now(timezone.utc)
                if exp_time < now:
                    logger.warning("Token has expired")
                    return None
            
            return {
                "id": user.id,
                "email": user.email or "",
                "role": user.user_metadata.get("role", "user") if user.user_metadata else "user",
                "email_verified": user.email_confirmed_at is not None
            }
        
        return None
    except Exception as e:
        logger.error(f"Token verification error: {str(e)}", exc_info=True)
        return None


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> dict:
    """
    Dependency to get current authenticated user with request context
    
    Args:
        request: FastAPI request object
        credentials: HTTP Bearer token credentials
        
    Returns:
        User information dictionary
        
    Raises:
        UnauthorizedError: If authentication fails
    """
    # Generate request ID for tracking
    if not hasattr(request.state, "request_id"):
        request.state.request_id = str(uuid.uuid4())
    
    if not credentials:
        logger.warning(
            "Missing authentication credentials",
            extra={"request_id": request.state.request_id, "path": request.url.path}
        )
        raise UnauthorizedError("Authentication required. Please provide a valid token.")
    
    token = credentials.credentials
    
    user = verify_jwt_token(token)
    
    if not user:
        logger.warning(
            "Invalid or expired token",
            extra={"request_id": request.state.request_id, "path": request.url.path}
        )
        raise UnauthorizedError("Invalid or expired token")
    
    # Add user to request state for logging
    request.state.user_id = user["id"]
    
    logger.debug(
        "User authenticated",
        extra={
            "request_id": request.state.request_id,
            "user_id": user["id"],
            "path": request.url.path
        }
    )
    
    return user


async def get_current_admin_user(
    request: Request,
    current_user: dict = Depends(get_current_user)
) -> dict:
    """
    Dependency to verify admin user
    
    Args:
        request: FastAPI request object
        current_user: Current authenticated user
        
    Returns:
        User information dictionary
        
    Raises:
        ForbiddenError: If user is not an admin
    """
    if current_user.get("role") != "admin":
        logger.warning(
            "Admin access required",
            extra={
                "request_id": getattr(request.state, "request_id", None),
                "user_id": current_user.get("id"),
                "user_role": current_user.get("role")
            }
        )
        raise ForbiddenError("Admin access required")
    
    return current_user


def check_user_access(
    user_id: str,
    resource_user_id: str,
    admin_override: bool = False,
    user_role: Optional[str] = None
) -> bool:
    """
    Check if user has access to a resource
    
    Args:
        user_id: Current user ID
        resource_user_id: Resource owner user ID
        admin_override: Whether admin can access any resource
        user_role: User role (for admin check)
        
    Returns:
        True if user has access, False otherwise
    """
    if admin_override and user_role == "admin":
        return True
    return user_id == resource_user_id

