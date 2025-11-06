"""
Helper utility functions
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import json
import hashlib


def generate_attempt_id(user_id: str, assessment_id: str) -> str:
    """Generate unique attempt ID"""
    timestamp = datetime.now(timezone.utc).isoformat()
    raw = f"{user_id}_{assessment_id}_{timestamp}"
    return hashlib.md5(raw.encode()).hexdigest()[:16]


def calculate_time_remaining(start_time: datetime, duration_minutes: int) -> int:
    """Calculate remaining time in seconds - optimized datetime reuse"""
    end_time = start_time + timedelta(minutes=duration_minutes)
    now = datetime.now(timezone.utc)
    remaining = (end_time - now).total_seconds()
    return max(0, int(remaining))


def validate_json_response(content: str) -> Dict[str, Any]:
    """Parse and validate JSON response from LLM - optimized string operations"""
    try:
        # Remove code block markers if present - optimized single pass
        content = content.strip()
        
        # Optimized: check prefixes once
        if content.startswith("```json"):
            content = content[7:].strip()
        elif content.startswith("```"):
            content = content[3:].strip()
        
        # Remove trailing markers
        if content.endswith("```"):
            content = content[:-3].strip()
        
        return json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON response from LLM: {str(e)}")


def extract_question_metadata(question_data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract and structure question metadata"""
    return {
        "skill_domain": question_data.get("skill_domain", ""),
        "difficulty": question_data.get("difficulty", "medium"),
        "tags": question_data.get("tags", []),
        "question_type": question_data.get("question_type", "mcq"),
        "estimated_time": question_data.get("estimated_time", 60),  # seconds
    }


def format_score_percentage(score: float, max_score: float) -> float:
    """Calculate and format score as percentage"""
    if max_score == 0:
        return 0.0
    return round((score / max_score) * 100, 2)


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for storage - optimized with str.translate"""
    # Use str.translate for O(1) character replacement instead of O(n*m) loop
    invalid_chars = '<>:"/\\|?*'
    translation_table = str.maketrans(invalid_chars, '_' * len(invalid_chars))
    return filename.translate(translation_table)[:255]  # Limit length


def parse_rubric(rubric_str: str) -> Dict[str, Any]:
    """Parse rubric string to structured format"""
    try:
        if isinstance(rubric_str, str):
            return json.loads(rubric_str)
        return rubric_str
    except (json.JSONDecodeError, TypeError):
        return {
            "criteria": "Overall answer quality",
            "max_points": 10,
            "description": rubric_str if rubric_str else "No rubric provided"
        }


def generate_report_filename(attempt_id: str, user_email: Optional[str] = None) -> str:
    """Generate filename for PDF report"""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    user_part = user_email.split("@")[0] if user_email else "user"
    return f"assessment_report_{user_part}_{attempt_id}_{timestamp}.pdf"


def check_assessment_permission(
    assessment: Dict[str, Any],
    current_user: Dict[str, Any],
    require_creator: bool = False
) -> bool:
    """Check if user has permission to access assessment - optimized helper"""
    if current_user.get("role") == "admin":
        return True
    
    if require_creator:
        return assessment.get("created_by") == current_user.get("id")
    
    # For viewing: published or creator
    return (
        assessment.get("status") == "published" or
        assessment.get("created_by") == current_user.get("id")
    )


def extract_url_path(report_url: str) -> Optional[tuple[str, str]]:
    """Extract bucket and file path from Supabase storage URL - optimized"""
    if "/storage/v1/object/public/" not in report_url:
        return None
    
    try:
        path_parts = report_url.split("/storage/v1/object/public/", 1)
        if len(path_parts) > 1:
            bucket_and_path = path_parts[1]
            parts = bucket_and_path.split("/", 1)
            if len(parts) == 2:
                return parts[0], parts[1]
    except (ValueError, IndexError):
        pass
    
    return None


def parse_datetime_iso(dt_str: str) -> datetime:
    """Parse ISO datetime string with optimized Z handling"""
    # Optimize: single replace instead of checking
    if dt_str.endswith('Z'):
        dt_str = dt_str[:-1] + '+00:00'
    return datetime.fromisoformat(dt_str)

