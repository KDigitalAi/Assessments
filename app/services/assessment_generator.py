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
import re


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
        
        Cleans structural metadata (module numbers, training structure) while preserving content topic
        
        Args:
            source_name: PDF document name
        
        Returns:
            Extracted topic/skill domain (cleaned of structural metadata)
        """
        if not source_name:
            return "General PDF"
        
        # Clean the title
        cleaned_title = source_name.strip()
        
        # Remove .pdf extension
        cleaned_title = re.sub(r'\.pdf$', '', cleaned_title, flags=re.IGNORECASE)
        
        # Remove module numbers and patterns like "Module 4:", "Module IV:", etc.
        cleaned_title = re.sub(r'\bmodule\s+\d+[:\s]*', '', cleaned_title, flags=re.IGNORECASE)
        cleaned_title = re.sub(r'\bmodule\s+[ivx]+[:\s]*', '', cleaned_title, flags=re.IGNORECASE)
        
        # Remove lesson numbers
        cleaned_title = re.sub(r'\blesson\s+\d+[:\s]*', '', cleaned_title, flags=re.IGNORECASE)
        
        # Remove chapter numbers
        cleaned_title = re.sub(r'\bchapter\s+\d+[:\s]*', '', cleaned_title, flags=re.IGNORECASE)
        
        # Remove leading numbers and separators (e.g., "4_", "10_", "1-")
        cleaned_title = re.sub(r'^\d+[_\-\s]+', '', cleaned_title)
        
        # Remove "Training", "Course", "Tutorial" prefixes if they're structural
        cleaned_title = re.sub(r'^(training|course|tutorial)[:\s]+', '', cleaned_title, flags=re.IGNORECASE)
        
        # Remove common structural prefixes
        cleaned_title = re.sub(r'^(for|on|about)\s+', '', cleaned_title, flags=re.IGNORECASE)
        
        # Clean up multiple spaces and trim
        cleaned_title = re.sub(r'\s+', ' ', cleaned_title).strip()
        
        # If title is empty after cleaning, use a generic name
        if not cleaned_title:
            cleaned_title = "Content Assessment"
        
        return cleaned_title
    
    def analyze_content_for_coding_suitability(self, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze embedding chunks to determine if content supports coding questions.
        
        This method examines the content to detect programming-related concepts,
        code examples, syntax, algorithms, and other coding indicators.
        
        Returns:
            Dictionary with:
            - supports_coding: bool - Whether content supports coding questions
            - coding_score: float (0.0 to 1.0) - Confidence score for coding content
            - coding_keywords_found: list - List of detected coding keywords
            - recommended_coding_count: int - Recommended number of coding questions (0-16)
        """
        if not chunks:
            return {
                "supports_coding": False,
                "coding_score": 0.0,
                "coding_keywords_found": [],
                "recommended_coding_count": 0
            }
        
        # Keywords that indicate coding/programming content
        coding_keywords = [
            # Code-related terms
            "code", "function", "method", "class", "variable", "syntax", "compile",
            "execute", "runtime", "algorithm", "data structure", "array", "list",
            "loop", "if", "else", "return", "import", "package", "module",
            # Programming concepts
            "programming", "implementation", "debug", "error", "exception",
            "try", "catch", "finally", "public", "private", "static", "void",
            "int", "string", "boolean", "object", "instance", "constructor",
            # Code patterns and control flow
            "for loop", "while loop", "switch", "case", "break", "continue",
            "recursion", "iteration", "polymorphism", "inheritance", "encapsulation",
            # Language-specific (Java, Python, JavaScript, etc.)
            "java", "python", "javascript", "c++", "c#", "typescript",
            # Code examples indicators
            "example", "sample code", "code snippet", "program", "application"
        ]
        
        # Combine all chunk text for analysis
        all_text = " ".join([
            chunk.get("chunk_text", "").lower() 
            for chunk in chunks[:20]  # Analyze top 20 chunks for efficiency
        ])
        
        # Count coding keywords found
        found_keywords = []
        keyword_count = 0
        for keyword in coding_keywords:
            if keyword.lower() in all_text:
                keyword_count += 1
                found_keywords.append(keyword)
        
        # Calculate coding score (0.0 to 1.0)
        # Higher score = more suitable for coding questions
        # Normalize based on number of unique keywords found
        coding_score = min(keyword_count / 15.0, 1.0)
        
        # Determine if content supports coding questions
        # Threshold: at least 30% coding indicators
        supports_coding = coding_score >= 0.3
        
        # Recommend coding question count based on score
        # Minimum 7 coding questions if content supports it
        if supports_coding:
            if coding_score >= 0.7:
                recommended_coding_count = 10  # High coding content - more coding questions
            elif coding_score >= 0.5:
                recommended_coding_count = 8   # Medium coding content
            else:
                recommended_coding_count = 7   # Minimum coding content - still generate 7
        else:
            recommended_coding_count = 0  # Theory only - no coding questions
        
        return {
            "supports_coding": supports_coding,
            "coding_score": coding_score,
            "coding_keywords_found": found_keywords[:10],  # Top 10 keywords
            "recommended_coding_count": recommended_coding_count
        }
    
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
        num_questions: int = 16  # Default to 16 questions as per requirement
    ) -> Dict[str, Any]:
        """
        Generate questions for a specific PDF source.
        
        This method generates 16 total questions with at least 7 coding questions
        when content supports it. The distribution is dynamic based on content analysis.
        
        Args:
            pdf_id: PDF document ID
            pdf_name: PDF document name
            num_questions: Number of questions to generate (default 16)
        
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
            
            # STEP 1: Analyze content for coding suitability
            content_analysis = self.analyze_content_for_coding_suitability(chunks)
            supports_coding = content_analysis["supports_coding"]
            recommended_coding_count = content_analysis["recommended_coding_count"]
            
            logger.info(f"Content analysis for {pdf_name}:")
            logger.info(f"  - Supports coding: {supports_coding}")
            logger.info(f"  - Coding score: {content_analysis['coding_score']:.2f}")
            logger.info(f"  - Recommended coding questions: {recommended_coding_count}")
            
            # STEP 2: Determine question distribution
            total_questions = num_questions  # Default 16
            
            if supports_coding:
                # Ensure at least 7 coding questions
                coding_count = max(7, recommended_coding_count)
                theory_count = total_questions - coding_count
                
                # Ensure we have at least some theory questions (minimum 3)
                if theory_count < 3:
                    theory_count = 3
                    coding_count = total_questions - theory_count
            else:
                # Fallback to theory-only if content doesn't support coding
                coding_count = 0
                theory_count = total_questions
                logger.info(f"Content does not support coding questions. Generating {theory_count} theory questions only.")
            
            all_questions = []
            
            # STEP 3: Generate theory questions (if needed)
            if theory_count > 0:
                # Distribute theory questions across difficulty levels
                theory_easy = max(1, theory_count // 3)
                theory_medium = max(1, (theory_count * 2) // 3)
                theory_hard = theory_count - theory_easy - theory_medium
                
                if theory_easy > 0:
                    theory_easy_q = topic_question_service.generate_questions_from_embeddings(
                        topic=topic,
                        chunks=chunks[:10],
                        num_questions=theory_easy,
                        question_type="theory",  # Specify theory type
                        difficulty="easy"
                    )
                    all_questions.extend(theory_easy_q)
                
                if theory_medium > 0:
                    theory_medium_q = topic_question_service.generate_questions_from_embeddings(
                        topic=topic,
                        chunks=chunks[:20],
                        num_questions=theory_medium,
                        question_type="theory",
                        difficulty="medium"
                    )
                    all_questions.extend(theory_medium_q)
                
                if theory_hard > 0:
                    theory_hard_q = topic_question_service.generate_questions_from_embeddings(
                        topic=topic,
                        chunks=chunks,
                        num_questions=theory_hard,
                        question_type="theory",
                        difficulty="hard"
                    )
                    all_questions.extend(theory_hard_q)
            
            # STEP 4: Generate coding questions (if content supports it)
            if coding_count > 0 and supports_coding:
                # Distribute coding questions across difficulty levels
                coding_easy = max(1, coding_count // 3)
                coding_medium = max(2, (coding_count * 2) // 3)
                coding_hard = coding_count - coding_easy - coding_medium
                
                if coding_easy > 0:
                    coding_easy_q = topic_question_service.generate_questions_from_embeddings(
                        topic=topic,
                        chunks=chunks[:10],
                        num_questions=coding_easy,
                        question_type="coding",  # Specify coding type
                        difficulty="easy"
                    )
                    all_questions.extend(coding_easy_q)
                
                if coding_medium > 0:
                    coding_medium_q = topic_question_service.generate_questions_from_embeddings(
                        topic=topic,
                        chunks=chunks[:20],
                        num_questions=coding_medium,
                        question_type="coding",
                        difficulty="medium"
                    )
                    all_questions.extend(coding_medium_q)
                
                if coding_hard > 0:
                    coding_hard_q = topic_question_service.generate_questions_from_embeddings(
                        topic=topic,
                        chunks=chunks,
                        num_questions=coding_hard,
                        question_type="coding",
                        difficulty="hard"
                    )
                    all_questions.extend(coding_hard_q)
            
            if not all_questions:
                return {
                    "success": False,
                    "error": "Failed to generate questions"
                }
            
            # Log final distribution
            coding_q_count = sum(1 for q in all_questions if q.get("question_type") == "coding")
            theory_q_count = sum(1 for q in all_questions if q.get("question_type") == "theory")
            logger.info(f"Generated {len(all_questions)} total questions:")
            logger.info(f"  - Coding questions: {coding_q_count}")
            logger.info(f"  - Theory questions: {theory_q_count}")
            
            # Store questions (without source_id and source_type as per user request)
            questions_to_store = []
            for q in all_questions:
                questions_to_store.append({
                    "topic": topic,
                    "question": q.get("question", ""),
                    "options": q.get("options", []),
                    "correct_answer": q.get("correct_answer", ""),
                    "explanation": q.get("explanation", ""),
                    "difficulty": q.get("difficulty", "medium"),
                    "question_type": q.get("question_type", "theory")  # Store question type (theory | coding)
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
                    error_str = str(e)
                    # Handle case where question_type column doesn't exist in database
                    if "question_type" in error_str.lower() and ("column" in error_str.lower() or "does not exist" in error_str.lower()):
                        logger.warning(f"[WARN] question_type column not found, retrying without it...")
                        # Remove question_type from batch and retry
                        batch_without_type = []
                        for q in batch:
                            q_copy = q.copy()
                            q_copy.pop("question_type", None)
                            batch_without_type.append(q_copy)
                        try:
                            response = self.client.table('skill_assessment_questions').insert(batch_without_type).execute()
                            if response.data:
                                batch_ids = [q.get('id') for q in response.data]
                                inserted_ids.extend(batch_ids)
                                logger.info(f"[OK] Successfully inserted {len(batch_ids)} questions without question_type column")
                            else:
                                logger.warning(f"[WARN] Insert response has no data for batch {i//batch_size + 1}")
                        except Exception as retry_error:
                            logger.error(f"[FAILED] Error inserting questions batch {i//batch_size + 1}: {str(retry_error)}")
                            import traceback
                            logger.error(traceback.format_exc())
                    else:
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
                "difficulty": difficulty,
                "coding_count": coding_q_count,
                "theory_count": theory_q_count,
                "total_count": len(all_questions)
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

