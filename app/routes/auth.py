"""
FastAPI routes for authentication using Supabase
"""

from fastapi import APIRouter, HTTPException, status, Depends
from typing import Optional
from pydantic import BaseModel, EmailStr
from uuid import UUID

from app.services.supabase_service import supabase_service
from app.utils.logger import logger
from app.utils.error_handler import AppException
from app.utils.auth import get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


# Request/Response models
class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


@router.post("/login", response_model=AuthResponse, status_code=status.HTTP_200_OK)
async def login(request: LoginRequest):
    """
    Login user using Supabase Auth
    
    - **email**: User email address
    - **password**: User password
    """
    try:
        client = supabase_service.get_client()
        if not client:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service unavailable. Please configure Supabase credentials."
            )
        
        # Authenticate with Supabase
        response = client.auth.sign_in_with_password({
            "email": request.email,
            "password": request.password
        })
        
        if not response.user or not response.session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        # Get or create user profile
        user_id = UUID(response.user.id)
        profile = supabase_service.get_profile(user_id)
        
        if not profile:
            # Create profile if it doesn't exist
            profile = supabase_service.create_profile(
                user_id=user_id,
                email=request.email,
                name=response.user.user_metadata.get("name", ""),
                created_at=response.user.created_at
            )
        
        return {
            "access_token": response.session.access_token,
            "token_type": "bearer",
            "user": {
                "id": response.user.id,
                "email": response.user.email,
                "name": profile.get("name") if profile else response.user.user_metadata.get("name", ""),
                "profile": profile
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {str(e)}"
        )


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest):
    """
    Register new user using Supabase Auth
    
    - **email**: User email address
    - **password**: User password (min 6 characters)
    - **name**: User full name
    """
    logger.info(f"[REGISTER] Registration request received for email: {request.email}, name: {request.name}")
    logger.info(f"[REGISTER] Password length: {len(request.password)}")
    
    try:
        client = supabase_service.get_client()
        logger.info(f"[REGISTER] Supabase client obtained: {client is not None}")
        
        if not client:
            logger.error("[REGISTER] Supabase client is None - credentials not configured")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service unavailable. Please configure Supabase credentials."
            )
        
        # Validate password length
        if len(request.password) < 6:
            logger.warning(f"[REGISTER] Password validation failed - length: {len(request.password)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 6 characters"
            )
        
        # Register with Supabase - email confirmation disabled
        # Users are auto-confirmed and can login immediately
        logger.info(f"[REGISTER] Calling Supabase sign_up for: {request.email}")
        try:
            signup_data = {
                "email": request.email,
                "password": request.password,
                "options": {
                    "data": {
                        "name": request.name
                    }
                    # No email_redirect_to - email confirmation is disabled
                }
            }
            logger.info(f"[REGISTER] Signup data prepared (password hidden)")
            response = client.auth.sign_up(signup_data)
            logger.info(f"[REGISTER] Supabase sign_up response received")
            logger.info(f"[REGISTER] Response user: {response.user is not None if response else 'None'}")
            logger.info(f"[REGISTER] Response session: {response.session is not None if response else 'None'}")
        except Exception as signup_error:
            error_msg = str(signup_error)
            error_type = type(signup_error).__name__
            logger.error(f"[REGISTER] Supabase sign_up exception: {error_type}: {error_msg}")
            logger.error(f"[REGISTER] Full error details: {repr(signup_error)}")
            
            # Check for common Supabase errors
            if "already registered" in error_msg.lower() or "already exists" in error_msg.lower() or "user already" in error_msg.lower():
                logger.warning(f"[REGISTER] Email already registered: {request.email}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered. Please use a different email or try logging in."
                )
            elif "invalid" in error_msg.lower() or "validation" in error_msg.lower():
                logger.warning(f"[REGISTER] Invalid registration data: {error_msg}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid registration data: {error_msg}"
                )
            else:
                logger.error(f"[REGISTER] Unknown Supabase error: {error_msg}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Registration failed: {error_msg}"
                )
        
        if not response.user:
            logger.error(f"[REGISTER] No user in response for: {request.email}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Registration failed. Email may already be in use."
            )
        
        logger.info(f"[REGISTER] User created successfully: {response.user.id}")
        logger.info(f"[REGISTER] User email: {response.user.email}")
        
        # Create user profile
        user_id = UUID(response.user.id)
        logger.info(f"[REGISTER] Creating profile for user: {user_id}")
        profile = supabase_service.create_profile(
            user_id=user_id,
            email=request.email,
            name=request.name,
            created_at=response.user.created_at
        )
        logger.info(f"[REGISTER] Profile created: {profile is not None}")
        
        # Auto-confirm user if email confirmation is enabled in Supabase
        # If session is None, use service key to auto-confirm and get session
        if not response.session:
            logger.info(f"No session returned for {request.email} - attempting auto-confirmation")
            # Email confirmation was required - auto-confirm using service key
            from app.config import settings
            if settings.SUPABASE_SERVICE_KEY:
                try:
                    # Use service key to auto-confirm user
                    from supabase import create_client
                    admin_client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
                    
                    # Auto-confirm the user
                    admin_client.auth.admin.update_user_by_id(
                        response.user.id,
                        {"email_confirm": True}
                    )
                    logger.info(f"User {request.email} auto-confirmed via service key")
                    
                    # Sign in the user to get session
                    signin_response = client.auth.sign_in_with_password({
                        "email": request.email,
                        "password": request.password
                    })
                    
                    if signin_response.session:
                        response.session = signin_response.session
                        logger.info(f"User {request.email} signed in successfully after auto-confirmation")
                    else:
                        logger.warning(f"Sign in after auto-confirmation returned no session for {request.email}")
                        raise HTTPException(
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Failed to create session after auto-confirmation. Please try logging in."
                        )
                except HTTPException:
                    raise
                except Exception as e:
                    logger.error(f"Auto-confirmation error: {str(e)}")
                    # If auto-confirmation fails, try to sign in anyway
                    # (user might already be confirmed if Supabase settings are disabled)
                    try:
                        logger.info(f"Attempting sign in without auto-confirmation for {request.email}")
                        signin_response = client.auth.sign_in_with_password({
                            "email": request.email,
                            "password": request.password
                        })
                        if signin_response.session:
                            response.session = signin_response.session
                            logger.info(f"User {request.email} signed in successfully without auto-confirmation")
                        else:
                            logger.warning(f"Sign in attempt returned no session for {request.email}")
                    except Exception as signin_err:
                        logger.error(f"Sign in error: {str(signin_err)}")
            else:
                logger.warning(f"SUPABASE_SERVICE_KEY not configured - trying direct sign in for {request.email}")
                # No service key - try to sign in directly (user might already be confirmed)
                try:
                    signin_response = client.auth.sign_in_with_password({
                        "email": request.email,
                        "password": request.password
                    })
                    if signin_response.session:
                        response.session = signin_response.session
                        logger.info(f"User {request.email} signed in successfully (no service key needed)")
                    else:
                        logger.warning(f"Direct sign in returned no session for {request.email}")
                except Exception as signin_err:
                    logger.error(f"Direct sign in error: {str(signin_err)}")
        
        # If still no session, raise error
        if not response.session:
            logger.error(f"No session available for {request.email} after all attempts")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Registration successful but unable to create session. Please try logging in manually. If this persists, check Supabase configuration."
            )
        
        # User is auto-confirmed and logged in
        logger.info(f"[REGISTER] Registration successful for: {request.email}")
        logger.info(f"[REGISTER] Access token length: {len(response.session.access_token) if response.session else 0}")
        
        result = {
            "access_token": response.session.access_token,
            "token_type": "bearer",
            "user": {
                "id": response.user.id,
                "email": response.user.email,
                "name": request.name,
                "profile": profile
            }
        }
        logger.info(f"[REGISTER] Returning success response for: {request.email}")
        return result
        
    except HTTPException as http_err:
        logger.error(f"[REGISTER] HTTPException: {http_err.status_code} - {http_err.detail}")
        raise
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        logger.error(f"[REGISTER] Unexpected exception: {error_type}: {error_msg}")
        logger.error(f"[REGISTER] Full error details: {repr(e)}")
        import traceback
        logger.error(f"[REGISTER] Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {error_msg}"
        )


@router.get("/me")
async def get_current_user_info(
    current_user: dict = Depends(get_current_user)
):
    """
    Get current user information
    """
    return {
        "id": current_user.get("id"),
        "email": current_user.get("email"),
        "role": current_user.get("role"),
        "email_verified": current_user.get("email_verified", False)
    }

