"""
Service for automatically generating assessments from existing embeddings
Reads video_embeddings and pdf_embeddings, generates questions, and creates assessments
"""

from typing import List, Dict, Any, Optional
from uuid import UUID, uuid4
from datetime import datetime
from app.services.supabase_service import supabase_service
from app.services.topic_question_service import topic_question_service
from app.utils.logger import logger
import json


class AssessmentGenerator:
    """Service for generating assessments from existing embeddings"""
    
    def __init__(self):
        """Initialize assessment generator"""
        self.client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize Supabase client"""
        self.client = supabase_service.get_client()
    
    def get_all_video_sources(self) -> List[Dict[str, Any]]:
        """
        Get all unique video sources from video_embeddings table
        
        Returns:
            List of unique video sources with metadata
        """
        try:
            if not self.client:
                logger.error("Supabase client not available")
                return []
            
            # Get distinct video IDs and titles
            response = self.client.table("video_embeddings")\
                .select("video_id, video_title")\
                .execute()
            
            if not response.data:
                return []
            
            # Get unique video sources
            unique_videos = {}
            for row in response.data:
                video_id = row.get("video_id")
                if video_id and video_id not in unique_videos:
                    unique_videos[video_id] = {
                        "video_id": video_id,
                        "video_title": row.get("video_title", f"Video {video_id}"),
                        "source_type": "video"
                    }
            
            logger.info(f"Found {len(unique_videos)} unique video sources")
            return list(unique_videos.values())
            
        except Exception as e:
            logger.error(f"Error getting video sources: {str(e)}")
            return []
    
    def get_all_pdf_sources(self) -> List[Dict[str, Any]]:
        """
        Get all unique PDF sources from pdf_embeddings table
        
        Returns:
            List of unique PDF sources with metadata
        """
        try:
            if not self.client:
                logger.error("Supabase client not available")
                return []
            
            # Get distinct document IDs and names
            # Note: Actual column names are pdf_id and pdf_title (not document_id/document_name)
            logger.info("Querying pdf_embeddings table...")
            response = self.client.table("pdf_embeddings")\
                .select("pdf_id, pdf_title")\
                .execute()
            
            logger.info(f"PDF embeddings query returned {len(response.data) if response.data else 0} rows")
            
            if not response.data:
                logger.warning("No data in pdf_embeddings table")
                return []
            
            # Get unique PDF sources
            unique_pdfs = {}
            for row in response.data:
                doc_id = row.get("pdf_id")
                if doc_id and doc_id not in unique_pdfs:
                    unique_pdfs[doc_id] = {
                        "document_id": doc_id,  # Keep for compatibility
                        "pdf_id": doc_id,
                        "document_name": row.get("pdf_title", f"Document {doc_id}"),  # Keep for compatibility
                        "pdf_title": row.get("pdf_title", f"Document {doc_id}"),
                        "source_type": "pdf"
                    }
            
            logger.info(f"Found {len(unique_pdfs)} unique PDF sources")
            return list(unique_pdfs.values())
            
        except Exception as e:
            logger.error(f"Error getting PDF sources: {str(e)}")
            return []
    
    def get_chunks_for_source(self, source_id: str, source_type: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get text chunks for a specific video or PDF source
        
        Args:
            source_id: Video ID or document ID
            source_type: 'video' or 'pdf'
            limit: Maximum number of chunks to retrieve
        
        Returns:
            List of chunks with text content
        """
        try:
            if not self.client:
                return []
            
            if source_type == "video":
                # Note: Actual column name is 'content' not 'chunk_text'
                response = self.client.table("video_embeddings")\
                    .select("id, content, chunk_id, video_title")\
                    .eq("video_id", source_id)\
                    .limit(limit)\
                    .execute()
                
                chunks = []
                for row in response.data or []:
                    chunks.append({
                        "chunk_text": row.get("content", ""),  # Map 'content' to 'chunk_text' for compatibility
                        "source_type": "video",
                        "source_id": source_id,
                        "source_name": row.get("video_title", source_id)
                    })
                return chunks
            
            elif source_type == "pdf":
                # Note: Actual column names are 'content', 'pdf_id', 'pdf_title' (not chunk_text, document_id, document_name)
                response = self.client.table("pdf_embeddings")\
                    .select("id, content, chunk_id, pdf_title, page_number")\
                    .eq("pdf_id", source_id)\
                    .limit(limit)\
                    .execute()
                
                chunks = []
                for row in response.data or []:
                    chunks.append({
                        "chunk_text": row.get("content", ""),  # Map 'content' to 'chunk_text' for compatibility
                        "source_type": "pdf",
                        "source_id": source_id,
                        "source_name": row.get("pdf_title", source_id)
                    })
                return chunks
            
            return []
            
        except Exception as e:
            logger.error(f"Error getting chunks for source {source_id}: {str(e)}")
            return []
    
    def determine_difficulty_from_chunks(self, chunks: List[Dict[str, Any]]) -> str:
        """
        Determine difficulty level based on content complexity
        
        Args:
            chunks: List of text chunks
        
        Returns:
            Difficulty level: 'easy', 'medium', or 'hard'
        """
        if not chunks:
            return "medium"
        
        # Simple heuristic: count technical terms, length, complexity
        total_length = sum(len(chunk.get("chunk_text", "")) for chunk in chunks)
        avg_length = total_length / len(chunks) if chunks else 0
        
        # Count technical indicators
        technical_terms = ["function", "class", "method", "algorithm", "implementation", 
                          "complexity", "optimization", "architecture", "pattern"]
        tech_count = sum(
            1 for chunk in chunks 
            for term in technical_terms 
            if term.lower() in chunk.get("chunk_text", "").lower()
        )
        
        # Determine difficulty
        if avg_length < 200 and tech_count < 3:
            return "easy"
        elif avg_length > 500 or tech_count > 8:
            return "hard"
        else:
            return "medium"
    
    def extract_topic_from_source(self, source_name: str, source_type: str) -> str:
        """
        Extract topic/skill domain from source name
        
        Args:
            source_name: Video title or document name
            source_type: 'video' or 'pdf'
        
        Returns:
            Extracted topic/skill domain
        """
        # Common skill domains
        skill_keywords = {
            "react": "React",
            "javascript": "JavaScript",
            "typescript": "TypeScript",
            "python": "Python",
            "java": "Java",
            "problem": "Problem Solving",
            "communication": "Communication",
            "teamwork": "Teamwork",
            "collaboration": "Communication & Collaboration"
        }
        
        source_lower = source_name.lower()
        
        # Try to match keywords
        for keyword, skill in skill_keywords.items():
            if keyword in source_lower:
                return skill
        
        # Fallback: extract from title or use generic
        if " " in source_name:
            # Use first significant word
            words = source_name.split()
            if len(words) > 0:
                return words[0].title()
        
        return source_name[:30] if source_name else "General"
    
    def generate_questions_from_chunks(
        self,
        chunks: List[Dict[str, Any]],
        topic: str,
        num_questions: int = 10
    ) -> Dict[str, Any]:
        """
        Generate questions directly from text chunks (for individual embeddings)
        
        Args:
            chunks: List of text chunks with content
            topic: Topic/skill domain
            num_questions: Number of questions to generate
        
        Returns:
            Dictionary with success status and generated questions
        """
        try:
            if not chunks:
                return {
                    "success": False,
                    "error": "No chunks provided"
                }
            
            # Determine difficulty
            difficulty = self.determine_difficulty_from_chunks(chunks)
            
            # Generate questions with mixed difficulty levels
            easy_count = num_questions // 3
            medium_count = (num_questions * 2) // 3
            hard_count = num_questions - easy_count - medium_count
            
            all_questions = []
            
            # Generate easy questions
            if easy_count > 0:
                easy_questions = topic_question_service.generate_questions_from_embeddings(
                    topic=topic,
                    chunks=chunks[:10],
                    num_questions=easy_count,
                    question_type="mcq",
                    difficulty="easy"
                )
                all_questions.extend(easy_questions)
            
            # Generate medium questions
            if medium_count > 0:
                medium_questions = topic_question_service.generate_questions_from_embeddings(
                    topic=topic,
                    chunks=chunks[:20] if len(chunks) > 20 else chunks,
                    num_questions=medium_count,
                    question_type="mcq",
                    difficulty="medium"
                )
                all_questions.extend(medium_questions)
            
            # Generate hard questions
            if hard_count > 0:
                hard_questions = topic_question_service.generate_questions_from_embeddings(
                    topic=topic,
                    chunks=chunks,
                    num_questions=hard_count,
                    question_type="mcq",
                    difficulty="hard"
                )
                all_questions.extend(hard_questions)
            
            if not all_questions:
                return {
                    "success": False,
                    "error": "Failed to generate questions"
                }
            
            # Store questions directly
            questions_to_store = []
            for q in all_questions:
                questions_to_store.append({
                    "topic": topic,
                    "question": q.get("question", ""),
                    "options": q.get("options", []),
                    "correct_answer": q.get("correct_answer", ""),
                    "explanation": q.get("explanation", ""),
                    "difficulty": q.get("difficulty", "medium")
                })
            
            # Store questions using Supabase client
            if not self.client:
                return {
                    "success": False,
                    "error": "Supabase client not available"
                }
            
            # Insert questions in batches
            batch_size = 50
            inserted_ids = []
            
            for i in range(0, len(questions_to_store), batch_size):
                batch = questions_to_store[i:i + batch_size]
                try:
                    logger.info(f"Inserting batch {i//batch_size + 1} with {len(batch)} questions...")
                    response = self.client.table('skill_assessment_questions').insert(batch).execute()
                    if response.data:
                        batch_ids = [q.get('id') for q in response.data]
                        inserted_ids.extend(batch_ids)
                        logger.info(f"✅ Successfully inserted {len(batch_ids)} questions. IDs: {batch_ids[:3]}...")
                    else:
                        logger.warning(f"⚠️  Insert response has no data for batch {i//batch_size + 1}")
                except Exception as e:
                    logger.error(f"❌ Error inserting questions batch {i//batch_size + 1}: {str(e)}")
                    import traceback
                    logger.error(traceback.format_exc())
            
            return {
                "success": len(inserted_ids) > 0,
                "topic": topic,
                "questions": all_questions,
                "question_ids": inserted_ids,
                "difficulty": difficulty
            }
            
        except Exception as e:
            logger.error(f"Error generating questions from chunks: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def generate_questions_for_source(
        self,
        source_id: str,
        source_name: str,
        source_type: str,
        num_questions: int = 10
    ) -> Dict[str, Any]:
        """
        Generate questions for a specific video or PDF source
        
        Args:
            source_id: Video ID or document ID
            source_name: Video title or document name
            source_type: 'video' or 'pdf'
            num_questions: Number of questions to generate (default 10)
        
        Returns:
            Dictionary with success status and generated questions
        """
        try:
            # Get chunks for this source
            chunks = self.get_chunks_for_source(source_id, source_type, limit=30)
            
            if not chunks:
                logger.warning(f"No chunks found for {source_type} {source_id}")
                return {
                    "success": False,
                    "error": f"No content found for {source_name}"
                }
            
            # Extract topic from source name
            topic = self.extract_topic_from_source(source_name, source_type)
            
            # Determine difficulty
            difficulty = self.determine_difficulty_from_chunks(chunks)
            
            # Generate questions with mixed difficulty levels
            # Generate 3 easy, 4 medium, 3 hard questions
            easy_count = num_questions // 3
            medium_count = (num_questions * 2) // 3
            hard_count = num_questions - easy_count - medium_count
            
            all_questions = []
            
            # Generate easy questions
            if easy_count > 0:
                easy_questions = topic_question_service.generate_questions_from_embeddings(
                    topic=topic,
                    chunks=chunks[:10],  # Use simpler chunks
                    num_questions=easy_count,
                    question_type="mcq",
                    difficulty="easy"
                )
                all_questions.extend(easy_questions)
            
            # Generate medium questions
            if medium_count > 0:
                medium_questions = topic_question_service.generate_questions_from_embeddings(
                    topic=topic,
                    chunks=chunks[:20],  # Use more chunks
                    num_questions=medium_count,
                    question_type="mcq",
                    difficulty="medium"
                )
                all_questions.extend(medium_questions)
            
            # Generate hard questions
            if hard_count > 0:
                hard_questions = topic_question_service.generate_questions_from_embeddings(
                    topic=topic,
                    chunks=chunks,  # Use all chunks
                    num_questions=hard_count,
                    question_type="mcq",
                    difficulty="hard"
                )
                all_questions.extend(hard_questions)
            
            if not all_questions:
                return {
                    "success": False,
                    "error": "Failed to generate questions"
                }
            
            # Store questions (without source_id and source_type as per user request)
            questions_to_store = []
            for q in all_questions:
                questions_to_store.append({
                    "topic": topic,
                    "question": q.get("question", ""),
                    "options": q.get("options", []),
                    "correct_answer": q.get("correct_answer", ""),
                    "explanation": q.get("explanation", ""),
                    "difficulty": q.get("difficulty", "medium")
                    # Note: source_type and source_id are NOT stored as per user requirements
                })
            
            # Store questions directly using Supabase client
            if not self.client:
                logger.error("Supabase client not available for storing questions")
                return {
                    "success": False,
                    "error": "Supabase client not available"
                }
            
            # Insert questions in batches
            batch_size = 50
            inserted_ids = []
            
            for i in range(0, len(questions_to_store), batch_size):
                batch = questions_to_store[i:i + batch_size]
                try:
                    logger.info(f"Inserting batch {i//batch_size + 1} with {len(batch)} questions...")
                    response = self.client.table('skill_assessment_questions').insert(batch).execute()
                    if response.data:
                        batch_ids = [q.get('id') for q in response.data]
                        inserted_ids.extend(batch_ids)
                        logger.info(f"✅ Successfully inserted {len(batch_ids)} questions. IDs: {batch_ids[:3]}...")
                    else:
                        logger.warning(f"⚠️  Insert response has no data for batch {i//batch_size + 1}")
                except Exception as e:
                    logger.error(f"❌ Error inserting questions batch {i//batch_size + 1}: {str(e)}")
                    import traceback
                    logger.error(traceback.format_exc())
            
            store_result = {
                "success": len(inserted_ids) > 0,
                "inserted_count": len(inserted_ids),
                "question_ids": inserted_ids
            }
            
            if not store_result.get("success"):
                logger.error(f"Failed to store questions: {store_result.get('error')}")
                return {
                    "success": False,
                    "error": "Failed to store questions",
                    "questions": all_questions
                }
            
            return {
                "success": True,
                "topic": topic,
                "source_name": source_name,
                "source_type": source_type,
                "questions": all_questions,
                "question_ids": store_result.get("question_ids", []),
                "difficulty": difficulty
            }
            
        except Exception as e:
            logger.error(f"Error generating questions for source {source_id}: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def create_assessment_from_questions(
        self,
        topic: str,
        source_name: str,
        question_ids: List[str],
        difficulty: str,
        question_count: int
    ) -> Optional[Dict[str, Any]]:
        """
        Create an assessment entry in the assessments table
        
        Args:
            topic: Skill domain/topic
            source_name: Original source name (video title or document name)
            question_ids: List of question UUIDs
            difficulty: Average difficulty level
            question_count: Total number of questions
        
        Returns:
            Created assessment record or None
        """
        try:
            if not self.client:
                logger.error("Supabase client not available")
                return None
            
            # Calculate duration (1.5 minutes per question)
            duration_minutes = int(question_count * 1.5)
            
            # Create description
            description = f"Assessment based on {source_name}. Test your knowledge with {question_count} multiple-choice questions."
            
            # Create blueprint (JSON structure)
            blueprint = {
                "question_distribution": {
                    "easy": question_count // 3,
                    "medium": (question_count * 2) // 3,
                    "hard": question_count - (question_count // 3) - ((question_count * 2) // 3)
                },
                "total_questions": question_count,
                "question_ids": question_ids
            }
            
            # Create assessment record
            assessment_data = {
                "title": f"{topic} Assessment",
                "description": description,
                "skill_domain": topic,
                "difficulty": difficulty,
                "question_count": question_count,
                "duration_minutes": duration_minutes,
                "passing_score": 70,
                "status": "published",
                "blueprint": json.dumps(blueprint),
                "created_by": None,  # No user in no-auth mode
                "published_at": datetime.utcnow().isoformat()
            }
            
            logger.info(f"Inserting assessment: {assessment_data.get('title')}")
            response = self.client.table("assessments").insert(assessment_data).execute()
            
            if response.data:
                assessment = response.data[0]
                assessment_id = assessment.get('id')
                logger.info(f"✅ Created assessment: {assessment_id} for topic: {topic}")
                return assessment
            else:
                logger.error(f"❌ Assessment insert response has no data")
                logger.error(f"   Assessment data: {assessment_data}")
                return None
            
        except Exception as e:
            logger.error(f"Error creating assessment: {str(e)}")
            return None
    
    def generate_all_assessments(self) -> Dict[str, Any]:
        """
        Generate assessments from all existing embeddings
        
        This function:
        1. Reads all video and PDF sources
        2. Generates questions for each source
        3. Creates assessment entries
        4. Stores everything in Supabase
        
        Returns:
            Dictionary with generation results
        """
        try:
            logger.info("Starting assessment generation from existing embeddings")
            
            # Get all sources
            video_sources = self.get_all_video_sources()
            pdf_sources = self.get_all_pdf_sources()
            
            all_sources = video_sources + pdf_sources
            
            if not all_sources:
                logger.warning("No video or PDF sources found in database")
                return {
                    "success": False,
                    "error": "No sources found in database",
                    "generated": 0
                }
            
            logger.info(f"Found {len(all_sources)} total sources ({len(video_sources)} videos, {len(pdf_sources)} PDFs)")
            
            generated_assessments = []
            failed_sources = []
            
            # Process each source
            for source in all_sources:
                # Handle both old and new column names
                source_id = source.get("video_id") or source.get("document_id") or source.get("pdf_id")
                source_name = source.get("video_title") or source.get("document_name") or source.get("pdf_title", "Unknown")
                source_type = source.get("source_type", "unknown")
                
                logger.info(f"Processing {source_type}: {source_name} (ID: {source_id})")
                
                # Generate questions
                result = self.generate_questions_for_source(
                    source_id=source_id,
                    source_name=source_name,
                    source_type=source_type,
                    num_questions=10
                )
                
                if not result.get("success"):
                    logger.warning(f"Failed to generate questions for {source_name}: {result.get('error')}")
                    failed_sources.append({
                        "source": source_name,
                        "error": result.get("error")
                    })
                    continue
                
                question_ids = result.get("question_ids", [])
                topic = result.get("topic")
                difficulty = result.get("difficulty", "medium")
                question_count = len(result.get("questions", []))
                
                if not question_ids or question_count == 0:
                    logger.warning(f"No questions stored for {source_name}")
                    failed_sources.append({
                        "source": source_name,
                        "error": "Questions generated but not stored"
                    })
                    continue
                
                # Create assessment
                assessment = self.create_assessment_from_questions(
                    topic=topic,
                    source_name=source_name,
                    question_ids=question_ids,
                    difficulty=difficulty,
                    question_count=question_count
                )
                
                if assessment:
                    generated_assessments.append({
                        "assessment_id": assessment.get("id"),
                        "title": assessment.get("title"),
                        "topic": topic,
                        "source": source_name,
                        "question_count": question_count
                    })
                    logger.info(f"✅ Created assessment: {assessment.get('title')}")
                else:
                    logger.warning(f"Failed to create assessment for {source_name}")
                    failed_sources.append({
                        "source": source_name,
                        "error": "Assessment creation failed"
                    })
            
            return {
                "success": True,
                "total_sources": len(all_sources),
                "generated": len(generated_assessments),
                "failed": len(failed_sources),
                "assessments": generated_assessments,
                "failed_sources": failed_sources
            }
            
        except Exception as e:
            logger.error(f"Error in generate_all_assessments: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "generated": 0
            }


# Global service instance
assessment_generator = AssessmentGenerator()

