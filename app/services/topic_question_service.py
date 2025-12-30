"""
Service for generating questions from topics using existing embeddings
Reuses PDF embeddings without re-processing
"""

from typing import List, Dict, Any, Optional
from openai import OpenAI
from app.config import settings
from app.services.supabase_service import supabase_service
from app.services.embedding_service import embedding_service
from app.services.rag_service import rag_service
from app.utils.logger import logger
import json
import re


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
        pdf_id: Optional[str] = None,
        match_threshold: float = 0.7,
        match_count: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Fetch relevant content chunks by topic using existing PDF embeddings
        
        Args:
            topic: Topic or subject (e.g., "JavaScript", "React", "Machine Learning")
            pdf_id: Optional PDF ID to filter by specific document
            match_threshold: Similarity threshold (0-1)
            match_count: Maximum number of chunks to retrieve
        
        Returns:
            List of matched chunks with metadata
        """
        try:
            # Use existing RAG service to search for similar chunks
            # This reuses existing PDF embeddings without re-processing
            chunks = rag_service.search_similar_chunks(
                query_text=topic,
                pdf_id=pdf_id,
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
            
            # Combine context chunks - CRITICAL: Only include chunk_text, exclude source_name/metadata
            # This prevents questions about PDF structure, module numbers, or document organization
            context_text = "\n\n".join([
                chunk.get('chunk_text', '').strip()
                for chunk in chunks[:10]  # Limit to top 10 chunks
                if chunk.get('chunk_text', '').strip()  # Only include non-empty chunks
            ])
            
            # Validate context_text is not empty
            if not context_text or not context_text.strip():
                logger.warning("No valid content text extracted from chunks. Cannot generate questions.")
                return []
            
            # Build prompt based on question type
            if question_type == "coding":
                # CODING QUESTIONS: Generate coding-related questions
                prompt = f"""Generate exactly {num_questions} CODING-RELATED multiple-choice questions at {difficulty} difficulty level based ONLY on the actual textual content provided below.

CONTENT TEXT (extracted from document):
{context_text}

CRITICAL INSTRUCTIONS - READ CAREFULLY:
1. Generate questions ONLY from the actual textual content above
2. Do NOT create questions about:
   - Module numbers (Module 1, Module 4, etc.)
   - Course structure or organization
   - Training outlines or curriculum
   - Document titles or file names
   - Section headings like "Module", "Lesson", "Chapter"
3. Questions must test:
   - Programming concepts explained in the content
   - Code examples and their behavior from the content
   - Syntax, algorithms, or logic described in the content
   - Implementation details or best practices from the content
4. Each question must be answerable ONLY by reading the content text above
5. Include code snippets IN THE QUESTION TEXT when relevant (use \\n for line breaks)

REQUIREMENTS:
- Generate CODING questions that test programming knowledge, code understanding, or implementation skills
- Question types: Code output prediction, code completion, bug detection, syntax questions, algorithm/logic questions
- Questions must be based on the actual content provided, not document structure

OUTPUT FORMAT - RESPOND WITH JSON ARRAY ONLY (no markdown, no code blocks):
[
  {{
    "question": "What will be the output of the following code?\\nint x = 5;\\nint y = x++ + ++x;\\nSystem.out.println(y);",
    "options": ["A) 10", "B) 11", "C) 12", "D) 13"],
    "correct_answer": "C",
    "explanation": "x++ returns 5 then increments to 6, ++x increments to 7 then returns 7. So y = 5 + 7 = 12",
    "question_type": "coding"
  }}
]

CRITICAL INSTRUCTIONS: 
- You MUST respond with ONLY a JSON array starting with [ and ending with ]
- Do NOT return code examples, code snippets, or any text outside the JSON array
- Do NOT use markdown code blocks (no ``` symbols)
- Code snippets must be INSIDE the question text as plain strings (use \\n for newlines)
- Return QUESTIONS ABOUT code in JSON format, not code examples
- Your response must be parseable as JSON immediately"""
            
            elif question_type == "theory":
                # THEORY QUESTIONS: Generate conceptual/theoretical questions
                prompt = f"""Generate exactly {num_questions} THEORETICAL/CONCEPTUAL multiple-choice questions at {difficulty} difficulty level based ONLY on the actual textual content provided below.

CONTENT TEXT (extracted from document):
{context_text}

CRITICAL INSTRUCTIONS - READ CAREFULLY:
1. Generate questions ONLY from the actual textual content above
2. Do NOT create questions about:
   - Module numbers (Module 1, Module 4, etc.)
   - Course structure or organization
   - Training outlines or curriculum
   - Document titles or file names
   - Section headings like "Module", "Lesson", "Chapter"
   - Course metadata or organizational structure
3. Questions must test:
   - Concepts and definitions explained in the content
   - Processes and procedures described in the content
   - Tools, technologies, or methods explained in the content
   - Behaviors, best practices, or principles from the content
4. Each question must be answerable ONLY by reading the content text above
5. If content is insufficient, generate conceptual questions based on explanations in the text

Question types to include:
1. Conceptual questions (What is the concept of...?)
2. Definition questions (What does X mean?)
3. Comparison questions (What is the difference between X and Y?)
4. Explanation questions (Why does X happen?)
5. Best practice questions (What is the best approach for...?)

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
    "explanation": "Brief explanation of the correct answer",
    "question_type": "theory"
  }}
]

FORBIDDEN QUESTION PATTERNS (DO NOT CREATE):
- "What is the focus of Module X?"
- "Which module covers..."
- "In this training..."
- "What does Module X teach?"
- Any question referencing module numbers, lessons, chapters, or course structure

RESPOND WITH JSON ONLY - No markdown, no explanations, no code blocks outside JSON
The entire response must be a valid JSON array that can be parsed directly"""
            
            elif question_type == "mcq":
                # DEFAULT/LEGACY: Standard MCQ (backward compatibility)
                prompt = f"""Generate exactly {num_questions} multiple-choice questions at {difficulty} difficulty level based ONLY on the actual textual content provided below.

CONTENT TEXT (extracted from document):
{context_text}

CRITICAL INSTRUCTIONS - READ CAREFULLY:
1. Generate questions ONLY from the actual textual content above
2. Do NOT create questions about:
   - Module numbers (Module 1, Module 4, etc.)
   - Course structure or organization
   - Training outlines or curriculum
   - Document titles or file names
   - Section headings like "Module", "Lesson", "Chapter"
3. Questions must test concepts, definitions, processes, tools, or behaviors explained in the content
4. Each question must be answerable ONLY by reading the content text above

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

FORBIDDEN QUESTION PATTERNS (DO NOT CREATE):
- "What is the focus of Module X?"
- "Which module covers..."
- "In this training..."
- Any question referencing module numbers, lessons, chapters, or course structure

RESPOND WITH JSON ONLY - No markdown, no explanations, no code blocks outside JSON
The entire response must be a valid JSON array that can be parsed directly"""
            
            else:
                # Descriptive questions
                prompt = f"""Generate exactly {num_questions} descriptive/open-ended questions at {difficulty} difficulty level based ONLY on the actual textual content provided below.

CONTENT TEXT (extracted from document):
{context_text}

CRITICAL INSTRUCTIONS - READ CAREFULLY:
1. Generate questions ONLY from the actual textual content above
2. Do NOT create questions about:
   - Module numbers (Module 1, Module 4, etc.)
   - Course structure or organization
   - Training outlines or curriculum
   - Document titles or file names
   - Section headings like "Module", "Lesson", "Chapter"
3. Questions must test:
   - Concepts and definitions explained in the content
   - Processes and procedures described in the content
   - Tools, technologies, or methods explained in the content
   - Behaviors, best practices, or principles from the content
4. Each question must be answerable ONLY by reading the content text above

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

FORBIDDEN QUESTION PATTERNS (DO NOT CREATE):
- "What is the focus of Module X?"
- "Which module covers..."
- "In this training..."
- Any question referencing module numbers, lessons, chapters, or course structure

RESPOND WITH JSON ONLY - No markdown, no explanations, no code blocks outside JSON
The entire response must be a valid JSON array that can be parsed directly"""
            
            # Generate questions using OpenAI
            # Use more explicit system message for coding questions
            system_message = "You are an expert question generator for educational assessments. You MUST respond with ONLY a valid JSON array. Do NOT include markdown code blocks, explanations, or any text outside the JSON. Code snippets must be INSIDE the JSON question text as strings (use \\n for newlines). The response must start with [ and end with ]."
            
            try:
                logger.debug(f"Calling OpenAI API for question generation (topic: {topic}, num_questions: {num_questions})")
                response = self.client.chat.completions.create(
                    model=settings.OPENAI_MODEL,
                    messages=[
                        {
                            "role": "system",
                            "content": system_message
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    temperature=0.7,
                    max_tokens=4000,  # Increased for coding questions with code snippets
                    timeout=60.0  # 60 second timeout for API call
                )
                logger.debug("OpenAI API call completed successfully")
            except TimeoutError as e:
                logger.error(f"OpenAI API call timed out after 60 seconds for topic: {topic}")
                raise
            except Exception as e:
                logger.exception(f"OpenAI API call failed for topic: {topic}")
                raise
            
            # Parse response
            if not response.choices or len(response.choices) == 0:
                logger.error("OpenAI API returned no choices in response")
                return []
            
            if not response.choices[0].message or not response.choices[0].message.content:
                logger.error("OpenAI API returned empty message content")
                return []
            
            logger.debug("OpenAI API response parsed successfully")
            content = response.choices[0].message.content.strip()
            
            # Check if response is just code (common error case)
            if content.startswith("python") or content.startswith("java") or content.startswith("javascript"):
                logger.warning(f"Model returned code snippet instead of JSON. Retrying with more explicit prompt...")
                # Retry with even more explicit prompt
                retry_prompt = prompt + "\n\nREMINDER: You must respond with a JSON array starting with [ and ending with ]. Do NOT return code examples. Return JSON questions ABOUT code."
                retry_response = self.client.chat.completions.create(
                    model=settings.OPENAI_MODEL,
                    messages=[
                        {
                            "role": "system",
                            "content": "You MUST respond with ONLY a JSON array. Start with [ and end with ]. No code blocks, no explanations."
                        },
                        {
                            "role": "user",
                            "content": retry_prompt
                        }
                    ],
                    temperature=0.5,  # Lower temperature for more consistent output
                    max_tokens=4000,
                    timeout=60.0  # 60 second timeout for retry
                )
                
                if not retry_response.choices or len(retry_response.choices) == 0:
                    logger.error("OpenAI API retry returned no choices in response")
                    return []
                
                if not retry_response.choices[0].message or not retry_response.choices[0].message.content:
                    logger.error("OpenAI API retry returned empty message content")
                    return []
                
                logger.debug("OpenAI API retry response parsed successfully")
                content = retry_response.choices[0].message.content.strip()
            
            # Try to extract JSON from markdown code blocks if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                # Check if it's a code block (not JSON)
                code_block_start = content.find("```")
                code_block_end = content.find("```", code_block_start + 3)
                if code_block_start != -1 and code_block_end != -1:
                    # Extract what's inside the code block
                    code_block_content = content[code_block_start + 3:code_block_end].strip()
                    # If it looks like JSON, use it; otherwise try to find JSON elsewhere
                    if code_block_content.strip().startswith("["):
                        content = code_block_content
                    else:
                        # Try to find JSON array elsewhere
                        json_start = content.find("[")
                        json_end = content.rfind("]")
                        if json_start != -1 and json_end != -1 and json_end > json_start:
                            content = content[json_start:json_end + 1]
                        else:
                            # Last resort: try to extract JSON from the entire content
                            json_match = re.search(r'\[.*\]', content, re.DOTALL)
                            if json_match:
                                content = json_match.group(0)
            
            # Clean up content - remove any leading/trailing non-JSON text
            content = content.strip()
            # Find the first [ and last ] to extract JSON array
            json_start = content.find("[")
            json_end = content.rfind("]")
            if json_start != -1 and json_end != -1 and json_end > json_start:
                content = content[json_start:json_end + 1]
            elif json_start == -1 or json_end == -1:
                # No JSON found - log error and return empty
                logger.error(f"No JSON array found in response. Content: {content[:200]}")
                return []
            
            # Parse JSON
            questions = json.loads(content)
            
            # Ensure it's a list
            if not isinstance(questions, list):
                questions = [questions]
            
            # VALIDATION FILTER: Reject questions that reference structural metadata
            # This prevents questions about modules, lessons, training structure, etc.
            forbidden_patterns = [
                r'\bmodule\s+\d+',  # "Module 1", "Module 4", etc.
                r'\bmodule\s+[ivx]+',  # "Module I", "Module IV", etc.
                r'\blesson\s+\d+',  # "Lesson 1", etc.
                r'\bchapter\s+\d+',  # "Chapter 1", etc.
                r'\bin\s+this\s+training',  # "In this training"
                r'\bin\s+this\s+course',  # "In this course"
                r'\bwhich\s+module',  # "Which module"
                r'\bwhat\s+is\s+the\s+focus\s+of\s+module',  # "What is the focus of Module X"
                r'\bthe\s+main\s+focus\s+of\s+module',  # "The main focus of Module X"
            ]
            
            filtered_questions = []
            rejected_count = 0
            
            for question in questions:
                question_text = question.get('question', '').lower()
                
                # Check if question contains forbidden patterns
                is_rejected = False
                for pattern in forbidden_patterns:
                    if re.search(pattern, question_text, re.IGNORECASE):
                        logger.warning(f"Rejected question containing structural metadata: {question.get('question', '')[:100]}")
                        is_rejected = True
                        rejected_count += 1
                        break
                
                # Also check for common structural terms in question text
                structural_terms = ['module', 'lesson', 'chapter', 'training', 'course structure']
                if not is_rejected:
                    # Only reject if these terms appear in a structural context
                    # (e.g., "Module 4" but not "module system" or "training data")
                    for term in structural_terms:
                        # Check for patterns like "Module X", "Lesson Y", etc.
                        if re.search(rf'\b{term}\s+\d+', question_text, re.IGNORECASE):
                            logger.warning(f"Rejected question containing structural term '{term}': {question.get('question', '')[:100]}")
                            is_rejected = True
                            rejected_count += 1
                            break
                
                if not is_rejected:
                    filtered_questions.append(question)
            
            questions = filtered_questions
            
            if rejected_count > 0:
                logger.info(f"Validation filter rejected {rejected_count} question(s) containing structural metadata")
            
            # If all questions were rejected, log warning but return empty list
            if not questions:
                logger.warning("All questions were rejected by validation filter. This may indicate content issues.")
                return []
            
            # Get pdf_id from first chunk if available
            pdf_id = chunks[0].get('source_id') if chunks else None
            
            # Enhance questions with metadata
            for question in questions:
                question['topic'] = topic
                question['difficulty'] = difficulty
                question['source_type'] = 'pdf'
                question['source_id'] = pdf_id
                # Ensure question_type is set (default to question_type parameter if not in response)
                if 'question_type' not in question:
                    question['question_type'] = question_type
            
            return questions
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing JSON response: {str(e)}")
            logger.error(f"Response content: {content[:500] if 'content' in locals() else 'N/A'}")
            
            # If we got code snippets instead of JSON, try one more time with a very explicit prompt
            if 'content' in locals() and (content.startswith("python") or content.startswith("java") or content.startswith("javascript") or "def " in content or "class " in content):
                logger.warning("Detected code snippet response. Attempting final retry with explicit JSON requirement...")
                try:
                    final_prompt = f"""Generate exactly {num_questions} coding questions as a JSON array.

Content: {context_text[:1000]}

Return ONLY a JSON array with this structure:
[
  {{"question": "Question with code", "options": ["A", "B", "C", "D"], "correct_answer": "A", "explanation": "Explanation", "question_type": "coding"}}
]

Start with [ and end with ]. No other text."""
                    
                    logger.debug("Calling OpenAI API for final retry attempt")
                    try:
                        final_response = self.client.chat.completions.create(
                            model=settings.OPENAI_MODEL,
                            messages=[
                                {"role": "system", "content": "You are a JSON generator. Return ONLY valid JSON arrays. No markdown, no code blocks, no explanations."},
                                {"role": "user", "content": final_prompt}
                            ],
                            temperature=0.3,
                            max_tokens=4000,
                            timeout=60.0  # 60 second timeout for final retry
                        )
                        
                        if not final_response.choices or len(final_response.choices) == 0:
                            logger.error("OpenAI API final retry returned no choices in response")
                            return []
                        
                        if not final_response.choices[0].message or not final_response.choices[0].message.content:
                            logger.error("OpenAI API final retry returned empty message content")
                            return []
                        
                        logger.debug("OpenAI API final retry response parsed successfully")
                        final_content = final_response.choices[0].message.content.strip()
                    except TimeoutError as e:
                        logger.error(f"OpenAI API final retry timed out after 60 seconds: {str(e)}")
                        return []
                    except Exception as e:
                        logger.exception(f"OpenAI API final retry failed: {str(e)}")
                        return []
                    # Extract JSON array
                    json_start = final_content.find("[")
                    json_end = final_content.rfind("]")
                    if json_start != -1 and json_end != -1:
                        final_content = final_content[json_start:json_end + 1]
                        questions = json.loads(final_content)
                        # Add metadata
                        for question in questions:
                            question['topic'] = topic
                            question['difficulty'] = difficulty
                            question['source_type'] = 'pdf'
                            question['source_id'] = chunks[0].get('source_id') if chunks else None
                            if 'question_type' not in question:
                                question['question_type'] = question_type
                        return questions
                except Exception as retry_error:
                    logger.error(f"Final retry also failed: {str(retry_error)}")
            
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
                    'difficulty': question.get('difficulty', 'medium'),
                    'question_type': question.get('question_type', 'theory')  # Include question_type (theory | coding)
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
                            response = client.table('skill_assessment_questions').insert(batch_without_type).execute()
                            if response.data:
                                inserted_ids.extend([q.get('id') for q in response.data])
                                logger.info(f"[OK] Successfully inserted {len(batch_without_type)} questions without question_type column")
                            else:
                                logger.warning(f"[WARN] Insert response has no data for batch {i//batch_size + 1}")
                        except Exception as retry_error:
                            logger.error(f"[FAILED] Error inserting questions batch {i//batch_size + 1}: {str(retry_error)}")
                    else:
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
        pdf_id: Optional[str] = None,
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
            pdf_id: Optional PDF ID to filter by specific document
            num_questions: Number of questions to generate (5-10)
            question_type: Type of question ('mcq' or 'descriptive')
            difficulty: Difficulty level ('easy', 'medium', 'hard')
            match_threshold: Similarity threshold for retrieval
            match_count: Maximum number of chunks to retrieve
        
        Returns:
            Dictionary with success status and generated questions
        """
        try:
            # Step 1: Fetch relevant content using existing PDF embeddings
            chunks = self.fetch_embeddings_by_topic(
                topic=topic,
                pdf_id=pdf_id,
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

