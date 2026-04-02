"""
Session-first profile service for assessments.
Supports no-login student flow and optional admin user mapping.
"""

from typing import Optional, Dict, Any, Tuple
from uuid import UUID, uuid4

from app.services.supabase_service import supabase_service
from app.utils.logger import logger

DEFAULT_STUDENT_ROLE = "student"


def resolve_session_id(session_id: Optional[str]) -> str:
    """Return provided session id or generate a new UUID string."""
    sid = (session_id or "").strip()
    return sid if sid else str(uuid4())


def get_or_create_session_profile(session_id: Optional[str]) -> Tuple[Optional[Dict[str, Any]], str]:
    """
    Ensure a session-backed profile exists in assessment_profiles.

    Returns:
        (profile_row_or_none, effective_session_id)
    """
    sid = resolve_session_id(session_id)
    client = supabase_service.get_client(use_service_key=True) or supabase_service.get_client()
    if not client:
        logger.error("Supabase client not available in get_or_create_session_profile")
        return None, sid

    try:
        existing = client.table("assessment_profiles")\
            .select("id, user_id, session_id, role, created_at")\
            .eq("session_id", sid)\
            .limit(1)\
            .execute()
        if existing.data:
            return existing.data[0], sid

        payload = {
            "session_id": sid,
            "role": DEFAULT_STUDENT_ROLE,
        }
        created = client.table("assessment_profiles").insert(payload).execute()
        if created.data:
            return created.data[0], sid

        # Defensive fallback read-after-write
        verify = client.table("assessment_profiles")\
            .select("id, user_id, session_id, role, created_at")\
            .eq("session_id", sid)\
            .limit(1)\
            .execute()
        if verify.data:
            return verify.data[0], sid

        logger.error("Failed to create session profile")
        return None, sid
    except Exception as e:
        logger.error(f"Error in get_or_create_session_profile: {str(e)}")
        return None, sid


def get_test_user_id(session_id: Optional[str] = None) -> Optional[UUID]:
    """
    Backward-compatible alias used by existing routes.
    Returns session profile primary key UUID.
    """
    profile, _ = get_or_create_session_profile(session_id)
    if not profile:
        return None
    try:
        return UUID(str(profile.get("id")))
    except Exception:
        return None


def get_or_create_default_user() -> Optional[UUID]:
    """Backward-compatible helper."""
    return get_test_user_id()
