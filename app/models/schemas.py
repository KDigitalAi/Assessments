"""
Pydantic schemas for request/response validation - optimized for performance
"""

from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime

# Note: Pattern strings are used directly in Field() - Pydantic compiles them internally for efficiency


# ============================================
# Assessment Schemas
# ============================================

class AssessmentCreate(BaseModel):
    """Schema for creating an assessment - optimized"""
    model_config = ConfigDict(
        extra="forbid",  # Reject extra fields for security
        str_strip_whitespace=True,  # Auto-strip strings
        validate_assignment=True,  # Validate on assignment
        str_max_length=5000  # Global max length
    )
    
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=1000)
    skill_domain: str = Field(..., min_length=1, max_length=100)
    difficulty: str = Field(default="medium", pattern=r"^(easy|medium|hard)$")
    question_count: int = Field(default=10, ge=1, le=100)
    duration_minutes: int = Field(default=60, ge=5, le=300)
    passing_score: int = Field(default=60, ge=0, le=100)
    blueprint: Optional[str] = Field(default=None, max_length=5000)


class AssessmentUpdate(BaseModel):
    """Schema for updating an assessment - optimized"""
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True
    )
    
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=1000)
    skill_domain: Optional[str] = Field(default=None, min_length=1, max_length=100)
    difficulty: Optional[str] = Field(default=None, pattern=r"^(easy|medium|hard)$")
    question_count: Optional[int] = Field(default=None, ge=1, le=100)
    duration_minutes: Optional[int] = Field(default=None, ge=5, le=300)
    passing_score: Optional[int] = Field(default=None, ge=0, le=100)
    status: Optional[str] = Field(default=None, pattern=r"^(draft|published|archived)$")
    blueprint: Optional[str] = Field(default=None, max_length=5000)


class AssessmentResponse(BaseModel):
    """Schema for assessment response - optimized"""
    model_config = ConfigDict(
        from_attributes=True,  # Pydantic v2 way to say orm_mode=True
        extra="ignore",  # Ignore extra fields from DB
        str_strip_whitespace=True
    )
    
    id: UUID
    title: str
    description: Optional[str] = None
    skill_domain: str
    difficulty: str
    question_count: int
    duration_minutes: int
    passing_score: int
    status: str
    blueprint: Optional[str] = None
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    published_at: Optional[datetime] = None


# ============================================
# Question Schemas
# ============================================

class QuestionGenerate(BaseModel):
    """Schema for generating a question - optimized"""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    
    assessment_id: UUID
    question_type: str = Field(default="mcq", pattern=r"^(mcq|descriptive|coding)$")
    difficulty: Optional[str] = Field(default="medium", pattern=r"^(easy|medium|hard)$")
    skill_domain: Optional[str] = None
    blueprint: Optional[str] = Field(default=None, max_length=2000)
    count: int = Field(default=1, ge=1, le=10)


class QuestionCreate(BaseModel):
    """Schema for manually creating a question - optimized"""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    
    assessment_id: UUID
    question_text: str = Field(..., min_length=1)
    question_type: str = Field(..., pattern=r"^(mcq|descriptive|coding)$")
    difficulty: str = Field(default="medium", pattern=r"^(easy|medium|hard)$")
    options: Optional[List[str]] = None
    correct_answer: Optional[str] = None
    explanation: Optional[str] = None
    rubric: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None
    skill_domain: Optional[str] = None
    estimated_time: int = Field(default=60, ge=1, le=600)
    
    @field_validator("options")
    @classmethod
    def validate_options(cls, v, info):
        """Validate MCQ options - optimized validator"""
        if info.data.get("question_type") == "mcq" and (not v or len(v) < 2):
            raise ValueError("MCQ questions require at least 2 options")
        return v


class QuestionResponse(BaseModel):
    """Schema for question response - optimized"""
    model_config = ConfigDict(from_attributes=True, extra="ignore", str_strip_whitespace=True)
    
    id: UUID
    assessment_id: UUID
    question_text: str
    question_type: str
    difficulty: str
    options: Optional[List[str]] = None
    correct_answer: Optional[str] = None
    explanation: Optional[str] = None
    rubric: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None
    skill_domain: Optional[str] = None
    estimated_time: int
    created_at: datetime
    updated_at: datetime


# ============================================
# Attempt Schemas
# ============================================

class AttemptStart(BaseModel):
    """Schema for starting an attempt"""
    assessment_id: UUID


class AttemptResponse(BaseModel):
    """Schema for attempt response - optimized"""
    model_config = ConfigDict(from_attributes=True, extra="ignore")
    
    id: UUID
    assessment_id: UUID
    user_id: UUID
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    total_score: float
    max_score: float
    percentage_score: float
    time_spent_seconds: int
    time_remaining: Optional[int] = None


class AttemptUpdate(BaseModel):
    """Schema for updating an attempt - optimized"""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    
    status: Optional[str] = Field(default=None, pattern=r"^(completed|abandoned|timed_out)$")
    time_spent_seconds: Optional[int] = Field(default=None, ge=0)


# ============================================
# Response Schemas
# ============================================

class ResponseSubmit(BaseModel):
    """Schema for submitting a response - optimized"""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    
    attempt_id: UUID
    question_id: UUID
    answer_text: Optional[str] = None
    selected_option: Optional[int] = Field(default=None, ge=0)


class ResponseScore(BaseModel):
    """Schema for scored response - optimized"""
    model_config = ConfigDict(from_attributes=True, extra="ignore")
    
    id: UUID
    attempt_id: UUID
    question_id: UUID
    answer_text: Optional[str] = None
    selected_option: Optional[int] = None
    status: str
    score: float
    max_score: float
    feedback: Optional[str] = None
    feedback_json: Optional[Dict[str, Any]] = None
    auto_scored: bool
    scored_at: Optional[datetime] = None


class ResponseResponse(BaseModel):
    """Schema for response response - optimized"""
    model_config = ConfigDict(extra="forbid")
    
    response: ResponseScore
    question: Optional[QuestionResponse] = None


# ============================================
# Result Schemas
# ============================================

class ResultResponse(BaseModel):
    """Schema for result response - optimized"""
    model_config = ConfigDict(from_attributes=True, extra="ignore")
    
    id: UUID
    attempt_id: UUID
    user_id: UUID
    assessment_id: UUID
    total_score: float
    max_score: float
    percentage_score: float
    passing_score: int
    passed: bool
    section_scores: Optional[Dict[str, Any]] = None
    overall_feedback: Optional[str] = None
    feedback_json: Optional[Dict[str, Any]] = None
    report_url: Optional[str] = None
    generated_at: datetime


# ============================================
# Report Schemas
# ============================================

class ReportRequest(BaseModel):
    """Schema for report generation request"""
    attempt_id: UUID
    include_feedback: bool = True
    include_analytics: bool = True


class ReportResponse(BaseModel):
    """Schema for report response"""
    report_url: str
    signed_url: str
    expires_at: datetime
    attempt_id: UUID


# ============================================
# Generic Response Schemas
# ============================================

class SuccessResponse(BaseModel):
    """Generic success response - optimized"""
    model_config = ConfigDict(extra="forbid")  # Note: frozen=True available in Pydantic v2.1+
    
    success: bool = True
    message: str
    data: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseModel):
    """Generic error response - optimized"""
    model_config = ConfigDict(extra="forbid")  # Note: frozen=True available in Pydantic v2.1+
    
    success: bool = False
    error: str
    details: Optional[Dict[str, Any]] = None

