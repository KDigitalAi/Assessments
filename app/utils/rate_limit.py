"""
Rate limiting middleware using sliding window algorithm
"""

from fastapi import Request, status
from fastapi.responses import JSONResponse
from typing import Dict, Tuple, Optional
from datetime import datetime, timedelta
from collections import defaultdict, deque
import time
from threading import Lock

from app.utils.error_handler import RateLimitError, create_error_response
from app.utils.logger import logger


class RateLimiter:
    """Sliding window rate limiter"""
    
    def __init__(self):
        """Initialize rate limiter"""
        self._requests: Dict[str, deque] = defaultdict(deque)
        self._locks: Dict[str, Lock] = defaultdict(Lock)
    
    def _get_key(self, request: Request, user_id: Optional[str] = None) -> str:
        """Generate rate limit key"""
        if user_id:
            return f"user:{user_id}"
        
        # Fallback to IP address
        client_ip = request.client.host if request.client else "unknown"
        return f"ip:{client_ip}"
    
    def _clean_old_requests(self, key: str, window_seconds: int) -> None:
        """Remove requests outside the time window - optimized"""
        lock = self._locks[key]
        with lock:
            requests = self._requests[key]
            if not requests:
                return  # Early exit if empty
            
            # Optimized: compute once
            now = time.time()
            cutoff = now - window_seconds
            
            # Remove old requests - efficient deque popleft
            while requests and requests[0] < cutoff:
                requests.popleft()
    
    def is_allowed(
        self,
        key: str,
        max_requests: int,
        window_seconds: int
    ) -> Tuple[bool, Optional[int]]:
        """
        Check if request is allowed - optimized
        
        Args:
            key: Rate limit key
            max_requests: Maximum requests per window
            window_seconds: Time window in seconds
        
        Returns:
            Tuple of (is_allowed, retry_after_seconds)
        """
        self._clean_old_requests(key, window_seconds)
        
        lock = self._locks[key]
        with lock:
            requests = self._requests[key]
            requests_count = len(requests)
            now = time.time()
            
            # Check if limit exceeded - optimized: compute length once
            if requests_count >= max_requests:
                # Calculate retry after - optimized: reuse now
                oldest_request = requests[0] if requests else now
                retry_after = int(window_seconds - (now - oldest_request)) + 1
                return False, max(1, retry_after)  # Ensure at least 1 second
            
            # Add current request
            requests.append(now)
            return True, None
    
    def check_rate_limit(
        self,
        request: Request,
        user_id: Optional[str] = None,
        max_requests: int = 60,
        window_seconds: int = 60
    ) -> Optional[JSONResponse]:
        """
        Check rate limit for request
        
        Args:
            request: FastAPI request
            user_id: Optional user ID for per-user rate limiting
            max_requests: Maximum requests per window
            window_seconds: Time window in seconds
        
        Returns:
            JSONResponse if rate limited, None otherwise
        """
        key = self._get_key(request, user_id)
        allowed, retry_after = self.is_allowed(key, max_requests, window_seconds)
        
        if not allowed:
            logger.warning(
                "Rate limit exceeded",
                extra={
                    "key": key,
                    "max_requests": max_requests,
                    "window_seconds": window_seconds,
                    "retry_after": retry_after
                }
            )
            
            request_id = getattr(request.state, "request_id", None)
            return create_error_response(
                message=f"Rate limit exceeded. Maximum {max_requests} requests per {window_seconds} seconds.",
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                error_code="RATE_LIMIT_EXCEEDED",
                details={"retry_after": retry_after},
                request_id=request_id
            )
        
        return None


# Global rate limiter instance
rate_limiter = RateLimiter()


def rate_limit(max_requests: int = 60, window_seconds: int = 60):
    """
    Decorator for rate limiting endpoints
    
    Args:
        max_requests: Maximum requests per window
        window_seconds: Time window in seconds
    
    Usage:
        @router.post("/endpoint")
        @rate_limit(max_requests=10, window_seconds=60)
        async def my_endpoint(...):
            ...
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Extract request from args or kwargs
            request = None
            user_id = None
            
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            
            if not request:
                request = kwargs.get("request")
            
            # Get user ID if available
            if request and hasattr(request.state, "user_id"):
                user_id = request.state.user_id
            
            # Check rate limit
            if request:
                response = rate_limiter.check_rate_limit(
                    request=request,
                    user_id=user_id,
                    max_requests=max_requests,
                    window_seconds=window_seconds
                )
                if response:
                    return response
            
            return await func(*args, **kwargs)
        
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper
    return decorator


async def rate_limit_middleware(request: Request, call_next):
    """Middleware for global rate limiting"""
    # Skip rate limiting for health check
    if request.url.path == "/health":
        return await call_next(request)
    
    # Per-user rate limiting if authenticated
    user_id = getattr(request.state, "user_id", None)
    
    response = rate_limiter.check_rate_limit(
        request=request,
        user_id=user_id,
        max_requests=100,  # Default: 100 requests per minute
        window_seconds=60
    )
    
    if response:
        return response
    
    return await call_next(request)

