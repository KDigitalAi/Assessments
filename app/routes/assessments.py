"""
API routes for assessment generation and management
"""

from fastapi import APIRouter, HTTPException, status
from typing import Dict, Any
from app.services.assessment_generator import assessment_generator
from app.utils.logger import logger

router = APIRouter(prefix="/api", tags=["Assessments"])


@router.post("/generateAssessments")
async def generate_assessments():
    """
    Generate assessments from all existing embeddings
    
    This endpoint:
    1. Reads all video_embeddings and pdf_embeddings
    2. Generates 10 MCQ questions for each source
    3. Categorizes questions by difficulty
    4. Stores questions in skill_assessment_questions
    5. Creates assessment entries in assessments table
    
    Returns:
        Generation results with created assessments
    """
    try:
        logger.info("Starting assessment generation from embeddings")
        
        result = assessment_generator.generate_all_assessments()
        
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to generate assessments")
            )
        
        return {
            "success": True,
            "message": f"Generated {result.get('generated', 0)} assessments from {result.get('total_sources', 0)} sources",
            "total_sources": result.get("total_sources", 0),
            "generated": result.get("generated", 0),
            "failed": result.get("failed", 0),
            "assessments": result.get("assessments", []),
            "failed_sources": result.get("failed_sources", [])
        }
        
    except Exception as e:
        logger.error(f"Error generating assessments: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating assessments: {str(e)}"
        )


@router.get("/assessments/stats")
async def get_assessment_stats():
    """
    Get statistics about generated assessments
    
    Returns:
        Statistics about assessments and questions
    """
    try:
        from app.services.supabase_service import supabase_service
        
        client = supabase_service.get_client()
        if not client:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database service unavailable"
            )
        
        # Count assessments - get all and count
        assessments_response = client.table("assessments")\
            .select("id")\
            .execute()
        
        assessment_count = len(assessments_response.data) if assessments_response.data else 0
        
        # Count questions - get all and count
        questions_response = client.table("skill_assessment_questions")\
            .select("id, difficulty")\
            .execute()
        
        question_count = len(questions_response.data) if questions_response.data else 0
        
        # Count by difficulty
        difficulty_counts = {"easy": 0, "medium": 0, "hard": 0}
        for q in (questions_response.data or []):
            diff = q.get("difficulty", "medium")
            if diff in difficulty_counts:
                difficulty_counts[diff] += 1
        
        return {
            "success": True,
            "total_assessments": assessment_count,
            "total_questions": question_count,
            "questions_by_difficulty": difficulty_counts
        }
        
    except Exception as e:
        logger.error(f"Error getting assessment stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting stats: {str(e)}"
        )


@router.post("/embeddings/sync")
async def sync_embeddings():
    """
    Sync embeddings: Convert all video_embeddings and pdf_embeddings into questions and assessments
    
    This endpoint:
    1. Reads all embeddings from video_embeddings and pdf_embeddings tables
    2. For each embedding chunk, generates a question using OpenAI
    3. Groups every 10 questions into an assessment
    4. Stores questions in skill_assessment_questions table
    5. Creates assessment entries in assessments table
    
    Returns:
        Success message with counts of generated questions and assessments
    """
    try:
        logger.info("Starting embeddings sync process...")
        
        # Use the assessment generator to process all embeddings
        result = assessment_generator.generate_all_assessments()
        
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to sync embeddings")
            )
        
        generated_count = result.get("generated", 0)
        total_sources = result.get("total_sources", 0)
        failed_count = result.get("failed", 0)
        
        logger.info(f"✅ Embeddings sync completed: {generated_count} assessments generated from {total_sources} sources")
        
        return {
            "success": True,
            "message": f"Successfully synced embeddings! Generated {generated_count} assessments from {total_sources} sources.",
            "total_sources": total_sources,
            "generated_assessments": generated_count,
            "failed_sources": failed_count,
            "assessments": result.get("assessments", []),
            "failed_sources_list": result.get("failed_sources", [])
        }
        
    except Exception as e:
        logger.error(f"Error syncing embeddings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error syncing embeddings: {str(e)}"
        )

