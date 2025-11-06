"""
Database models and table definitions - optimized for performance
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID


class Profile(BaseModel):
    """Profile model - optimized"""
    model_config = ConfigDict(from_attributes=True, extra="ignore", str_strip_whitespace=True)
    
    id: UUID
    email: str
    full_name: Optional[str] = None
    role: str = "user"
    organization: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class Assessment(BaseModel):
    """Assessment model - optimized"""
    model_config = ConfigDict(from_attributes=True, extra="ignore", str_strip_whitespace=True)
    
    id: UUID
    title: str
    description: Optional[str] = None
    skill_domain: str
    difficulty: str = "medium"
    question_count: int = 10
    duration_minutes: int = 60
    passing_score: int = 60
    status: str = "draft"
    blueprint: Optional[str] = None
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    published_at: Optional[datetime] = None


class Question(BaseModel):
    """Question model - optimized"""
    model_config = ConfigDict(from_attributes=True, extra="ignore", str_strip_whitespace=True)
    
    id: UUID
    assessment_id: UUID
    question_text: str
    question_type: str
    difficulty: str = "medium"
    options: Optional[List[str]] = None
    correct_answer: Optional[str] = None
    explanation: Optional[str] = None
    rubric: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None
    skill_domain: Optional[str] = None
    estimated_time: int = 60
    embedding: Optional[List[float]] = None
    created_at: datetime
    updated_at: datetime


class Attempt(BaseModel):
    """Attempt model - optimized"""
    model_config = ConfigDict(from_attributes=True, extra="ignore")
    
    id: UUID
    assessment_id: UUID
    user_id: UUID
    status: str = "in_progress"
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    total_score: float = 0.0
    max_score: float = 0.0
    percentage_score: float = 0.0
    time_spent_seconds: int = 0
    created_at: datetime
    updated_at: datetime


class Response(BaseModel):
    """Response model - optimized"""
    model_config = ConfigDict(from_attributes=True, extra="ignore", str_strip_whitespace=True)
    
    id: UUID
    attempt_id: UUID
    question_id: UUID
    answer_text: Optional[str] = None
    selected_option: Optional[int] = None
    status: str = "pending"
    score: float = 0.0
    max_score: float = 0.0
    feedback: Optional[str] = None
    feedback_json: Optional[Dict[str, Any]] = None
    auto_scored: bool = False
    scored_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class Result(BaseModel):
    """Result model - optimized"""
    model_config = ConfigDict(from_attributes=True, extra="ignore", str_strip_whitespace=True)
    
    id: UUID
    attempt_id: UUID
    user_id: UUID
    assessment_id: UUID
    total_score: float = 0.0
    max_score: float = 0.0
    percentage_score: float = 0.0
    passing_score: int = 60
    passed: bool = False
    section_scores: Optional[Dict[str, Any]] = None
    overall_feedback: Optional[str] = None
    feedback_json: Optional[Dict[str, Any]] = None
    report_url: Optional[str] = None
    generated_at: datetime
    created_at: datetime
    updated_at: datetime


class Embedding(BaseModel):
    """Embedding model - optimized"""
    model_config = ConfigDict(from_attributes=True, extra="ignore")
    
    id: UUID
    question_id: UUID
    embedding: List[float]
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime

