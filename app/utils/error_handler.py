"""
Centralized error handling utilities
"""

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from typing import Any, Dict, Optional
from pydantic import ValidationError
import traceback

from app.utils.logger import logger
from app.config import settings


class AppException(Exception):
    """Base application exception"""
    
    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code or "INTERNAL_ERROR"
        self.details = details or {}
        super().__init__(self.message)


class NotFoundError(AppException):
    """Resource not found exception"""
    
    def __init__(self, resource: str, identifier: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"{resource} not found: {identifier}",
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="NOT_FOUND",
            details={"resource": resource, "identifier": identifier, **(details or {})}
        )


class ValidationError(AppException):
    """Validation error exception"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error_code="VALIDATION_ERROR",
            details=details or {}
        )


# Alias to avoid conflict with Pydantic's ValidationError
AppValidationError = ValidationError


class UnauthorizedError(AppException):
    """Unauthorized access exception"""
    
    def __init__(self, message: str = "Authentication required"):
        super().__init__(
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="UNAUTHORIZED"
        )


class ForbiddenError(AppException):
    """Forbidden access exception"""
    
    def __init__(self, message: str = "Access forbidden"):
        super().__init__(
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            error_code="FORBIDDEN"
        )


class RateLimitError(AppException):
    """Rate limit exceeded exception"""
    
    def __init__(self, message: str = "Rate limit exceeded", retry_after: Optional[int] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            error_code="RATE_LIMIT_EXCEEDED",
            details={"retry_after": retry_after} if retry_after else {}
        )


def create_error_response(
    message: str,
    status_code: int,
    error_code: str,
    details: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None
) -> JSONResponse:
    """
    Create standardized error response
    
    Args:
        message: Error message
        status_code: HTTP status code
        error_code: Application error code
        details: Additional error details
        request_id: Request ID for tracking
    
    Returns:
        JSONResponse with error details
    """
    response_data = {
        "success": False,
        "error": {
            "code": error_code,
            "message": message,
            "details": details or {}
        }
    }
    
    if request_id:
        response_data["error"]["request_id"] = request_id
    
    return JSONResponse(
        status_code=status_code,
        content=response_data
    )


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler for unhandled exceptions"""
    request_id = getattr(request.state, "request_id", None)
    
    # Log the full exception
    logger.error(
        "Unhandled exception",
        exc_info=exc,
        extra={
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method
        }
    )
    
    # Return user-friendly error
    error_message = str(exc) if settings.DEBUG else "An unexpected error occurred"
    error_details = {"traceback": traceback.format_exc()} if settings.DEBUG else {}
    
    return create_error_response(
        message=error_message,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_code="INTERNAL_SERVER_ERROR",
        details=error_details,
        request_id=request_id
    )


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Handler for application exceptions"""
    request_id = getattr(request.state, "request_id", None)
    
    logger.warning(
        f"Application exception: {exc.message}",
        extra={
            "request_id": request_id,
            "error_code": exc.error_code,
            "status_code": exc.status_code,
            "details": exc.details
        }
    )
    
    return create_error_response(
        message=exc.message,
        status_code=exc.status_code,
        error_code=exc.error_code,
        details=exc.details,
        request_id=request_id
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handler for HTTP exceptions"""
    request_id = getattr(request.state, "request_id", None)
    
    return create_error_response(
        message=exc.detail,
        status_code=exc.status_code,
        error_code="HTTP_ERROR",
        request_id=request_id
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError
) -> JSONResponse:
    """Handler for validation errors - optimized list comprehension"""
    request_id = getattr(request.state, "request_id", None)
    
    # Optimized: list comprehension instead of loop + append
    errors = [
        {
            "field": ".".join(str(loc) for loc in error.get("loc", [])),
            "message": error.get("msg"),
            "type": error.get("type")
        }
        for error in exc.errors()
    ]
    
    logger.warning(
        "Validation error",
        extra={
            "request_id": request_id,
            "errors": errors
        }
    )
    
    return create_error_response(
        message="Validation failed",
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        error_code="VALIDATION_ERROR",
        details={"validation_errors": errors},
        request_id=request_id
    )

