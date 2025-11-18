"""
Standalone script to generate assessments from PDF embeddings
Fetches all PDFs, generates 20 questions per PDF, and creates assessments

Requirements:
- .env file with SUPABASE_URL, SUPABASE_KEY, and OPENAI_API_KEY
- pdf_embeddings table with pdf_id and content columns
- assessments table (pdf_id is stored in blueprint JSON field)
- skill_assessment_questions table (uses source_id to link to PDFs)

Note: 
- pdf_id is stored in the assessments.blueprint JSON field
- Questions are linked to PDFs via skill_assessment_questions.source_id
- Questions have source_type='pdf' to identify PDF sources
"""

import os
import sys
import json
import time
from typing import List, Dict, Any, Optional
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client, Client
from openai import OpenAI

# Load environment variables
BASE_DIR = Path(__file__).resolve().parent
env_path = BASE_DIR / ".env"
load_dotenv(dotenv_path=env_path, override=True)

# Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Constants
NUM_QUESTIONS_PER_PDF = 20
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds


class AssessmentGenerator:
    """Standalone assessment generator for PDFs"""
    
    def __init__(self):
        """Initialize clients"""
        self.supabase_client: Optional[Client] = None
        self.openai_client: Optional[OpenAI] = None
        self._initialize_clients()
    
    def _initialize_clients(self):
        """Initialize Supabase and OpenAI clients"""
        # Initialize Supabase
        try:
            if not SUPABASE_URL or not SUPABASE_KEY:
                print("ERROR: SUPABASE_URL and SUPABASE_KEY must be set in .env file")
                sys.exit(1)
            
            if "your-project" in SUPABASE_URL.lower() or "your-supabase" in SUPABASE_KEY.lower():
                print("ERROR: Please configure actual Supabase credentials in .env file")
                sys.exit(1)
            
            self.supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
            print("✓ Supabase client initialized")
        except Exception as e:
            print(f"ERROR: Failed to initialize Supabase client: {str(e)}")
            sys.exit(1)
        
        # Initialize OpenAI
        try:
            if not OPENAI_API_KEY or "your-openai" in OPENAI_API_KEY.lower():
                print("ERROR: OPENAI_API_KEY must be set in .env file")
                sys.exit(1)
            
            self.openai_client = OpenAI(api_key=OPENAI_API_KEY)
            print("✓ OpenAI client initialized")
        except Exception as e:
            print(f"ERROR: Failed to initialize OpenAI client: {str(e)}")
            sys.exit(1)
    
    def fetch_all_pdf_ids(self) -> List[str]:
        """
        Fetch all unique PDF IDs from pdf_embeddings table
        
        Returns:
            List of unique PDF IDs
        """
        try:
            print("\n📋 Fetching all unique PDF IDs from pdf_embeddings...")
            
            # Query: select distinct pdf_id from pdf_embeddings
            response = self.supabase_client.table("pdf_embeddings")\
                .select("pdf_id")\
                .execute()
            
            if not response.data:
                print("⚠️  No PDFs found in pdf_embeddings table")
                return []
            
            # Get unique PDF IDs
            pdf_ids = list(set([row.get("pdf_id") for row in response.data if row.get("pdf_id")]))
            
            print(f"✓ Found {len(pdf_ids)} unique PDFs")
            return pdf_ids
            
        except Exception as e:
            print(f"ERROR: Failed to fetch PDF IDs: {str(e)}")
            return []
    
    def fetch_pdf_chunks(self, pdf_id: str) -> List[str]:
        """
        Fetch all content chunks for a specific PDF
        
        Args:
            pdf_id: PDF ID to fetch chunks for
        
        Returns:
            List of content strings (ordered by id asc)
        """
        try:
            # Query: select content from pdf_embeddings where pdf_id = <id> order by id asc
            response = self.supabase_client.table("pdf_embeddings")\
                .select("content")\
                .eq("pdf_id", pdf_id)\
                .order("id", desc=False)\
                .execute()
            
            if not response.data:
                return []
            
            # Extract content strings
            chunks = [row.get("content", "") for row in response.data if row.get("content")]
            return chunks
            
        except Exception as e:
            print(f"ERROR: Failed to fetch chunks for PDF {pdf_id}: {str(e)}")
            return []
    
    def get_pdf_name(self, pdf_id: str) -> str:
        """
        Get PDF name/title from pdf_embeddings table
        
        Args:
            pdf_id: PDF ID
        
        Returns:
            PDF name or default name
        """
        try:
            response = self.supabase_client.table("pdf_embeddings")\
                .select("pdf_title")\
                .eq("pdf_id", pdf_id)\
                .limit(1)\
                .execute()
            
            if response.data and response.data[0].get("pdf_title"):
                return response.data[0].get("pdf_title")
            
            return f"PDF {pdf_id[:8]}"
            
        except Exception as e:
            print(f"WARNING: Could not fetch PDF name for {pdf_id}: {str(e)}")
            return f"PDF {pdf_id[:8]}"
    
    def extract_knowledge_from_content(self, chunks: List[str]) -> Dict[str, Any]:
        """
        Extract structured knowledge from PDF content before generating questions
        
        Args:
            chunks: List of content strings from PDF
        
        Returns:
            Dictionary with extracted knowledge structure
        """
        if not chunks:
            return {}
        
        # Combine chunks into context
        context_text = "\n\n".join(chunks)
        
        # Limit context to avoid token limits
        max_context_length = 12000  # characters
        if len(context_text) > max_context_length:
            context_text = context_text[:max_context_length] + "..."
        
        extraction_prompt = f"""Extract structured knowledge from the following PDF content. 
Focus ONLY on the actual educational content, code examples, concepts, and explanations.
IGNORE any file names, video titles, timestamps, metadata, or chunk labels.

Extract and organize the knowledge into this JSON structure:

{{
  "topics": ["list of main topics covered"],
  "definitions": ["key definitions and terms"],
  "important_points": ["important concepts and principles"],
  "code_examples": ["code snippets and examples from the content"],
  "common_errors": ["common mistakes or errors discussed"],
  "advanced_concepts": ["advanced topics covered"],
  "flow_explanations": ["explanations of processes or flows"]
}}

IMPORTANT:
- Extract ONLY from the actual content text
- DO NOT include any file names, PDF names, video names, or metadata
- Focus on educational content, code, and concepts
- Output ONLY valid JSON, no markdown, no explanations

PDF Content:
{context_text}"""
        
        try:
            response = self.openai_client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a knowledge extraction expert. Extract structured knowledge from educational content. Always respond with valid JSON only. No markdown, no explanations."
                    },
                    {
                        "role": "user",
                        "content": extraction_prompt
                    }
                ],
                temperature=0.3,  # Lower temperature for more accurate extraction
                max_tokens=4000
            )
            
            content = response.choices[0].message.content.strip()
            
            # Extract JSON from markdown if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            knowledge = json.loads(content)
            print(f"✓ Extracted knowledge: {len(knowledge.get('topics', []))} topics, {len(knowledge.get('code_examples', []))} code examples")
            return knowledge
            
        except Exception as e:
            print(f"WARNING: Knowledge extraction failed: {str(e)}. Continuing with raw content...")
            return {}
    
    def validate_question(self, question: Dict[str, Any]) -> bool:
        """
        Validate a question before insertion
        
        Args:
            question: Question dictionary to validate
        
        Returns:
            True if valid, False otherwise
        """
        # Check required fields
        question_text = question.get("question", "")
        if not question_text or not str(question_text).strip():
            return False
        
        question_text_lower = str(question_text).lower()
        
        # BAN: Questions based on filenames, video names, metadata
        banned_patterns = [
            "pdf_", "video_", ".pdf", ".mp4", ".avi", ".mov",
            "file name", "filename", "file title", "video title",
            "timestamp", "2025-", "2024-", "2023-", "2022-",
            "chunk", "embedding", "metadata",
            "what is the name", "what is the title", "what is the file"
        ]
        
        for pattern in banned_patterns:
            if pattern in question_text_lower:
                return False
        
        # BAN: Generic trivial questions
        generic_questions = [
            "what is python", "what is a variable", "what is a function",
            "what is a loop", "what is a list", "what is a dictionary",
            "what is python used for", "what is the purpose of python"
        ]
        
        # Check if question is too generic (starts with generic phrases)
        if any(question_text_lower.startswith(gen) for gen in generic_questions):
            return False
        
        # Check if question is too short or lacks substance
        if len(question_text.strip()) < 30:
            return False
        
        options = question.get("options", [])
        if not isinstance(options, list) or len(options) != 4:
            return False
        
        # Check that all options are non-empty strings
        if not all(isinstance(opt, str) and opt.strip() for opt in options):
            return False
        
        correct_answer = question.get("correct_answer", "")
        if not correct_answer or not str(correct_answer).strip():
            return False
        
        # Accept correct_answer in two formats:
        # 1. Letter format: "A", "B", "C", or "D" (must be valid index)
        # 2. Full text format: matches one of the option texts
        correct_answer_str = str(correct_answer).strip()
        
        # Check if it's a letter (A, B, C, D) - map to index
        if correct_answer_str.upper() in ["A", "B", "C", "D"]:
            # Letter format is valid if we have 4 options
            pass  # Valid
        # Check if it matches one of the option texts
        elif correct_answer_str in options:
            # Full text format is valid
            pass  # Valid
        else:
            # Invalid format
            return False
        
        if not question.get("explanation") or not question.get("explanation").strip():
            return False
        
        difficulty = question.get("difficulty", "").lower()
        if difficulty not in ["easy", "medium", "hard"]:
            return False
        
        if not question.get("topic") or not question.get("topic").strip():
            return False
        
        return True
    
    def generate_questions_from_pdf_content(self, chunks: List[str]) -> List[Dict[str, Any]]:
        """
        Generate 20 high-quality questions using GPT from PDF content chunks
        Uses two-step process: extract knowledge, then generate questions
        
        Args:
            chunks: List of content strings from PDF
        
        Returns:
            List of question dictionaries
        """
        if not chunks:
            print("ERROR: No chunks provided for question generation")
            return []
        
        # Step 1: Extract structured knowledge from content
        print("  → Extracting knowledge from PDF content...")
        knowledge = self.extract_knowledge_from_content(chunks)
        
        # Combine chunks into context for question generation
        context_text = "\n\n".join(chunks)
        
        # Limit context to avoid token limits
        max_context_length = 12000  # characters
        if len(context_text) > max_context_length:
            context_text = context_text[:max_context_length] + "..."
        
        # Build knowledge summary for prompt
        knowledge_summary = ""
        if knowledge:
            knowledge_summary = f"""
Extracted Knowledge Structure:
- Topics: {', '.join(knowledge.get('topics', [])[:10])}
- Code Examples: {len(knowledge.get('code_examples', []))} examples found
- Important Points: {len(knowledge.get('important_points', []))} key points
- Advanced Concepts: {len(knowledge.get('advanced_concepts', []))} advanced topics
"""
        
        # Build enhanced prompt with strict requirements
        prompt = f"""You are an expert assessment generator. Generate EXACTLY 20 high-quality exam questions based on the PDF content.

CRITICAL REQUIREMENTS:

1. Question Distribution (MUST follow exactly):
   - At least 10 questions MUST be code-tracing/debugging/output questions
     * "What is the output of this code?"
     * "What error will this code produce?"
     * "What will be printed?"
     * "Which line causes the error?"
   - At least 5 questions MUST be deep conceptual reasoning questions
     * "Why does X work this way?"
     * "What is the principle behind Y?"
     * "How does Z mechanism function?"
   - At least 5 questions MUST be application/scenario questions
     * "In which scenario would you use X?"
     * "How would you solve problem Y?"
     * "What approach is best for situation Z?"

2. STRICT BANS (NEVER include):
   ❌ Questions about PDF file names, video names, or file titles
   ❌ Questions about timestamps, dates, or metadata
   ❌ Generic questions like "What is Python?" or "What is a variable?"
   ❌ Questions that reference chunk labels or embedding IDs
   ❌ Trivial questions with obvious answers
   ❌ Questions that don't test real understanding

3. Content Requirements:
   - ALL questions MUST be derived from the actual PDF content provided
   - Questions must test understanding, not just memorization
   - Code questions must use actual code from the content
   - Conceptual questions must reference real concepts explained in the content

4. Question Format:
   Each question MUST have:
   - "question": Clear, specific question text (minimum 30 characters)
   - "options": Exactly 4 options with full text (not just letters)
   - "correct_answer": Letter "A", "B", "C", or "D"
   - "explanation": Detailed explanation of why the answer is correct
   - "difficulty": "easy", "medium", or "hard"
   - "topic": Specific topic name (e.g., "Loops", "Functions", "Error Handling")

5. Output Format:
   Output ONLY valid JSON array, no markdown, no backticks, no explanations outside JSON.

Example structure:
[
  {{
    "question": "What will be the output when executing: for i in range(3): print(i)",
    "options": ["0\\n1\\n2", "1\\n2\\n3", "0, 1, 2", "Error"],
    "correct_answer": "A",
    "explanation": "range(3) generates 0, 1, 2. The loop prints each value on a new line.",
    "difficulty": "medium",
    "topic": "Loops"
  }}
]

{knowledge_summary}

PDF Content:
{context_text}"""
        
        # Retry logic for JSON parsing
        for attempt in range(MAX_RETRIES):
            try:
                # Generate questions using OpenAI with enhanced prompt
                response = self.openai_client.chat.completions.create(
                    model=OPENAI_MODEL,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are an expert assessment generator. Generate high-quality, contextual questions based ONLY on the provided content. NEVER reference file names, video titles, or metadata. Output ONLY valid JSON array, no markdown, no backticks, no explanations outside JSON."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    temperature=0.8,  # Slightly higher for more creative but still focused questions
                    max_tokens=10000  # Increased for 20 detailed questions
                )
                
                # Parse response
                content = response.choices[0].message.content.strip()
                
                # Try to extract JSON from markdown code blocks if present
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                
                # Parse JSON
                questions = json.loads(content)
                
                # Ensure it's a list
                if not isinstance(questions, list):
                    questions = [questions]
                
                # Validate all questions with enhanced checks
                valid_questions = []
                invalid_questions = []
                invalid_count = 0
                
                for q in questions:
                    if self.validate_question(q):
                        valid_questions.append(q)
                    else:
                        invalid_count += 1
                        invalid_questions.append(q)
                        question_text = q.get('question', 'N/A')[:60]
                        
                        # Determine why it's invalid
                        issues = []
                        question_text_lower = str(q.get("question", "")).lower()
                        
                        # Check for banned patterns
                        if any(pattern in question_text_lower for pattern in ["pdf_", "video_", ".pdf", "file name", "filename", "timestamp"]):
                            issues.append("contains filename/metadata reference")
                        elif any(question_text_lower.startswith(gen) for gen in ["what is python", "what is a variable", "what is a function"]):
                            issues.append("generic/trivial question")
                        elif len(str(q.get("question", "")).strip()) < 30:
                            issues.append("question too short")
                        elif not q.get("question") or not str(q.get("question", "")).strip():
                            issues.append("missing question")
                        
                        options = q.get("options", [])
                        if not isinstance(options, list) or len(options) != 4:
                            issues.append(f"invalid options (got {len(options) if isinstance(options, list) else 'not a list'})")
                        
                        correct_answer = q.get("correct_answer", "")
                        if not correct_answer:
                            issues.append("missing correct_answer")
                        elif str(correct_answer).strip().upper() not in ["A", "B", "C", "D"] and correct_answer not in options:
                            issues.append(f"invalid correct_answer format")
                        
                        if not q.get("explanation") or not str(q.get("explanation", "")).strip():
                            issues.append("missing explanation")
                        
                        difficulty = str(q.get("difficulty", "")).lower()
                        if difficulty not in ["easy", "medium", "hard"]:
                            issues.append(f"invalid difficulty")
                        
                        if not q.get("topic") or not str(q.get("topic", "")).strip():
                            issues.append("missing topic")
                        
                        if invalid_count <= 3:  # Only show first 3 invalid questions
                            print(f"WARNING: Invalid question skipped: {question_text}... (Reason: {', '.join(issues) if issues else 'validation failed'})")
                
                if invalid_count > 3:
                    print(f"WARNING: ... and {invalid_count - 3} more invalid questions")
                
                # If we have invalid questions but need more, try to regenerate them
                if len(valid_questions) < NUM_QUESTIONS_PER_PDF and invalid_questions and attempt < MAX_RETRIES - 1:
                    needed = NUM_QUESTIONS_PER_PDF - len(valid_questions)
                    print(f"  → Regenerating {needed} invalid questions...")
                    # Will retry in next iteration
                
                # Accept if we have at least 18 questions (90% of target)
                min_acceptable = max(18, NUM_QUESTIONS_PER_PDF - 2)
                
                if len(valid_questions) >= NUM_QUESTIONS_PER_PDF:
                    print(f"✓ Generated {len(valid_questions)} valid questions")
                    return valid_questions[:NUM_QUESTIONS_PER_PDF]  # Return exactly 20
                elif len(valid_questions) >= min_acceptable:
                    print(f"⚠️  Generated {len(valid_questions)} valid questions (expected {NUM_QUESTIONS_PER_PDF}, but acceptable)")
                    return valid_questions
                elif len(valid_questions) > 0:
                    print(f"WARNING: Generated {len(valid_questions)} valid questions, expected {NUM_QUESTIONS_PER_PDF}")
                    # If we have some valid questions but not enough, retry
                    if attempt < MAX_RETRIES - 1:
                        print(f"Retrying... (attempt {attempt + 2}/{MAX_RETRIES})")
                        time.sleep(RETRY_DELAY)
                        continue
                    else:
                        print(f"ERROR: Only generated {len(valid_questions)} questions after all retries")
                        return valid_questions if len(valid_questions) >= 15 else []  # Accept if at least 15
                else:
                    # No valid questions, retry
                    if attempt < MAX_RETRIES - 1:
                        print(f"WARNING: No valid questions generated. Retrying... (attempt {attempt + 2}/{MAX_RETRIES})")
                        time.sleep(RETRY_DELAY)
                        continue
                    else:
                        print("ERROR: Failed to generate valid questions after retries")
                        return []
                
            except json.JSONDecodeError as e:
                print(f"ERROR: Invalid JSON response (attempt {attempt + 1}/{MAX_RETRIES}): {str(e)}")
                if attempt < MAX_RETRIES - 1:
                    print(f"Retrying in {RETRY_DELAY} seconds...")
                    time.sleep(RETRY_DELAY)
                else:
                    print(f"Response content (first 500 chars): {content[:500] if 'content' in locals() else 'N/A'}")
                    return []
            
            except Exception as e:
                print(f"ERROR: Failed to generate questions (attempt {attempt + 1}/{MAX_RETRIES}): {str(e)}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY)
                else:
                    return []
        
        return []
    
    def check_assessment_exists(self, pdf_id: str) -> Optional[str]:
        """
        Check if an assessment already exists for a given PDF ID
        
        Args:
            pdf_id: PDF ID to check
        
        Returns:
            Existing assessment ID if found, None otherwise
        """
        try:
            # Check if assessment exists with pdf_id in blueprint JSON field
            # pdf_id is stored in blueprint as JSON: {"pdf_id": "pdf_xxx"}
            response = self.supabase_client.table("assessments")\
                .select("id, blueprint")\
                .execute()
            
            if response.data:
                for assessment in response.data:
                    blueprint = assessment.get("blueprint")
                    if blueprint:
                        # blueprint can be a string (JSON) or dict
                        try:
                            if isinstance(blueprint, str):
                                blueprint_data = json.loads(blueprint)
                            else:
                                blueprint_data = blueprint
                            
                            # Check if pdf_id matches
                            if blueprint_data.get("pdf_id") == pdf_id:
                                return str(assessment.get("id"))
                        except (json.JSONDecodeError, TypeError):
                            # If blueprint is not valid JSON, skip
                            continue
            
            return None
        except Exception as e:
            print(f"⚠️  Warning: Could not check for existing assessment: {str(e)}")
            return None
    
    def check_questions_exist(self, assessment_id: str) -> bool:
        """
        Check if questions already exist for an assessment
        
        Args:
            assessment_id: Assessment ID to check
        
        Returns:
            True if questions exist, False otherwise
        """
        try:
            response = self.supabase_client.table("skill_assessment_questions")\
                .select("id")\
                .eq("assessment_id", assessment_id)\
                .limit(1)\
                .execute()
            
            return response.data is not None and len(response.data) > 0
        except Exception as e:
            print(f"⚠️  Warning: Could not check for existing questions: {str(e)}")
            return False
    
    def create_assessment(self, pdf_id: str, num_questions: int, pdf_title: Optional[str] = None) -> Optional[str]:
        """
        Create assessment row in Supabase FIRST (before generating questions)
        Checks for duplicates before creating.
        
        Args:
            pdf_id: PDF ID
            num_questions: Number of questions (expected 20)
            pdf_title: PDF title from pdf_embeddings table (optional)
        
        Returns:
            Assessment ID if successful, None otherwise
        """
        try:
            # Use pdf_title for assessment title, with fallback
            if pdf_title and pdf_title.strip():
                assessment_title = pdf_title.strip()
            else:
                assessment_title = f"Assessment for {pdf_id}"
            
            # Store pdf_id in blueprint JSON field
            blueprint_data = {"pdf_id": pdf_id}
            
            # Use exact structure as specified by user
            assessment_data = {
                "title": assessment_title,
                "description": f"Auto-generated assessment based on: {assessment_title}",
                "skill_domain": "Python",
                "question_count": num_questions,  # Using question_count to match schema
                "status": "published",
                "difficulty": "medium",
                "blueprint": json.dumps(blueprint_data)  # Store pdf_id in blueprint
            }
            
            # Supabase SDK v2: insert() returns data by default, no .select() needed
            response = self.supabase_client.table("assessments")\
                .insert(assessment_data)\
                .execute()
            
            # Validate the insert
            if not response.data or len(response.data) == 0:
                print(f"❌ Failed to insert assessment: {response}")
                raise Exception("Assessment insert returned empty data")
            
            assessment_id = response.data[0]["id"]
            return str(assessment_id)
                
        except Exception as e:
            print(f"❌ ERROR: Failed to create assessment: {str(e)}")
            print(f"Details: {e}")
            return None
    
    def insert_questions(self, assessment_id: str, questions: List[Dict[str, Any]], pdf_id: str) -> bool:
        """
        Insert all questions into skill_assessment_questions table
        Checks for duplicates before inserting.
        
        Args:
            assessment_id: Assessment ID to link questions
            questions: List of question dictionaries
            pdf_id: PDF ID to link questions to source
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if questions already exist for this assessment
            if self.check_questions_exist(assessment_id):
                print(f"⚠️  Questions already exist for assessment {assessment_id}, skipping insertion")
                return True  # Return True since questions already exist
            
            # Prepare questions for insertion with all required fields
            # Note: question_type column does NOT exist in skill_assessment_questions table
            records = []
            for q in questions:
                record = {
                    "topic": q.get("topic", "Python"),
                    "question": q.get("question", ""),
                    "options": q.get("options", []),
                    "correct_answer": q.get("correct_answer", ""),
                    "source_type": "pdf",
                    "source_id": pdf_id,
                    "explanation": q.get("explanation", ""),
                    "difficulty": q.get("difficulty", "medium"),
                    "assessment_id": assessment_id
                    # Removed "question_type": "mcq" - this column does not exist in the schema
                }
                records.append(record)
            
            # Supabase SDK v2: insert() returns data by default, no .select() needed
            response = self.supabase_client.table("skill_assessment_questions")\
                .insert(records)\
                .execute()
            
            if response.data:
                print(f"✓ Inserted {len(response.data)} questions successfully")
                return True
            else:
                print(f"❌ ERROR: Question insert returned no data")
                print(f"Details: {response}")
                return False
                
        except Exception as e:
            print(f"❌ ERROR: Failed to insert questions: {str(e)}")
            print(f"Details: {e}")
            return False
    
    def generate_assessment_from_pdf(self, pdf_id: str) -> Optional[str]:
        """
        Complete workflow for a single PDF:
        1. Fetch chunks
        2. Generate questions
        3. Insert assessment
        4. Insert questions
        
        Args:
            pdf_id: PDF ID to process
        
        Returns:
            Assessment ID if successful, None otherwise
        """
        try:
            print(f"\n{'='*50}")
            print(f"Processing PDF: {pdf_id}")
            print(f"{'='*50}")
            
            # Step 0: Fetch PDF title from pdf_embeddings table
            print("Step 0: Fetching PDF title...")
            pdf_title = None
            try:
                response = self.supabase_client.table("pdf_embeddings")\
                    .select("pdf_title")\
                    .eq("pdf_id", pdf_id)\
                    .limit(1)\
                    .execute()
                
                if response.data and response.data[0].get("pdf_title"):
                    pdf_title = response.data[0].get("pdf_title")
                    print(f"✓ Found PDF title: {pdf_title}")
                else:
                    print(f"⚠️  No pdf_title found, using fallback title")
            except Exception as e:
                print(f"⚠️  Could not fetch PDF title: {str(e)}, using fallback title")
            
            # Step 1: Check if assessment already exists, create if not
            print("Step 1: Checking for existing assessment...")
            existing_assessment_id = self.check_assessment_exists(pdf_id)
            
            if existing_assessment_id:
                print(f"✓ Found existing assessment: {existing_assessment_id}")
                assessment_id = existing_assessment_id
                
                # Check if questions already exist
                if self.check_questions_exist(assessment_id):
                    print(f"✓ Assessment and questions already exist for PDF {pdf_id}")
                    print(f"⏭️  Skipping PDF {pdf_id} (already processed)")
                    return assessment_id
                else:
                    print(f"⚠️  Assessment exists but no questions found, will generate questions...")
            else:
                print("Step 1: Creating new assessment record...")
                assessment_id = self.create_assessment(pdf_id, NUM_QUESTIONS_PER_PDF, pdf_title)
                
                if not assessment_id:
                    print(f"❌ ERROR: Failed to create assessment for PDF {pdf_id}")
                    return None
                
                print(f"✓ Created assessment: {assessment_id}")
            
            # Step 2: Fetch chunks
            print("Step 2: Fetching content chunks...")
            chunks = self.fetch_pdf_chunks(pdf_id)
            
            if not chunks:
                print(f"❌ ERROR: No chunks found for PDF {pdf_id}")
                return None
            
            print(f"✓ Fetched {len(chunks)} chunks")
            
            # Step 3: Generate 20 questions from LLM (theory + code tracing)
            print("Step 3: Generating questions using GPT...")
            questions = self.generate_questions_from_pdf_content(chunks)
            
            # Accept if we have at least 18 questions (90% of target)
            min_acceptable = max(18, NUM_QUESTIONS_PER_PDF - 2)
            
            if not questions or len(questions) < min_acceptable:
                print(f"❌ ERROR: Failed to generate sufficient questions. Got {len(questions) if questions else 0}, need at least {min_acceptable}")
                return None
            
            if len(questions) != NUM_QUESTIONS_PER_PDF:
                print(f"⚠️  Generated {len(questions)} questions instead of {NUM_QUESTIONS_PER_PDF}, but proceeding...")
            
            # Step 4: Insert all questions into skill_assessment_questions
            print("Step 4: Inserting questions...")
            success = self.insert_questions(assessment_id, questions, pdf_id)
            
            if not success:
                print(f"❌ ERROR: Failed to insert questions for assessment {assessment_id}")
                return None
            
            # Success logging
            print(f"\n{'='*50}")
            print(f"PDF: {pdf_id}")
            print(f"Created assessment: {assessment_id}")
            print(f"Inserted {len(questions)} questions")
            print(f"Status: SUCCESS")
            print(f"{'='*50}\n")
            
            return assessment_id
            
        except Exception as e:
            print(f"\nERROR: {str(e)}")
            print(f"Details: {e}\n")
            return None
    
    def generate_all_assessments(self):
        """
        Main function to generate assessments for all PDFs
        """
        print("\n" + "="*60)
        print("🚀 Starting Assessment Generation for All PDFs")
        print("="*60 + "\n")
        
        # Step 1: Fetch all PDF IDs
        pdf_ids = self.fetch_all_pdf_ids()
        
        if not pdf_ids:
            print("No PDFs found. Exiting.")
            return
        
        print(f"\n📊 Processing {len(pdf_ids)} PDFs...\n")
        
        # Step 2: Process each PDF
        successful = 0
        failed = 0
        
        for i, pdf_id in enumerate(pdf_ids, 1):
            print(f"\n[{i}/{len(pdf_ids)}] Processing PDF: {pdf_id}")
            
            try:
                assessment_id = self.generate_assessment_from_pdf(pdf_id)
                
                if assessment_id:
                    successful += 1
                else:
                    failed += 1
                    print(f"⚠️  Skipping PDF {pdf_id} due to errors (continuing with others)...")
            
            except Exception as e:
                failed += 1
                print(f"ERROR: Unexpected error processing PDF {pdf_id}: {str(e)}")
                print(f"Details: {e}")
                print(f"⚠️  Skipping PDF {pdf_id} (continuing with others)...\n")
                continue
        
        # Final summary
        print("\n" + "="*60)
        print("📊 FINAL SUMMARY")
        print("="*60)
        print(f"Total PDFs processed: {len(pdf_ids)}")
        print(f"Successful: {successful} ✓")
        print(f"Failed: {failed} ✗")
        print("="*60 + "\n")


def test_insert_assessment(generator: AssessmentGenerator):
    """
    Quick test function to verify assessment insert works
    """
    try:
        print("\n[TEST] Testing assessment insert...")
        test_data = {
            "title": "Test Assessment",
            "description": "Testing",
            "skill_domain": "Python",
            "question_count": 5,
            "status": "published",
            "difficulty": "medium"
        }
        response = generator.supabase_client.table("assessments").insert(test_data).execute()
        
        if response.data and len(response.data) > 0:
            test_id = response.data[0]["id"]
            print(f"[TEST] ✓ Assessment insert successful! ID: {test_id}")
            print(f"[TEST] Response data: {response.data[0]}")
            return True
        else:
            print(f"[TEST] ❌ Assessment insert returned no data")
            print(f"[TEST] Response: {response}")
            return False
    except Exception as e:
        print(f"[TEST] ❌ Assessment insert test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main entry point"""
    try:
        generator = AssessmentGenerator()
        
        # Optional: Run test first (uncomment to enable)
        # if not test_insert_assessment(generator):
        #     print("\n[WARNING] Test insert failed. Continuing anyway...")
        
        generator.generate_all_assessments()
    except KeyboardInterrupt:
        print("\n\n⚠️  Process interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nERROR: Fatal error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

