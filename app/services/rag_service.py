"""
RAG (Retrieval-Augmented Generation) service
Handles similarity search and context-aware question/answer generation
"""

from typing import List, Dict, Any, Optional
from openai import OpenAI
from app.config import settings
from app.services.supabase_service import supabase_service
from app.services.embedding_service import embedding_service
from app.utils.logger import logger


class RAGService:
    """Service for RAG-based question and answer generation"""
    
    def __init__(self):
        """Initialize RAG service"""
        self.client = None
        self._initialize_openai_client()
    
    def _initialize_openai_client(self):
        """Initialize OpenAI client"""
        try:
            if settings.OPENAI_API_KEY and "your-openai" not in settings.OPENAI_API_KEY:
                self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
                logger.info("OpenAI client initialized for RAG service")
            else:
                logger.warning("OpenAI API key not configured. RAG features will not work.")
                self.client = None
        except Exception as e:
            logger.error(f"Error initializing OpenAI client: {str(e)}")
            self.client = None
    
    def search_similar_chunks(
        self,
        query_text: str,
        source_type: Optional[str] = None,  # 'video', 'pdf', or None for both
        source_id: Optional[str] = None,  # Video ID or document ID
        match_threshold: float = 0.7,
        match_count: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search for similar chunks using vector similarity
        
        Args:
            query_text: Query text to search for
            source_type: Type of source ('video', 'pdf', or None for both)
            source_id: Specific source ID to filter by
            match_threshold: Similarity threshold (0-1)
            match_count: Maximum number of results
        
        Returns:
            List of similar chunks with metadata
        """
        try:
            # Generate query embedding
            query_embedding = embedding_service.generate_embedding(query_text)
            if not query_embedding:
                logger.error("Failed to generate query embedding")
                return []
            
            client = supabase_service.get_client()
            if not client:
                logger.error("Supabase client not available")
                return []
            
            # Use unified search function
            if source_type is None:
                # Search both video and PDF
                # Note: Function signature may vary - try with all parameters first
                try:
                    response = client.rpc(
                        'match_unified_embeddings',
                        {
                            'query_embedding': str(query_embedding),
                            'match_threshold': match_threshold,
                            'match_count': match_count,
                            'source_type': source_type
                        }
                    ).execute()
                except Exception as rpc_error:
                    # If parameter error, try without source_type (may not be in function signature)
                    error_msg = str(rpc_error).lower()
                    if 'parameter' in error_msg or 'function' in error_msg or 'pgrst' in error_msg:
                        logger.warning(f"RPC call with source_type failed, trying without: {str(rpc_error)[:100]}")
                        try:
                            response = client.rpc(
                                'match_unified_embeddings',
                                {
                                    'query_embedding': str(query_embedding),
                                    'match_threshold': match_threshold,
                                    'match_count': match_count
                                }
                            ).execute()
                        except Exception as rpc_error2:
                            # Try with just required parameters (match_count, query_embedding)
                            logger.warning(f"RPC call failed, trying minimal parameters: {str(rpc_error2)[:100]}")
                            response = client.rpc(
                                'match_unified_embeddings',
                                {
                                    'match_count': match_count,
                                    'query_embedding': str(query_embedding),
                                    'match_threshold': match_threshold
                                }
                            ).execute()
                    else:
                        raise
                
                chunks = response.data if response.data else []
                
                # Filter by source_id if provided
                if source_id:
                    chunks = [c for c in chunks if c.get('source_id') == source_id]
                
                return chunks
                
            elif source_type == 'video':
                # Search only video embeddings
                response = client.rpc(
                    'match_video_embeddings',
                    {
                        'query_embedding': str(query_embedding),
                        'match_threshold': match_threshold,
                        'match_count': match_count,
                        'filter_video_id': source_id
                    }
                ).execute()
                
                chunks = response.data if response.data else []
                
                # Convert to unified format
                return [{
                    'id': c.get('id'),
                    'source_type': 'video',
                    'source_id': c.get('video_id'),
                    'source_name': c.get('video_title', c.get('video_id')),
                    'chunk_text': c.get('chunk_text'),
                    'chunk_index': c.get('chunk_index'),
                    'start_time': c.get('start_time'),
                    'end_time': c.get('end_time'),
                    'similarity': c.get('similarity')
                } for c in chunks]
                
            elif source_type == 'pdf':
                # Search only PDF embeddings
                # Note: Use pdf_id instead of document_id, and handle both column name variations
                filter_doc_id = source_id if source_id else None
                
                # Try RPC function first, but fallback to direct query if RPC fails
                try:
                    response = client.rpc(
                        'match_documents',
                        {
                            'query_embedding': str(query_embedding),
                            'match_threshold': match_threshold,
                            'match_count': match_count,
                            'filter_document_id': filter_doc_id
                        }
                    ).execute()
                    
                    chunks = response.data if response.data else []
                    
                    # Convert to unified format - handle both old and new column names
                    return [{
                        'id': c.get('id'),
                        'source_type': 'pdf',
                        # Handle both pdf_id and document_id (RPC might return either)
                        'source_id': c.get('pdf_id') or c.get('document_id'),
                        # Handle both pdf_title and document_name
                        'source_name': c.get('pdf_title') or c.get('document_name'),
                        # Handle both content and chunk_text
                        'chunk_text': c.get('content') or c.get('chunk_text'),
                        'chunk_index': c.get('chunk_id') or c.get('chunk_index'),
                        'page_number': c.get('page_number'),
                        'similarity': c.get('similarity')
                    } for c in chunks]
                except Exception as rpc_error:
                    # Fallback: Direct query to pdf_embeddings table
                    logger.warning(f"RPC match_documents failed, using direct query: {str(rpc_error)[:100]}")
                    query = client.table("pdf_embeddings")\
                        .select("id, content, pdf_id, pdf_title, chunk_id, page_number")\
                        .limit(match_count)
                    
                    if filter_doc_id:
                        query = query.eq("pdf_id", filter_doc_id)
                    
                    response = query.execute()
                    chunks = response.data if response.data else []
                    
                    # For direct query, we need to calculate similarity manually or use a simpler approach
                    # For now, return chunks with similarity = 1.0 (we can't calculate without embedding)
                    return [{
                        'id': c.get('id'),
                        'source_type': 'pdf',
                        'source_id': c.get('pdf_id'),
                        'source_name': c.get('pdf_title'),
                        'chunk_text': c.get('content'),
                        'chunk_index': c.get('chunk_id'),
                        'page_number': c.get('page_number'),
                        'similarity': 1.0  # Placeholder since we can't calculate without vector search
                    } for c in chunks]
            
            return []
            
        except Exception as e:
            logger.error(f"Error searching similar chunks: {str(e)}")
            return []
    
    def generate_question_from_context(
        self,
        context_chunks: List[Dict[str, Any]],
        question_type: str = "general",
        difficulty: str = "medium",
        num_questions: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Generate questions from retrieved context chunks
        
        Args:
            context_chunks: List of relevant chunks from similarity search
            question_type: Type of question ('mcq', 'descriptive', 'general')
            difficulty: Difficulty level ('easy', 'medium', 'hard')
            num_questions: Number of questions to generate
        
        Returns:
            List of generated questions
        """
        try:
            if not self.client:
                logger.error("OpenAI client not initialized")
                return []
            
            if not context_chunks:
                logger.warning("No context chunks provided")
                return []
            
            # Combine context chunks
            context_text = "\n\n".join([
                f"[{chunk.get('source_type', 'unknown').upper()} - {chunk.get('source_name', 'source')}]\n{chunk.get('chunk_text', '')}"
                for chunk in context_chunks[:10]  # Limit to top 10 chunks
            ])
            
            # Build prompt based on question type
            if question_type == "mcq":
                prompt = f"""Based on the following context from videos and documents, generate {num_questions} multiple-choice question(s) at {difficulty} difficulty level.

Context:
{context_text}

For each question, provide:
1. Question text
2. Four options (A, B, C, D)
3. Correct answer (A, B, C, or D)
4. Brief explanation

Format as JSON array with this structure:
[
  {{
    "question": "Question text here",
    "options": ["Option A", "Option B", "Option C", "Option D"],
    "correct_answer": "A",
    "explanation": "Brief explanation"
  }}
]
"""
            elif question_type == "descriptive":
                prompt = f"""Based on the following context from videos and documents, generate {num_questions} descriptive/open-ended question(s) at {difficulty} difficulty level.

Context:
{context_text}

For each question, provide:
1. Question text
2. Suggested answer points or rubric

Format as JSON array with this structure:
[
  {{
    "question": "Question text here",
    "suggested_answer": "Key points that should be covered in the answer",
    "rubric": {{
      "max_points": 10,
      "criteria": ["Criterion 1", "Criterion 2"]
    }}
  }}
]
"""
            else:
                prompt = f"""Based on the following context from videos and documents, generate {num_questions} question(s) at {difficulty} difficulty level.

Context:
{context_text}

Format as JSON array with this structure:
[
  {{
    "question": "Question text here",
    "type": "mcq or descriptive",
    "options": ["Option A", "Option B", "Option C", "Option D"] (if MCQ),
    "correct_answer": "A or answer text",
    "explanation": "Brief explanation"
  }}
]
"""
            
            # Generate questions using OpenAI
            response = self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "You are an expert question generator. Always respond with valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=2000
            )
            
            # Parse response
            import json
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
            
            # Add metadata
            for question in questions:
                question['difficulty'] = difficulty
                question['source_chunks'] = [c.get('id') for c in context_chunks[:5]]  # Reference top 5 chunks
            
            return questions
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing JSON response: {str(e)}")
            logger.error(f"Response content: {content[:500]}")
            return []
        except Exception as e:
            logger.error(f"Error generating questions: {str(e)}")
            return []
    
    def generate_answer_from_context(
        self,
        question: str,
        context_chunks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Generate answer from retrieved context chunks
        
        Args:
            question: User's question
            context_chunks: List of relevant chunks from similarity search
        
        Returns:
            Dictionary with answer and metadata
        """
        try:
            if not self.client:
                logger.error("OpenAI client not initialized")
                return {'error': 'OpenAI client not available'}
            
            if not context_chunks:
                return {'error': 'No relevant context found'}
            
            # Combine context chunks
            context_text = "\n\n".join([
                f"[{chunk.get('source_type', 'unknown').upper()} - {chunk.get('source_name', 'source')}]\n{chunk.get('chunk_text', '')}"
                for chunk in context_chunks[:10]
            ])
            
            prompt = f"""Based on the following context from videos and documents, answer the user's question.

Context:
{context_text}

Question: {question}

Provide a comprehensive answer based on the context. If the context doesn't contain enough information, say so."""
            
            response = self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that answers questions based on provided context from videos and documents."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1000
            )
            
            answer = response.choices[0].message.content.strip()
            
            return {
                'answer': answer,
                'sources': [
                    {
                        'type': chunk.get('source_type'),
                        'id': chunk.get('source_id'),
                        'name': chunk.get('source_name'),
                        'similarity': chunk.get('similarity')
                    }
                    for chunk in context_chunks[:5]
                ]
            }
            
        except Exception as e:
            logger.error(f"Error generating answer: {str(e)}")
            return {'error': str(e)}
    
    def store_user_query(
        self,
        user_id: str,
        query_text: str,
        query_type: str = "general",
        source_type: Optional[str] = None,
        source_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Store user query in database
        
        Args:
            user_id: User ID
            query_text: Query text
            query_type: Type of query
            source_type: Source type
            source_id: Source ID
        
        Returns:
            Query ID or None
        """
        try:
            # Generate query embedding
            query_embedding = embedding_service.generate_embedding(query_text)
            
            client = supabase_service.get_client()
            if not client:
                return None
            
            data = {
                'user_id': user_id,
                'query_text': query_text,
                'query_type': query_type,
                'source_type': source_type,
                'source_id': source_id,
                'embedding': str(query_embedding) if query_embedding else None
            }
            
            response = client.table('user_queries').insert(data).execute()
            
            if response.data:
                return response.data[0].get('id')
            return None
            
        except Exception as e:
            logger.error(f"Error storing user query: {str(e)}")
            return None
    
    def store_chat_message(
        self,
        user_id: str,
        session_id: str,
        message_type: str,
        message_text: str,
        source_type: Optional[str] = None,
        source_id: Optional[str] = None,
        context_chunks: Optional[List[Dict[str, Any]]] = None
    ) -> Optional[str]:
        """
        Store chat message in history
        
        Args:
            user_id: User ID
            session_id: Session ID
            message_type: 'user' or 'assistant'
            message_text: Message text
            source_type: Source type
            source_id: Source ID
            context_chunks: Context chunks used
        
        Returns:
            Message ID or None
        """
        try:
            client = supabase_service.get_client()
            if not client:
                return None
            
            data = {
                'user_id': user_id,
                'session_id': session_id,
                'message_type': message_type,
                'message_text': message_text,
                'source_type': source_type,
                'source_id': source_id,
                'context_chunks': [c.get('id') for c in context_chunks] if context_chunks else None
            }
            
            response = client.table('chat_history').insert(data).execute()
            
            if response.data:
                return response.data[0].get('id')
            return None
            
        except Exception as e:
            logger.error(f"Error storing chat message: {str(e)}")
            return None


# Global service instance
rag_service = RAGService()

