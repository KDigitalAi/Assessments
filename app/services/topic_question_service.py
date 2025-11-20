"""
Service for generating questions from topics using existing embeddings
Reuses embeddings from vimeo_video_chatbot project without re-processing
"""

from typing import List, Dict, Any, Optional
from openai import OpenAI
from app.config import settings
from app.services.supabase_service import supabase_service
from app.services.embedding_service import embedding_service
from app.services.rag_service import rag_service
from app.utils.logger import logger
import json


class TopicQuestionService:
    """Service for generating questions from topics using existing embeddings"""
    
    def __init__(self):
        """Initialize topic question service"""
        self.client = None
        self._initialize_openai_client()
    
    def _initialize_openai_client(self):
        """Initialize OpenAI client"""
        try:
            if settings.OPENAI_API_KEY and "your-openai" not in settings.OPENAI_API_KEY:
                self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
            else:
                logger.warning("OpenAI API key not configured. Question generation will not work.")
                self.client = None
        except Exception as e:
            logger.error(f"Error initializing OpenAI client: {str(e)}")
            self.client = None
    
    def fetch_embeddings_by_topic(
        self,
        topic: str,
        source_type: Optional[str] = None,  # 'video', 'pdf', or None for both
        match_threshold: float = 0.7,
        match_count: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Fetch relevant content chunks by topic using existing embeddings
        
        Args:
            topic: Topic or subject (e.g., "JavaScript", "React", "Machine Learning")
            source_type: Type of source ('video', 'pdf', or None for both)
            match_threshold: Similarity threshold (0-1)
            match_count: Maximum number of chunks to retrieve
        
        Returns:
            List of matched chunks with metadata
        """
        try:
            # Use existing RAG service to search for similar chunks
            # This reuses existing embeddings without re-processing
            chunks = rag_service.search_similar_chunks(
                query_text=topic,
                source_type=source_type,
                source_id=None,
                match_threshold=match_threshold,
                match_count=match_count
            )
            
            return chunks
            
        except Exception as e:
            logger.error(f"Error fetching embeddings by topic: {str(e)}")
            return []
    
    def generate_questions_from_embeddings(
        self,
        topic: str,
        chunks: List[Dict[str, Any]],
        num_questions: int = 5,
        question_type: str = "mcq",
        difficulty: str = "medium"
    ) -> List[Dict[str, Any]]:
        """
        Generate multiple-choice questions from retrieved content chunks
        
        Args:
            topic: Topic or subject
            chunks: List of relevant content chunks from embeddings
            num_questions: Number of questions to generate (5-10)
            question_type: Type of question ('mcq' or 'descriptive')
            difficulty: Difficulty level ('easy', 'medium', 'hard')
        
        Returns:
            List of generated questions with options and answers
        """
        try:
            if not self.client:
                logger.error("OpenAI client not initialized")
                return []
            
            if not chunks:
                logger.warning("No chunks provided for question generation")
                return []
            
            # Limit number of questions
            num_questions = min(max(num_questions, 5), 10)
            
            # Combine context chunks
            context_text = "\n\n".join([
                f"[{chunk.get('source_type', 'unknown').upper()} - {chunk.get('source_name', 'source')}]\n{chunk.get('chunk_text', '')}"
                for chunk in chunks[:10]  # Limit to top 10 chunks
            ])
            
            # Build prompt for MCQ generation
            if question_type == "mcq":
                prompt = f"""Based on the following content about {topic}, generate exactly {num_questions} multiple-choice questions at {difficulty} difficulty level.

Content:
{context_text}

For each question, provide:
1. A clear, concise question text
2. Four options (A, B, C, D) where only one is correct
3. The correct answer (A, B, C, or D)
4. A brief explanation of why the answer is correct

Format as JSON array with this exact structure:
[
  {{
    "question": "Question text here",
    "options": ["Option A text", "Option B text", "Option C text", "Option D text"],
    "correct_answer": "A",
    "explanation": "Brief explanation of the correct answer"
  }}
]

Ensure all questions are relevant to the topic "{topic}" and based on the provided content. Questions should test understanding, not just recall."""
            else:
                # Descriptive questions
                prompt = f"""Based on the following content about {topic}, generate exactly {num_questions} descriptive/open-ended questions at {difficulty} difficulty level.

Content:
{context_text}

For each question, provide:
1. A clear, thought-provoking question text
2. Key points that should be covered in a good answer

Format as JSON array with this exact structure:
[
  {{
    "question": "Question text here",
    "options": [],  # Empty for descriptive questions
    "correct_answer": "Key points that should be covered in the answer",
    "explanation": "Additional context or rubric if needed"
  }}
]

Ensure all questions are relevant to the topic "{topic}" and based on the provided content."""
            
            # Generate questions using OpenAI
            response = self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert question generator for educational assessments. Always respond with valid JSON only. Do not include markdown code blocks."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=3000
            )
            
            # Parse response
            content = response.choices[0].message.content.strip()
            
            # Try to extract JSON from markdown code blocks if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            questions = json.loads(content)
            
            # Ensure it's a list
            if not isinstance(questions, list):
                questions = [questions]
            
            # Add metadata and determine source type
            source_types = set(chunk.get('source_type') for chunk in chunks[:5])
            source_type = 'both' if len(source_types) > 1 else (list(source_types)[0] if source_types else None)
            
            # Get source_id from first chunk if available
            source_id = chunks[0].get('source_id') if chunks else None
            
            # Enhance questions with metadata
            for question in questions:
                question['topic'] = topic
                question['difficulty'] = difficulty
                question['source_type'] = source_type
                question['source_id'] = source_id
                question['question_type'] = question_type
            
            return questions
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing JSON response: {str(e)}")
            logger.error(f"Response content: {content[:500] if 'content' in locals() else 'N/A'}")
            return []
        except Exception as e:
            logger.error(f"Error generating questions from embeddings: {str(e)}")
            return []
    
    def store_questions(
        self,
        questions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Store generated questions in skill_assessment_questions table
        
        Args:
            questions: List of question dictionaries
        
        Returns:
            Dictionary with success status and stored question IDs
        """
        try:
            client = supabase_service.get_client()
            if not client:
                return {'success': False, 'error': 'Supabase client not available'}
            
            # Prepare records for insertion
            # Note: Do not store source_type or source_id as per user requirements
            records = []
            for question in questions:
                record = {
                    'topic': question.get('topic', ''),
                    'question': question.get('question', ''),
                    'options': question.get('options', []),
                    'correct_answer': question.get('correct_answer', ''),
                    'explanation': question.get('explanation', ''),
                    'difficulty': question.get('difficulty', 'medium')
                }
                records.append(record)
            
            if not records:
                return {'success': False, 'error': 'No questions to store'}
            
            # Insert in batches
            batch_size = 50
            inserted_ids = []
            
            for i in range(0, len(records), batch_size):
                batch = records[i:i + batch_size]
                try:
                    response = client.table('skill_assessment_questions').insert(batch).execute()
                    if response.data:
                        inserted_ids.extend([q.get('id') for q in response.data])
                except Exception as e:
                    logger.error(f"Error inserting questions batch: {str(e)}")
            
            return {
                'success': True,
                'inserted_count': len(inserted_ids),
                'question_ids': inserted_ids
            }
            
        except Exception as e:
            logger.error(f"Error storing questions: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def generate_and_store_questions(
        self,
        topic: str,
        source_type: Optional[str] = None,
        num_questions: int = 5,
        question_type: str = "mcq",
        difficulty: str = "medium",
        match_threshold: float = 0.7,
        match_count: int = 10
    ) -> Dict[str, Any]:
        """
        Complete workflow: Fetch embeddings → Generate questions → Store in database
        
        Args:
            topic: Topic or subject
            source_type: Type of source ('video', 'pdf', or None for both)
            num_questions: Number of questions to generate (5-10)
            question_type: Type of question ('mcq' or 'descriptive')
            difficulty: Difficulty level ('easy', 'medium', 'hard')
            match_threshold: Similarity threshold for retrieval
            match_count: Maximum number of chunks to retrieve
        
        Returns:
            Dictionary with success status and generated questions
        """
        try:
            # Step 1: Fetch relevant content using existing embeddings
            chunks = self.fetch_embeddings_by_topic(
                topic=topic,
                source_type=source_type,
                match_threshold=match_threshold,
                match_count=match_count
            )
            
            if not chunks:
                return {
                    'success': False,
                    'error': f'No relevant content found for topic: {topic}'
                }
            
            # Step 2: Generate questions from retrieved content
            questions = self.generate_questions_from_embeddings(
                topic=topic,
                chunks=chunks,
                num_questions=num_questions,
                question_type=question_type,
                difficulty=difficulty
            )
            
            if not questions:
                return {
                    'success': False,
                    'error': 'Failed to generate questions'
                }
            
            # Step 3: Store questions in database
            store_result = self.store_questions(questions)
            
            if not store_result.get('success'):
                return {
                    'success': False,
                    'error': store_result.get('error', 'Failed to store questions'),
                    'questions': questions  # Return questions even if storage failed
                }
            
            return {
                'success': True,
                'topic': topic,
                'questions': questions,
                'stored_count': store_result.get('inserted_count', 0),
                'question_ids': store_result.get('question_ids', [])
            }
            
        except Exception as e:
            logger.error(f"Error in generate_and_store_questions: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_questions_by_topic(
        self,
        topic: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Retrieve stored questions by topic
        
        Args:
            topic: Topic to filter by
            limit: Maximum number of questions to return
        
        Returns:
            List of questions
        """
        try:
            client = supabase_service.get_client()
            if not client:
                return []
            
            response = client.table('skill_assessment_questions')\
                .select('*')\
                .eq('topic', topic)\
                .order('created_at', desc=True)\
                .limit(limit)\
                .execute()
            
            return response.data if response.data else []
            
        except Exception as e:
            logger.error(f"Error retrieving questions by topic: {str(e)}")
            return []


# Global service instance
topic_question_service = TopicQuestionService()

