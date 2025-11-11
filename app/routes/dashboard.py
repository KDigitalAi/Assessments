"""
Unified Dashboard API endpoints for Skill Assessment frontend
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta
from pydantic import BaseModel, Field

from app.services.supabase_service import supabase_service
from app.services.topic_question_service import topic_question_service
from app.services.feedback_service import FeedbackService
from app.utils.logger import logger

# Initialize feedback service
feedback_service = FeedbackService()

router = APIRouter(prefix="/api", tags=["Dashboard"])


# ============================================
# Request/Response Models
# ============================================

class StartAssessmentRequest(BaseModel):
    skill_name: str = Field(..., description="Skill name (e.g., 'React', 'JavaScript')")
    num_questions: int = Field(5, ge=5, le=30, description="Number of questions")


class SubmitAssessmentRequest(BaseModel):
    attempt_id: UUID
    answers: List[Dict[str, Any]] = Field(..., description="List of answers with question_id and answer")


# ============================================
# API Endpoints
# ============================================

@router.get("/getAssessments")
async def get_assessments():
    """
    Get list of available assessments
    
    Returns assessments with:
    - Skill name
    - Question count
    - Duration
    - Difficulty level
    - User's current level
    - Market demand
    """
    try:
        client = supabase_service.get_client()
        if not client:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database service unavailable"
            )
        
        # Get all assessments (include published, active, draft, and NULL/empty status)
        # This ensures assessments are shown even if status column wasn't properly set
        try:
            # First, try to get all assessments without status filter
            all_assessments_response = client.table("assessments")\
                .select("*")\
                .execute()
            
            all_assessments = all_assessments_response.data if all_assessments_response.data else []
            
            # Filter to include: published, active, draft, NULL, empty, or any other status
            # Only exclude explicitly "archived" or "deleted" assessments
            assessments = [
                a for a in all_assessments
                if a.get("status") not in ("archived", "deleted")
            ]
            
            # If we still have no assessments, include everything (safety fallback)
            if not assessments and all_assessments:
                logger.warning("No assessments matched status filter, including all assessments")
                assessments = all_assessments
                
        except Exception as e:
            logger.error(f"Error fetching assessments: {str(e)}")
            # Fallback: try original query
            assessments_response = client.table("assessments")\
                .select("*")\
                .eq("status", "published")\
                .execute()
            assessments = assessments_response.data if assessments_response.data else []
        
        # Normalize domain name function
        def normalize_domain(raw_name: str) -> str:
            """Normalize course domain name.
            
            Handles:
            - Removes .pdf suffix: "python.pdf" -> "python"
            - Replaces underscores with spaces: "python_101" -> "python 101"
            - Trims whitespace
            - Capitalizes each word: "python datatypes" -> "Python Datatypes"
            """
            if not raw_name or not isinstance(raw_name, str):
                return "General"
            
            # Convert to lowercase and trim
            name = raw_name.strip().lower()
            
            # Remove .pdf suffix
            if name.endswith('.pdf'):
                name = name[:-4]
            
            # Replace underscores with spaces
            name = name.replace('_', ' ')
            
            # Trim again after replacements
            name = name.strip()
            
            if not name:
                return "General"
            
            # Capitalize each word (e.g., "python datatypes" -> "Python Datatypes")
            words = name.split()
            normalized_words = [word.capitalize() for word in words]
            
            return " ".join(normalized_words)
        
        # Group assessments by normalized skill_domain and count unique sources
        grouped_courses = {}
        
        for assessment in assessments:
            # Normalize skill_domain using the normalization function
            raw_skill = assessment.get("skill_domain", "Unknown")
            skill = normalize_domain(raw_skill)
            
            # Initialize course group if not exists
            if skill not in grouped_courses:
                grouped_courses[skill] = {
                    "skill_domain": skill,
                    "assessments": [],
                    "unique_sources": set()  # Track unique video/PDF sources
                }
            
            # Add assessment to course group
            grouped_courses[skill]["assessments"].append(assessment)
            
            # Try to extract source identifier from title or description
            # Since source_id is not stored, we'll use title patterns or query embeddings
            title = assessment.get("title", "").lower()
            # For now, we'll count unique assessment titles as a proxy for unique sources
            # This will be improved by querying embeddings tables
            assessment_id = assessment.get("id")
            if assessment_id:
                grouped_courses[skill]["unique_sources"].add(str(assessment_id))
        
        # Query embeddings tables to get actual unique source counts per course
        # Note: These tables may not exist, so we wrap in try-except
        try:
            # Get all unique video sources (if table exists)
            try:
                video_response = client.table("video_embeddings")\
                    .select("video_id, video_title")\
                    .execute()
                
                video_sources = {}
                if video_response.data:
                    for row in video_response.data:
                        video_id = row.get("video_id")
                        video_title = row.get("video_title", "")
                        if video_id:
                            # Normalize video title to match course names
                            normalized_video_title = normalize_domain(video_title)
                            if normalized_video_title not in video_sources:
                                video_sources[normalized_video_title] = set()
                            video_sources[normalized_video_title].add(video_id)
            except Exception as video_error:
                logger.debug(f"video_embeddings table not available or error: {str(video_error)}")
                video_sources = {}
            
            # Get all unique PDF sources (if table exists)
            try:
                pdf_response = client.table("pdf_embeddings")\
                    .select("pdf_id, pdf_title")\
                    .execute()
                
                pdf_sources = {}
                if pdf_response.data:
                    for row in pdf_response.data:
                        pdf_id = row.get("pdf_id")
                        pdf_title = row.get("pdf_title", "")
                        if pdf_id:
                            # Normalize PDF title to match course names
                            normalized_pdf_title = normalize_domain(pdf_title)
                            if normalized_pdf_title not in pdf_sources:
                                pdf_sources[normalized_pdf_title] = set()
                            pdf_sources[normalized_pdf_title].add(pdf_id)
            except Exception as pdf_error:
                logger.debug(f"pdf_embeddings table not available or error: {str(pdf_error)}")
                pdf_sources = {}
            
            # Update unique source counts for each course
            for skill, course_info in grouped_courses.items():
                # Count unique videos for this course
                video_count = len(video_sources.get(skill, set()))
                # Count unique PDFs for this course
                pdf_count = len(pdf_sources.get(skill, set()))
                # Total unique sources
                total_unique_sources = video_count + pdf_count
                
                # If we found sources in embeddings, use that; otherwise use assessment count as fallback
                if total_unique_sources > 0:
                    course_info["unique_source_count"] = total_unique_sources
                else:
                    # Fallback: count unique assessment titles (normalized)
                    unique_titles = set()
                    for a in course_info["assessments"]:
                        title = a.get("title", "")
                        if title:
                            # Normalize title to remove duplicates
                            normalized_title = normalize_domain(title)
                            unique_titles.add(normalized_title.lower())
                    course_info["unique_source_count"] = len(unique_titles) if unique_titles else 1
        except Exception as e:
            logger.warning(f"Could not query embeddings for source counts: {str(e)}")
            # Fallback: use assessment count
            for skill, course_info in grouped_courses.items():
                unique_titles = set()
                for a in course_info["assessments"]:
                    title = a.get("title", "")
                    if title:
                        normalized_title = normalize_domain(title)
                        unique_titles.add(normalized_title.lower())
                course_info["unique_source_count"] = len(unique_titles) if unique_titles else 1
        
        # Format response with course grouping and unique source counts
        formatted_courses = []
        for skill, course_info in grouped_courses.items():
            unique_count = course_info.get("unique_source_count", 1)
            progress = min(unique_count * 5, 100)
            
            formatted_courses.append({
                "skill_domain": skill,
                "skill_name": skill,  # For compatibility
                "test_count": unique_count,  # Number of unique video/PDF sources
                "progress": progress,
                "assessments": course_info["assessments"]  # All assessments for this course
            })
        
        # Format individual assessments for backward compatibility
        formatted_assessments = []
        for assessment in assessments:
            raw_skill = assessment.get("skill_domain", "Unknown")
            skill = normalize_domain(raw_skill)
            
            # Set default user level (no user tracking)
            user_level = 0
            
            # Mock market demand (in real app, this would come from analytics)
            market_demand = {
                "React": 95,
                "JavaScript": 90,
                "TypeScript": 85,
                "Problem Solving": 88,
                "Communication": 85,
                "Teamwork": 80,
                "Python": 90
            }.get(skill, 75)
            
            formatted_assessments.append({
                "id": assessment.get("id"),
                "skill_name": skill,
                "skill_domain": skill,
                "title": assessment.get("title"),
                "description": assessment.get("description"),
                "question_count": assessment.get("question_count", 10),
                "duration_minutes": assessment.get("duration_minutes", 30),
                "difficulty": assessment.get("difficulty", "medium"),
                "user_level": user_level,
                "market_demand": market_demand
            })
        
        return {
            "success": True,
            "assessments": formatted_assessments,  # For backward compatibility
            "courses": formatted_courses  # New format with unique source counts
        }
        
    except Exception as e:
        logger.error(f"Error getting assessments: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching assessments: {str(e)}"
        )


@router.get("/assessments/by_course/{course_name}")
async def get_assessments_by_course(course_name: str):
    """
    Get assessments filtered by course name (skill_domain)
    
    Args:
        course_name: Course/skill domain name (e.g., "Python", "DevOps")
    
    Returns:
        List of assessments for the specified course
    """
    try:
        client = supabase_service.get_client()
        if not client:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database service unavailable"
            )
        
        # Get assessments by skill_domain (course name) - CASE INSENSITIVE
        # Fetch all published assessments and filter case-insensitively
        assessments_response = client.table("assessments")\
            .select("*")\
            .eq("status", "published")\
            .execute()
        
        all_assessments = assessments_response.data if assessments_response.data else []
        
        # Filter by course name case-insensitively
        course_name_lower = course_name.strip().lower()
        assessments = [
            a for a in all_assessments 
            if (a.get("skill_domain") or "").strip().lower() == course_name_lower
        ]
        
        # Normalize domain name function (same as get_assessments)
        def normalize_domain(raw_name: str) -> str:
            """Normalize course domain name."""
            if not raw_name or not isinstance(raw_name, str):
                return "General"
            name = raw_name.strip().lower()
            if name.endswith('.pdf'):
                name = name[:-4]
            name = name.replace('_', ' ').strip()
            if not name:
                return "General"
            words = name.split()
            normalized_words = [word.capitalize() for word in words]
            return " ".join(normalized_words)
        
        # Normalize assessment title function (for deduplication)
        def normalize_assessment_title(raw_title: str) -> str:
            """Normalize assessment title to avoid duplicates.
            
            Handles:
            - Removes .pdf anywhere in the title
            - Replaces underscores and hyphens with spaces
            - Removes double spaces
            - Converts to title case
            """
            if not raw_title or not isinstance(raw_title, str):
                return "Untitled Assessment"
            
            # Convert to lowercase and trim
            title = raw_title.strip().lower()
            
            # Remove .pdf anywhere in the title (not just at the end)
            title = title.replace('.pdf', '')
            
            # Replace underscores and hyphens with spaces
            title = title.replace('_', ' ').replace('-', ' ')
            
            # Remove double spaces and trim
            title = " ".join(title.split())
            
            # Remove standalone "pdf" word (e.g., "html pdf assessment" -> "html assessment")
            words = title.split()
            words = [word for word in words if word != 'pdf']
            title = " ".join(words)
            
            if not title:
                return "Untitled Assessment"
            
            # Convert to title case (capitalize each word)
            words = title.split()
            normalized_words = [word.capitalize() for word in words]
            
            return " ".join(normalized_words)
        
        # Format assessments for frontend (normalize skill_domain and deduplicate by title)
        formatted_assessments = []
        seen_titles = {}  # Track normalized titles to avoid duplicates
        
        for assessment in assessments:
            # Normalize skill_domain using the normalization function
            raw_skill = assessment.get("skill_domain", "Unknown")
            normalized_skill = normalize_domain(raw_skill)
            
            # Normalize assessment title for deduplication
            raw_title = assessment.get("title") or assessment.get("assessment_title") or "Untitled Assessment"
            normalized_title = normalize_assessment_title(raw_title)
            
            # Create a unique key for deduplication (normalized title + skill_domain)
            title_key = normalized_title.lower()
            
            # Skip if we've already seen this normalized title for this course
            if title_key in seen_titles:
                logger.debug(f"Skipping duplicate assessment: '{raw_title}' (normalized: '{normalized_title}')")
                continue
            
            # Mark this title as seen
            seen_titles[title_key] = True
            
            formatted_assessments.append({
                "id": assessment.get("id"),
                "title": normalized_title,  # Use normalized title for display
                "original_title": raw_title,  # Keep original for reference
                "skill_name": normalized_skill,  # Normalized
                "skill_domain": normalized_skill,  # Normalized
                "description": assessment.get("description"),
                "question_count": assessment.get("question_count", 10),
                "duration_minutes": assessment.get("duration_minutes", 30),
                "difficulty": assessment.get("difficulty", "medium")
            })
        
        return {
            "success": True,
            "course_name": course_name,
            "assessments": formatted_assessments,
            "total": len(formatted_assessments)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting assessments by course: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting assessments by course: {str(e)}"
        )


@router.get("/assessments/{assessment_id}/questions")
async def get_assessment_questions(assessment_id: str):
    """
    Get questions for a specific assessment by assessment ID
    
    Returns questions from the assessment's blueprint or topic
    """
    try:
        client = supabase_service.get_client()
        if not client:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database service unavailable"
            )
        
        # Get assessment
        assessment_response = client.table("assessments")\
            .select("*")\
            .eq("id", assessment_id)\
            .eq("status", "published")\
            .limit(1)\
            .execute()
        
        assessment = assessment_response.data[0] if assessment_response.data else None
        if not assessment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assessment not found"
            )
        
        # Try to get questions from blueprint first
        blueprint = assessment.get("blueprint")
        question_ids = []
        
        if blueprint:
            try:
                import json
                blueprint_data = json.loads(blueprint) if isinstance(blueprint, str) else blueprint
                question_ids = blueprint_data.get("question_ids", [])
            except:
                pass
        
        # Get questions
        if question_ids:
            # Get questions by IDs from blueprint
            questions_response = client.table("skill_assessment_questions")\
                .select("*")\
                .in_("id", question_ids)\
                .execute()
            
            questions = questions_response.data if questions_response.data else []
        else:
            # Get questions by topic
            skill_domain = assessment.get("skill_domain", "")
            question_count = assessment.get("question_count", 10)
            
            questions_response = client.table("skill_assessment_questions")\
                .select("*")\
                .eq("topic", skill_domain)\
                .limit(question_count)\
                .execute()
            
            questions = questions_response.data if questions_response.data else []
        
        # Format questions for frontend (remove correct answers)
        formatted_questions = []
        for q in questions:
            formatted_questions.append({
                "id": q.get("id"),
                "question": q.get("question"),
                "options": q.get("options", []),
                "difficulty": q.get("difficulty", "medium")
            })
        
        # Create attempt for this assessment
        # Always create an attempt - ensure we have a user_id (required by schema)
        attempt = None
        attempt_id = None
        
        try:
            # Always use the single test user for Skill Capital
            from app.services.profile_service import get_test_user_id
            
            system_user_id = None
            try:
                # Get the test user - this will create it if it doesn't exist
                test_user_id = get_test_user_id()
                if test_user_id:
                    system_user_id = str(test_user_id)
                    logger.info(f"✅ Using test user for attempt: {system_user_id}")
                else:
                    logger.error("❌ Could not get test user. Attempt creation will fail.")
                    logger.error("   Please ensure auth.users has at least one user, then run the SQL in profile_service.py")
            except Exception as e:
                logger.error(f"❌ Error getting test user: {str(e)}")
                import traceback
                logger.error(traceback.format_exc())
            
            # Only create attempt if we have a user_id (required by schema)
            if system_user_id:
                attempt_data = {
                    "assessment_id": str(assessment_id),
                    "user_id": system_user_id,
                    "status": "in_progress",
                    "started_at": datetime.utcnow().isoformat(),
                    "duration_minutes": assessment.get("duration_minutes", 30),
                    "total_score": 0,
                    "max_score": len(formatted_questions),
                    "percentage_score": 0
                }
                
                logger.info(f"Creating attempt with user_id: {system_user_id}, assessment_id: {assessment_id}")
                
                try:
                    attempt_response = client.table("attempts").insert(attempt_data).execute()
                    attempt = attempt_response.data[0] if attempt_response.data else None
                    attempt_id = attempt.get("id") if attempt else None
                    
                    if not attempt_id:
                        logger.error("❌ Failed to create attempt - no ID returned")
                        logger.error(f"Insert response: {attempt_response.data if attempt_response else 'No response'}")
                        logger.error(f"Attempt data sent: {attempt_data}")
                    else:
                        logger.info(f"✅ Created attempt: {attempt_id} for assessment: {assessment_id}")
                        logger.info(f"✅ Attempt created successfully - questions can now be submitted")
                        
                        # Verify attempt was actually inserted
                        try:
                            verify_response = client.table("attempts")\
                                .select("id, status, assessment_id, user_id")\
                                .eq("id", attempt_id)\
                                .limit(1)\
                                .execute()
                            if verify_response.data:
                                logger.info(f"✅ Verified attempt exists in database: {verify_response.data[0]}")
                            else:
                                logger.error(f"❌ Attempt creation verification failed - attempt not found in database")
                        except Exception as verify_error:
                            logger.error(f"❌ Error verifying attempt: {str(verify_error)}")
                except Exception as insert_error:
                    logger.error(f"❌ Error inserting attempt: {str(insert_error)}")
                    import traceback
                    logger.error(traceback.format_exc())
                    attempt_id = None
            else:
                logger.error("❌ No user_id available - cannot create attempt. Submission will fail.")
                logger.error("⚠️  SOLUTION: Ensure at least one profile exists in the 'profiles' table.")
                logger.error("   Run create_test_user.sql in Supabase SQL Editor to create the test user.")
                # Still return questions, but attempt_id will be None
                attempt_id = None
        except Exception as e:
            logger.error(f"Could not create attempt: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            # Continue without attempt - frontend will handle this
            attempt = None
            attempt_id = None
        
        # Ensure attempt_id is always returned (even if null, frontend needs to know)
        response_data = {
            "success": True,
            "attempt_id": attempt_id,  # This can be None if attempt creation failed
            "assessment_id": str(assessment_id),
            "title": assessment.get("title") or assessment.get("skill_domain", "Assessment"),
            "questions": formatted_questions,
            "duration_minutes": assessment.get("duration_minutes", 30),
            "started_at": attempt.get("started_at") if attempt else datetime.utcnow().isoformat()
        }
        
        # Log warning if attempt_id is missing
        if not attempt_id:
            logger.error(f"❌ No attempt_id created for assessment {assessment_id}. Submission will fail.")
            logger.error("   This usually means no user profile exists in the database.")
            logger.error("   Please ensure at least one profile exists in the 'profiles' table.")
            # Still return questions so user can see them, but they can't submit
            response_data["error"] = "No attempt created. Please ensure at least one user profile exists in the database."
            response_data["warning"] = "Assessment loaded but submission may fail. Please create a user profile in Supabase."
        else:
            logger.info(f"✅ Successfully loaded assessment {assessment_id} with {len(formatted_questions)} questions and attempt_id: {attempt_id}")
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting assessment questions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting assessment questions: {str(e)}"
        )


@router.post("/startAssessment")
async def start_assessment(
    request: StartAssessmentRequest
):
    """
    Start an assessment and generate/fetch questions using existing embeddings
    
    Uses existing embeddings from vimeo_video_chatbot project to generate questions
    """
    try:
        # Generate a temporary user ID for session tracking (optional, can use None)
        # For no-auth mode, we'll use a session-based approach or skip user tracking
        user_id = None  # No user tracking in no-auth mode
        
        # Check if assessment exists for this skill, or create one
        client = supabase_service.get_client()
        if not client:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database service unavailable"
            )
        
        # Find or create assessment
        assessment_response = client.table("assessments")\
            .select("*")\
            .eq("skill_domain", request.skill_name)\
            .eq("status", "published")\
            .limit(1)\
            .execute()
        
        assessment = assessment_response.data[0] if assessment_response.data else None
        
        if not assessment:
            # Create assessment if it doesn't exist
            assessment_data = {
                "title": f"{request.skill_name} Assessment",
                "skill_domain": request.skill_name,
                "difficulty": "medium",
                "question_count": request.num_questions,
                "duration_minutes": 30,
                "passing_score": 60,
                "status": "published",
                "created_by": None  # No user tracking
            }
            
            assessment_response = client.table("assessments").insert(assessment_data).execute()
            assessment = assessment_response.data[0] if assessment_response.data else None
        
        assessment_id = UUID(assessment["id"])
        
        # Get questions from the assessment's blueprint or directly from skill_assessment_questions
        logger.info(f"Fetching questions for assessment: {assessment.get('title')}")
        
        # Try to get questions from blueprint first
        blueprint = assessment.get("blueprint")
        question_ids = []
        
        if blueprint:
            try:
                import json
                blueprint_data = json.loads(blueprint) if isinstance(blueprint, str) else blueprint
                question_ids = blueprint_data.get("question_ids", [])
            except:
                pass
        
        # If no question_ids from blueprint, get questions by topic
        if not question_ids:
            questions_response = client.table("skill_assessment_questions")\
                .select("*")\
                .eq("topic", request.skill_name)\
                .limit(request.num_questions)\
                .execute()
            
            questions = questions_response.data if questions_response.data else []
        else:
            # Get questions by IDs from blueprint
            questions_response = client.table("skill_assessment_questions")\
                .select("*")\
                .in_("id", question_ids[:request.num_questions])\
                .execute()
            
            questions = questions_response.data if questions_response.data else []
        
        # If still no questions, try to generate them (fallback)
        if not questions:
            logger.warning(f"No questions found for {request.skill_name}, generating new ones...")
            result = topic_question_service.generate_and_store_questions(
                topic=request.skill_name,
                source_type=None,
                num_questions=request.num_questions,
                question_type="mcq",
                difficulty="medium",
                match_threshold=0.7,
                match_count=10
            )
            
            if result.get("success") and result.get("question_ids"):
                questions_response = client.table("skill_assessment_questions")\
                    .select("*")\
                    .in_("id", result.get("question_ids", [])[:request.num_questions])\
                    .execute()
                
                questions = questions_response.data if questions_response.data else []
        
        # Create attempt - always use the test user
        from app.services.profile_service import get_test_user_id
        
        system_user_id = None
        try:
            # Get the test user - this will create it if it doesn't exist
            test_user_id = get_test_user_id()
            if test_user_id:
                system_user_id = str(test_user_id)
                logger.info(f"✅ Using test user for attempt: {system_user_id}")
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="No test user available. Cannot create assessment attempt. Please ensure auth.users has at least one user."
                )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"❌ Error getting test user: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error getting test user: {str(e)}"
            )
        
        attempt_data = {
            "assessment_id": str(assessment_id),
            "user_id": system_user_id,
            "status": "in_progress",
            "started_at": datetime.utcnow().isoformat(),
            "duration_minutes": assessment.get("duration_minutes", 30)
        }
        
        attempt_response = client.table("attempts").insert(attempt_data).execute()
        attempt = attempt_response.data[0] if attempt_response.data else None
        
        if not attempt:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create attempt"
            )
        
        logger.info(f"✅ Created attempt: {attempt.get('id')}")
        
        # Format questions for frontend (remove correct answers)
        formatted_questions = []
        for q in questions:
            formatted_questions.append({
                "id": q.get("id"),
                "question": q.get("question"),
                "options": q.get("options", []),
                "difficulty": q.get("difficulty", "medium")
            })
        
        return {
            "success": True,
            "attempt_id": attempt["id"],
            "assessment_id": str(assessment_id),
            "questions": formatted_questions,
            "duration_minutes": assessment.get("duration_minutes", 30),
            "started_at": attempt["started_at"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting assessment: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error starting assessment: {str(e)}"
        )


@router.post("/submitAssessment")
async def submit_assessment(
    request: SubmitAssessmentRequest
):
    """
    Submit assessment answers and calculate score
    """
    try:
        client = supabase_service.get_client()
        if not client:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database service unavailable"
            )
        
        # Verify attempt exists
        if not request.attempt_id:
            logger.error("❌ Missing attempt_id in submit request")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing attempt_id. Please start a new assessment."
            )
        
        attempt_id_str = str(request.attempt_id)
        logger.info(f"🔍 Looking for attempt: {attempt_id_str}")
        
        # Try to find the attempt - check both UUID and string format
        attempt_response = client.table("attempts")\
            .select("*")\
            .eq("id", attempt_id_str)\
            .limit(1)\
            .execute()
        
        attempt = attempt_response.data[0] if attempt_response.data and len(attempt_response.data) > 0 else None
        
        if not attempt:
            # Log available attempts for debugging
            logger.error(f"❌ Attempt not found: {attempt_id_str}")
            try:
                # Get a sample of recent attempts for debugging
                recent_attempts = client.table("attempts")\
                    .select("id, assessment_id, status, started_at")\
                    .order("started_at", desc=True)\
                    .limit(5)\
                    .execute()
                if recent_attempts.data:
                    logger.info(f"Recent attempts: {recent_attempts.data}")
            except:
                pass
            
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No active assessment attempt found for ID: {attempt_id_str}. Please start a new assessment."
            )
        
        logger.info(f"✅ Found attempt: {attempt.get('id')}, status: {attempt.get('status')}")
        
        # Check if attempt is already completed
        if attempt.get("status") == "completed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This assessment has already been submitted."
            )
        
        # Get correct answers for scoring
        question_ids = [str(ans.get("question_id")) for ans in request.answers]
        
        if not question_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No answers provided."
            )
        
        questions_response = client.table("skill_assessment_questions")\
            .select("id, question, correct_answer, explanation, options")\
            .in_("id", question_ids)\
            .execute()
        
        questions_dict = {str(q["id"]): q for q in (questions_response.data or [])}
        
        # Score answers and prepare detailed results
        total_score = 0
        max_score = len(request.answers)
        correct_count = 0
        results_data = []
        
        for answer in request.answers:
            question_id = str(answer.get("question_id"))
            user_answer = answer.get("answer", "").strip().upper()  # Normalize to uppercase
            question_data = questions_dict.get(question_id, {})
            correct_answer = question_data.get("correct_answer", "").strip().upper()
            
            is_correct = user_answer == correct_answer
            if is_correct:
                total_score += 1
                correct_count += 1
            
            # Prepare detailed result for each question
            results_data.append({
                "question_id": question_id,
                "question_text": question_data.get("question", ""),
                "selected_option": answer.get("answer", ""),
                "correct_answer": question_data.get("correct_answer", ""),
                "is_correct": is_correct,
                "explanation": question_data.get("explanation", "No explanation available.")
            })
        
        percentage_score = round((total_score / max_score * 100), 2) if max_score > 0 else 0
        
        # Save responses
        for answer in request.answers:
            question_id = str(answer.get("question_id"))
            user_answer = answer.get("answer", "").strip().upper()  # Normalize to uppercase
            question_data = questions_dict.get(question_id, {})
            correct_answer = question_data.get("correct_answer", "").strip().upper()
            is_correct = user_answer == correct_answer
            
            response_data = {
                "attempt_id": str(request.attempt_id),
                "question_id": question_id,
                "answer_text": user_answer,
                "score": 1 if is_correct else 0,
                "max_score": 1,
                "status": "scored"
            }
            
            client.table("responses").insert(response_data).execute()
        
        # Update attempt
        update_data = {
            "status": "completed",
            "completed_at": datetime.utcnow().isoformat(),
            "total_score": total_score,
            "max_score": max_score,
            "percentage_score": percentage_score
        }
        
        client.table("attempts")\
            .update(update_data)\
            .eq("id", str(request.attempt_id))\
            .execute()
        
        # Get assessment info for feedback generation
        assessment_id = attempt.get("assessment_id")
        skill_domain = None
        if assessment_id:
            try:
                assessment_response = client.table("assessments")\
                    .select("skill_domain, title")\
                    .eq("id", str(assessment_id))\
                    .limit(1)\
                    .execute()
                if assessment_response.data:
                    assessment = assessment_response.data[0]
                    skill_domain = assessment.get("skill_domain") or assessment.get("title")
            except Exception as e:
                logger.warning(f"Could not fetch assessment info for feedback: {str(e)}")
        
        # Generate personalized feedback
        feedback_message = None
        try:
            feedback_message = feedback_service.generate_feedback(
                score=total_score,
                max_score=max_score,
                percentage=percentage_score,
                passed=percentage_score >= 60,
                results=results_data,
                skill_domain=skill_domain
            )
            logger.info("✅ Generated personalized feedback")
        except Exception as e:
            logger.warning(f"Feedback generation failed: {str(e)}. Using fallback.")
            # Fallback will be handled by the service
        
        # Create result - use user_id from attempt (required by schema)
        user_id = attempt.get("user_id")
        if not user_id:
            logger.warning("⚠️  Attempt has no user_id - cannot create result record")
            # Still return success, but log warning
        else:
            result_data_db = {
                "attempt_id": str(request.attempt_id),
                "user_id": user_id,  # Use user_id from attempt
                "assessment_id": attempt.get("assessment_id"),
                "total_score": total_score,
                "max_score": max_score,
                "percentage_score": percentage_score,
                "passing_score": 60,
                "passed": percentage_score >= 60
            }
            
            # Add feedback if generated
            if feedback_message:
                result_data_db["overall_feedback"] = feedback_message
            
            try:
                client.table("results").insert(result_data_db).execute()
                logger.info(f"✅ Created result for attempt {request.attempt_id}")
            except Exception as e:
                logger.error(f"Could not create result: {str(e)}")
                # Continue anyway - result is still returned to frontend
        
        return {
            "success": True,
            "score": total_score,
            "max_score": max_score,
            "percentage_score": percentage_score,
            "passed": percentage_score >= 60,
            "correct_count": correct_count,
            "total_questions": max_score,
            "feedback": feedback_message,  # Include generated feedback
            "results": results_data  # Include detailed results for frontend
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting assessment: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error submitting assessment: {str(e)}"
        )


@router.get("/attempts/{attempt_id}/result")
async def get_attempt_result(attempt_id: str):
    """
    Get complete result data for a specific assessment attempt
    
    Returns:
    - Attempt details
    - Result summary
    - Detailed responses with correct/incorrect answers
    - Questions with explanations
    """
    try:
        client = supabase_service.get_client()
        if not client:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database service unavailable"
            )
        
        # Get attempt with result and assessment info
        attempt_response = client.table("attempts")\
            .select("*, results(*), assessments(*)")\
            .eq("id", attempt_id)\
            .limit(1)\
            .execute()
        
        if not attempt_response.data or len(attempt_response.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Attempt not found: {attempt_id}"
            )
        
        attempt = attempt_response.data[0]
        result = attempt.get("results")
        if isinstance(result, list) and result:
            result = result[0]
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No result found for attempt: {attempt_id}"
            )
        
        # Get all responses for this attempt
        responses_response = client.table("responses")\
            .select("*")\
            .eq("attempt_id", attempt_id)\
            .execute()
        
        responses = responses_response.data if responses_response.data else []
        
        # Get question IDs from responses
        question_ids = [str(r.get("question_id")) for r in responses if r.get("question_id")]
        
        # Fetch questions separately if we have question IDs
        questions_dict = {}
        if question_ids:
            questions_response = client.table("skill_assessment_questions")\
                .select("*")\
                .in_("id", question_ids)\
                .execute()
            
            questions_data = questions_response.data if questions_response.data else []
            questions_dict = {str(q.get("id")): q for q in questions_data}
        
        # Build detailed results with question info
        detailed_results = []
        for response in responses:
            question_id = str(response.get("question_id"))
            question = questions_dict.get(question_id)
            
            if question:
                # Use answer_text if available, otherwise selected_option
                answer_text = response.get("answer_text") or response.get("selected_option") or ""
                
                detailed_results.append({
                    "question_id": question_id,
                    "question_text": question.get("question", ""),
                    "selected_option": answer_text,
                    "correct_answer": question.get("correct_answer", ""),
                    "is_correct": response.get("score", 0) > 0,
                    "explanation": question.get("explanation", ""),
                    "options": question.get("options", [])
                })
        
        # Get assessment info
        assessment = attempt.get("assessments")
        if isinstance(assessment, dict):
            assessment_title = assessment.get("title", "Assessment")
            skill_domain = assessment.get("skill_domain", "Unknown")
        else:
            assessment_title = "Assessment"
            skill_domain = "Unknown"
        
        # Get feedback from result
        feedback = result.get("overall_feedback")
        
        # If no feedback exists, generate it now
        if not feedback:
            try:
                feedback = feedback_service.generate_feedback(
                    score=float(result.get("total_score", 0)),
                    max_score=float(result.get("max_score", 0)),
                    percentage=float(result.get("percentage_score", 0)),
                    passed=result.get("passed", False),
                    results=detailed_results,
                    skill_domain=skill_domain
                )
                # Optionally update the result with generated feedback
                if feedback:
                    try:
                        client.table("results")\
                            .update({"overall_feedback": feedback})\
                            .eq("id", result.get("id"))\
                            .execute()
                    except Exception as e:
                        logger.warning(f"Could not update feedback in database: {str(e)}")
            except Exception as e:
                logger.warning(f"Could not generate feedback: {str(e)}")
        
        return {
            "success": True,
            "attempt_id": attempt_id,
            "assessment_id": attempt.get("assessment_id"),
            "assessment_title": assessment_title,
            "skill_domain": skill_domain,
            "score": float(result.get("total_score", 0)),
            "max_score": float(result.get("max_score", 0)),
            "percentage_score": float(result.get("percentage_score", 0)),
            "passed": result.get("passed", False),
            "correct_count": sum(1 for r in detailed_results if r.get("is_correct")),
            "total_questions": len(detailed_results),
            "completed_at": attempt.get("completed_at"),
            "started_at": attempt.get("started_at"),
            "duration_minutes": attempt.get("duration_minutes", 30),
            "feedback": feedback,  # Include feedback
            "results": detailed_results
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting attempt result: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching result: {str(e)}"
        )


@router.get("/getProgress")
async def get_progress():
    """
    Get user's progress, stats, and recent assessments
    """
    try:
        client = supabase_service.get_client()
        if not client:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database service unavailable"
            )
        
        # Get test user ID for filtering (if available)
        from app.services.profile_service import get_test_user_id
        test_user_id = get_test_user_id()
        
        # Build query - filter by test user if available, otherwise get all completed attempts
        # Note: Join queries may fail if foreign keys aren't set up, so we handle errors gracefully
        try:
            # Try with join query first (more efficient if relationships exist)
            query = client.table("attempts")\
                .select("*, results(*), assessments(skill_domain, title)")\
                .eq("status", "completed")\
                .order("completed_at", desc=True)
            
            # Filter by test user if available (for single-user mode)
            if test_user_id:
                query = query.eq("user_id", str(test_user_id))
            
            attempts_response = query.limit(50).execute()
            attempts = attempts_response.data if attempts_response.data else []
        except Exception as join_error:
            # Fallback: query without joins if foreign key relationships don't exist
            logger.warning(f"Join query failed, trying without joins: {str(join_error)}")
            try:
                query = client.table("attempts")\
                    .select("*")\
                    .eq("status", "completed")\
                    .order("completed_at", desc=True)
                
                if test_user_id:
                    query = query.eq("user_id", str(test_user_id))
                
                attempts_response = query.limit(50).execute()
                attempts = attempts_response.data if attempts_response.data else []
                
                # Manually fetch related data if needed
                # (This is a simplified fallback - you may need to adjust based on your schema)
            except Exception as fallback_error:
                logger.error(f"Failed to fetch attempts even without joins: {str(fallback_error)}")
                attempts = []
        
        # Calculate stats
        total_assessments = len(attempts)
        scores = []
        skill_scores = {}
        recent_assessments = []
        
        for attempt in attempts[:10]:  # Recent 10
            # Handle results - could be a dict, list, or None depending on join success
            result = attempt.get("results")
            if result:
                if isinstance(result, list) and result:
                    result = result[0]
                elif not isinstance(result, dict):
                    result = None
            
            # Handle assessments - could be a dict, list, or None depending on join success
            assessment_data = attempt.get("assessments")
            if assessment_data:
                if isinstance(assessment_data, list) and assessment_data:
                    assessment_data = assessment_data[0]
                elif not isinstance(assessment_data, dict):
                    assessment_data = None
            
            # If we don't have assessment data from join, try to get it from assessment_id
            if not assessment_data and attempt.get("assessment_id"):
                try:
                    assessment_response = client.table("assessments")\
                        .select("skill_domain, title")\
                        .eq("id", str(attempt.get("assessment_id")))\
                        .limit(1)\
                        .execute()
                    if assessment_response.data:
                        assessment_data = assessment_response.data[0]
                except Exception:
                    assessment_data = None
            
            # If we don't have result data from join, try to get it from attempt_id
            if not result and attempt.get("id"):
                try:
                    result_response = client.table("results")\
                        .select("*")\
                        .eq("attempt_id", str(attempt.get("id")))\
                        .limit(1)\
                        .execute()
                    if result_response.data:
                        result = result_response.data[0]
                except Exception:
                    result = None
            
            if result and result.get("percentage_score") is not None:
                score = result["percentage_score"]
                scores.append(score)
                
                skill = assessment_data.get("skill_domain") if assessment_data else attempt.get("skill_domain", "Unknown")
                if skill not in skill_scores:
                    skill_scores[skill] = []
                skill_scores[skill].append(score)
                
                # Recent assessments
                recent_assessments.append({
                    "id": attempt.get("id"),
                    "skill_name": skill,
                    "title": assessment_data.get("title") if assessment_data else skill,
                    "score": score,
                    "max_score": 100,
                    "date": attempt.get("completed_at", attempt.get("started_at")),
                    "duration_minutes": attempt.get("duration_minutes", 30)
                    })
        
        avg_score = sum(scores) / len(scores) if scores else 0
        
        # Calculate skill progress (for bar chart)
        # Map skill domains to standard skill names for consistent display
        skill_name_mapping = {
            "React": "React",
            "JavaScript": "JavaScript",
            "TypeScript": "TypeScript",
            "Python": "Python",
            "Java": "Java",
            "Problem Solving": "Problem Solving",
            "Communication": "Communication",
            "Teamwork": "Teamwork",
            "Communication & Collaboration": "Teamwork"
        }
        
        # Standardize skill names and calculate averages
        standardized_skills = {}
        for skill, skill_scores_list in skill_scores.items():
            # Find matching standardized name
            standardized_name = skill
            for key, value in skill_name_mapping.items():
                if key.lower() in skill.lower():
                    standardized_name = value
                    break
            
            if standardized_name not in standardized_skills:
                standardized_skills[standardized_name] = []
            standardized_skills[standardized_name].extend(skill_scores_list)
        
        # Calculate user averages and target scores (market benchmarks)
        # Target scores are typically 10-15 points higher than user average
        skill_progress = {}
        for skill, skill_scores_list in standardized_skills.items():
            user_avg = int(sum(skill_scores_list) / len(skill_scores_list)) if skill_scores_list else 0
            # Market/target score: user average + 12 points (simulating market demand)
            # This can be adjusted or fetched from a separate benchmark table in the future
            target_score = min(100, user_avg + 12)
            
            skill_progress[skill] = {
                "user_level": user_avg,
                "target_level": target_score,
                "attempts": len(skill_scores_list)
            }
        
        # Calculate competency map (for radar chart)
        # Map skills to competency categories
        competency_categories = {
            "Technical Skills": ["React", "JavaScript", "TypeScript", "Python", "Java"],
            "Problem Solving": ["Problem Solving"],
            "Communication": ["Communication"],
            "Collaboration": ["Teamwork", "Communication & Collaboration"],
            "Learning Ability": []  # Calculated from overall performance
        }
        
        competency_scores = {}
        for category, related_skills in competency_categories.items():
            category_scores = []
            if category == "Learning Ability":
                # Learning ability is average of all skills
                category_scores = scores if scores else []
            else:
                # Find scores for related skills
                for skill, skill_scores_list in skill_scores.items():
                    if any(related_skill.lower() in skill.lower() for related_skill in related_skills):
                        category_scores.extend(skill_scores_list)
            
            if category_scores:
                competency_scores[category] = int(sum(category_scores) / len(category_scores))
            else:
                competency_scores[category] = 0
        
        return {
            "success": True,
            "total_assessments": total_assessments,
            "avg_score": round(avg_score, 1),
            "skill_progress": skill_progress,
            "competency_scores": competency_scores,
            "recent_assessments": recent_assessments[:5]  # Last 5
        }
        
    except Exception as e:
        logger.error(f"Error getting progress: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching progress: {str(e)}"
        )

