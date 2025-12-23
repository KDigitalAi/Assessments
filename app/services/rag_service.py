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
            else:
                logger.warning("OpenAI API key not configured. RAG features will not work.")
                self.client = None
        except Exception as e:
            logger.error(f"Error initializing OpenAI client: {str(e)}")
            self.client = None
    
    def search_similar_chunks(
        self,
        query_text: str,
        pdf_id: Optional[str] = None,  # PDF document ID to filter by
        match_threshold: float = 0.7,
        match_count: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search for similar chunks using vector similarity from PDF embeddings
        
        Args:
            query_text: Query text to search for
            pdf_id: Specific PDF ID to filter by (optional)
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
            
            # Search PDF embeddings using new schema function
            # Try RPC function first, but fallback to direct query if RPC fails
            try:
                response = client.rpc(
                    'match_pdf_embeddings',
                    {
                        'query_embedding': str(query_embedding),
                        'match_threshold': match_threshold,
                        'match_count': match_count,
                        'filter_pdf_id': pdf_id
                    }
                ).execute()
                
                chunks = response.data if response.data else []
                
                # Convert to unified format
                return [{
                    'id': c.get('id'),
                    'source_type': 'pdf',
                    'source_id': c.get('pdf_id'),
                    'source_name': c.get('pdf_title'),
                    'chunk_text': c.get('chunk_text'),
                    'chunk_index': c.get('chunk_index'),
                    'page_number': c.get('page_number'),
                    'similarity': c.get('similarity')
                } for c in chunks]
            except Exception as rpc_error:
                # Fallback: Try old function name for backward compatibility
                try:
                    response = client.rpc(
                        'match_documents',
                        {
                            'query_embedding': str(query_embedding),
                            'match_threshold': match_threshold,
                            'match_count': match_count,
                            'filter_document_id': pdf_id
                        }
                    ).execute()
                    
                    chunks = response.data if response.data else []
                    return [{
                        'id': c.get('id'),
                        'source_type': 'pdf',
                        'source_id': c.get('pdf_id') or c.get('document_id'),
                        'source_name': c.get('pdf_title') or c.get('document_name'),
                        'chunk_text': c.get('chunk_text') or c.get('content'),
                        'chunk_index': c.get('chunk_index') or c.get('chunk_id'),
                        'page_number': c.get('page_number'),
                        'similarity': c.get('similarity', 1.0)
                    } for c in chunks]
                except Exception:
                    # Final fallback: Direct query (no similarity calculation)
                    logger.warning(f"RPC functions failed, using direct query: {str(rpc_error)[:100]}")
                    query = client.table("pdf_embeddings")\
                        .select("id, chunk_text, pdf_id, pdf_title, chunk_index, page_number")\
                        .limit(match_count)
                    
                    if pdf_id:
                        query = query.eq("pdf_id", pdf_id)
                    
                    response = query.execute()
                    chunks = response.data if response.data else []
                    
                    return [{
                        'id': c.get('id'),
                        'source_type': 'pdf',
                        'source_id': c.get('pdf_id'),
                        'source_name': c.get('pdf_title'),
                        'chunk_text': c.get('chunk_text'),
                        'chunk_index': c.get('chunk_index'),
                        'page_number': c.get('page_number'),
                        'similarity': 1.0  # Placeholder since we can't calculate without vector search
                    } for c in chunks]
            
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
                f"[{chunk.get('source_name', 'source')}]\n{chunk.get('chunk_text', '')}"
                for chunk in context_chunks[:10]  # Limit to top 10 chunks
            ])
            
            # Build prompt based on question type
            if question_type == "mcq":
                prompt = f"""Based on the following context from PDF documents, generate {num_questions} multiple-choice question(s) at {difficulty} difficulty level.

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
                prompt = f"""Based on the following context from PDF documents, generate {num_questions} descriptive/open-ended question(s) at {difficulty} difficulty level.

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
                prompt = f"""Based on the following context from PDF documents, generate {num_questions} question(s) at {difficulty} difficulty level.

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
                f"[{chunk.get('source_name', 'source')}]\n{chunk.get('chunk_text', '')}"
                for chunk in context_chunks[:10]
            ])
            
            prompt = f"""Based on the following context from PDF documents, answer the user's question.

Context:
{context_text}

Question: {question}

Provide a comprehensive answer based on the context. If the context doesn't contain enough information, say so."""
            
            response = self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that answers questions based on provided context from PDF documents."},
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
    
# Global service instance
rag_service = RAGService()

