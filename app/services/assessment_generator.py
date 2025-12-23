"""
Service for automatically generating assessments from existing embeddings
Reads pdf_embeddings, generates questions, and creates assessments
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
        # Use service key for admin operations (creating assessments)
        # This bypasses RLS policies
        self.client = supabase_service.get_client(use_service_key=True)
        
        # Fallback to anon key if service key not available
        if not self.client:
            logger.warning("Service key client not available, falling back to anon key")
            logger.warning("Admin operations (creating assessments) may fail due to RLS")
            self.client = supabase_service.get_client(use_service_key=False)
    
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
    
    def get_chunks_for_source(self, pdf_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get text chunks for a specific PDF source
        
        Args:
            pdf_id: PDF document ID
            limit: Maximum number of chunks to retrieve
        
        Returns:
            List of chunks with text content
        """
        try:
            if not self.client:
                return []
            
            # OPTIMIZATION: Use correct column names from schema
            # Schema uses: chunk_text, chunk_index (not content, chunk_id)
            response = self.client.table("pdf_embeddings")\
                .select("id, chunk_text, chunk_index, pdf_title, page_number")\
                .eq("pdf_id", pdf_id)\
                .order("chunk_index")\
                .limit(limit)\
                .execute()
            
            chunks = []
            for row in response.data or []:
                chunks.append({
                    "chunk_text": row.get("chunk_text", ""),  # Use correct column name
                    "source_type": "pdf",
                    "source_id": pdf_id,
                    "source_name": row.get("pdf_title", pdf_id)
                })
            return chunks
            
        except Exception as e:
            logger.error(f"Error getting chunks for PDF {pdf_id}: {str(e)}")
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
    
    def extract_topic_from_source(self, source_name: str) -> str:
        """
        Extract topic/skill domain from PDF source name
        
        Uses the full PDF title to ensure each PDF gets its own unique course
        
        Args:
            source_name: PDF document name
        
        Returns:
            Extracted topic/skill domain
        """
        # Use full PDF title as skill_domain to ensure each PDF is unique
        # Clean up the title but keep it unique
        cleaned_title = source_name.strip()
        # Remove common prefixes/suffixes but keep the unique part
        if cleaned_title:
            return cleaned_title
        return f"PDF {source_name[:30]}" if source_name else "General PDF"
    
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
                        logger.info(f"[OK] Successfully inserted {len(batch_ids)} questions. IDs: {batch_ids[:3]}...")
                    else:
                        logger.warning(f"[WARN] Insert response has no data for batch {i//batch_size + 1}")
                except Exception as e:
                    logger.error(f"[FAILED] Error inserting questions batch {i//batch_size + 1}: {str(e)}")
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
        pdf_id: str,
        pdf_name: str,
        num_questions: int = 10
    ) -> Dict[str, Any]:
        """
        Generate questions for a specific PDF source
        
        Args:
            pdf_id: PDF document ID
            pdf_name: PDF document name
            num_questions: Number of questions to generate (default 10)
        
        Returns:
            Dictionary with success status and generated questions
        """
        try:
            # Get chunks for this PDF
            chunks = self.get_chunks_for_source(pdf_id, limit=30)
            
            if not chunks:
                logger.warning(f"No chunks found for PDF {pdf_id}")
                return {
                    "success": False,
                    "error": f"No content found for {pdf_name}"
                }
            
            # Extract topic from PDF name
            topic = self.extract_topic_from_source(pdf_name)
            
            # Determine difficulty
            difficulty = self.determine_difficulty_from_chunks(chunks)
            
            # Generate questions with mixed difficulty levels
            # Ensure at least 5 coding questions total
            num_questions = max(num_questions, 5)  # Ensure minimum 5 questions

            easy_count = max(1, num_questions // 3)  # At least 1 easy
            medium_count = max(2, (num_questions * 2) // 3)  # At least 2 medium
            hard_count = max(2, num_questions - easy_count - medium_count)  # At least 2 hard

            all_questions = []

            # Generate easy coding questions
            if easy_count > 0:
                easy_questions = topic_question_service.generate_questions_from_embeddings(
                    topic=topic,
                    chunks=chunks[:10],
                    num_questions=easy_count,
                    question_type="mcq",
                    difficulty="easy"
                )
                all_questions.extend(easy_questions)

            # Generate medium coding questions
            if medium_count > 0:
                medium_questions = topic_question_service.generate_questions_from_embeddings(
                    topic=topic,
                    chunks=chunks[:20],
                    num_questions=medium_count,
                    question_type="mcq",
                    difficulty="medium"
                )
                all_questions.extend(medium_questions)

            # Generate hard coding questions
            if hard_count > 0:
                hard_questions = topic_question_service.generate_questions_from_embeddings(
                    topic=topic,
                    chunks=chunks,
                    num_questions=hard_count,
                    question_type="mcq",
                    difficulty="hard"
                )
                all_questions.extend(hard_questions)

            # Ensure we have at least 5 questions
            if len(all_questions) < 5:
                # Generate additional questions to reach minimum
                additional_needed = 5 - len(all_questions)
                additional_questions = topic_question_service.generate_questions_from_embeddings(
                    topic=topic,
                    chunks=chunks,
                    num_questions=additional_needed,
                    question_type="mcq",
                    difficulty="medium"
                )
                all_questions.extend(additional_questions)
            
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
                        logger.info(f"[OK] Successfully inserted {len(batch_ids)} questions. IDs: {batch_ids[:3]}...")
                    else:
                        logger.warning(f"[WARN] Insert response has no data for batch {i//batch_size + 1}")
                except Exception as e:
                    logger.error(f"[FAILED] Error inserting questions batch {i//batch_size + 1}: {str(e)}")
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
                "source_name": pdf_name,
                "source_type": "pdf",
                "questions": all_questions,
                "question_ids": store_result.get("question_ids", []),
                "difficulty": difficulty
            }
            
        except Exception as e:
            logger.error(f"Error generating questions for PDF {pdf_id}: {str(e)}")
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
        question_count: int,
        course_id: Optional[str] = None,
        assessment_title: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Create an assessment entry in the assessments table
        
        Args:
            topic: Skill domain/topic
            source_name: Original PDF document name
            question_ids: List of question UUIDs
            difficulty: Average difficulty level
            question_count: Total number of questions
            course_id: Optional course ID to link assessment
            assessment_title: Optional custom assessment title (defaults to source_name)
        
        Returns:
            Created assessment record or None
        """
        try:
            # Ensure we're using service key client for admin operations
            # This bypasses RLS policies which block inserts with created_by=None
            if not self.client:
                self.client = supabase_service.get_client(use_service_key=True)
            
            if not self.client:
                logger.error("Supabase service client not available. Cannot create assessments.")
                logger.error("SOLUTION: Add SUPABASE_SERVICE_KEY to your .env file")
                return None
            
            # Calculate duration (1.5 minutes per question)
            duration_minutes = int(question_count * 1.5)
            
            # Use custom title if provided, otherwise use source_name
            title = assessment_title or source_name
            
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
                "title": title,
                "description": description,
                "skill_domain": topic,
                "difficulty": difficulty,
                "question_count": question_count,
                "duration_minutes": duration_minutes,
                "passing_score": 70,
                "status": "published",
                "blueprint": json.dumps(blueprint),
                "created_by": None,  # System-generated assessment
                "published_at": datetime.utcnow().isoformat()
            }
            
            # Add course_id if provided
            if course_id:
                assessment_data["course_id"] = course_id
            
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
            # Provide helpful error message
            if "row-level security" in str(e).lower():
                logger.error("SOLUTION: Ensure SUPABASE_SERVICE_KEY is set in .env file")
                logger.error("The service key bypasses RLS policies for admin operations")
            return None
    
    def generate_all_assessments(self) -> Dict[str, Any]:
        """
        Generate assessments from all existing PDF embeddings
        
        This function:
        1. Reads all PDF sources
        2. Generates questions for each PDF
        3. Creates assessment entries
        4. Stores everything in Supabase
        
        Returns:
            Dictionary with generation results
        """
        try:
            logger.info("Starting assessment generation from existing PDF embeddings")
            
            # Get all PDF sources
            pdf_sources = self.get_all_pdf_sources()
            
            if not pdf_sources:
                logger.warning("No PDF sources found in database")
                return {
                    "success": False,
                    "error": "No PDF sources found in database",
                    "generated": 0
                }
            
            logger.info(f"Found {len(pdf_sources)} PDF sources")
            
            generated_assessments = []
            failed_sources = []
            
            # Process each PDF source
            for source in pdf_sources:
                # Handle both old and new column names
                pdf_id = source.get("document_id") or source.get("pdf_id")
                pdf_name = source.get("document_name") or source.get("pdf_title", "Unknown")
                
                logger.info(f"Processing PDF: {pdf_name} (ID: {pdf_id})")
                
                # Generate questions
                result = self.generate_questions_for_source(
                    pdf_id=pdf_id,
                    pdf_name=pdf_name,
                    num_questions=10
                )
                
                if not result.get("success"):
                    logger.warning(f"Failed to generate questions for {pdf_name}: {result.get('error')}")
                    failed_sources.append({
                        "source": pdf_name,
                        "error": result.get("error")
                    })
                    continue
                
                question_ids = result.get("question_ids", [])
                topic = result.get("topic")
                difficulty = result.get("difficulty", "medium")
                question_count = len(result.get("questions", []))
                
                if not question_ids or question_count == 0:
                    logger.warning(f"No questions stored for {pdf_name}")
                    failed_sources.append({
                        "source": pdf_name,
                        "error": "Questions generated but not stored"
                    })
                    continue
                
                # Create assessment
                assessment = self.create_assessment_from_questions(
                    topic=topic,
                    source_name=pdf_name,
                    question_ids=question_ids,
                    difficulty=difficulty,
                    question_count=question_count
                )
                
                if assessment:
                    generated_assessments.append({
                        "assessment_id": assessment.get("id"),
                        "title": assessment.get("title"),
                        "topic": topic,
                        "source": pdf_name,
                        "question_count": question_count
                    })
                    logger.info(f"[OK] Created assessment: {assessment.get('title')}")
                else:
                    logger.warning(f"Failed to create assessment for {pdf_name}")
                    failed_sources.append({
                        "source": pdf_name,
                        "error": "Assessment creation failed"
                    })
            
            return {
                "success": True,
                "total_sources": len(pdf_sources),
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

