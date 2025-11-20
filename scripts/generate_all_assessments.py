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
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client, Client
from openai import OpenAI

# Load environment variables (prefer project root .env)
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent

env_candidates = [
    PROJECT_ROOT / ".env",
    BASE_DIR / ".env"
]

for env_path in env_candidates:
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=True)
        break

# Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
# Load service role key first, fallback to anon key
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
SUPABASE_KEY = SUPABASE_SERVICE_KEY or os.getenv("SUPABASE_KEY", "")
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
        self.assessment_cache: Dict[str, Dict[str, Any]] = {}
        self._initialize_clients()
        self._populate_assessment_cache()
    
    def _initialize_clients(self):
        """Initialize Supabase and OpenAI clients"""
        # Initialize Supabase
        try:
            if not SUPABASE_URL:
                print("ERROR: SUPABASE_URL must be set in .env file")
                sys.exit(1)
            
            if not SUPABASE_KEY:
                print("ERROR: Either SUPABASE_SERVICE_KEY or SUPABASE_KEY must be set in .env file")
                sys.exit(1)
            
            if "your-project" in SUPABASE_URL.lower() or "your-supabase" in SUPABASE_KEY.lower():
                print("ERROR: Please configure actual Supabase credentials in .env file")
                sys.exit(1)
            
            self.supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
                
        except Exception as e:
            print(f"ERROR: Failed to initialize Supabase client: {str(e)}")
            sys.exit(1)
        
        # Initialize OpenAI
        try:
            if not OPENAI_API_KEY or "your-openai" in OPENAI_API_KEY.lower():
                print("ERROR: OPENAI_API_KEY must be set in .env file")
                sys.exit(1)
            
            self.openai_client = OpenAI(api_key=OPENAI_API_KEY)
        except Exception as e:
            print(f"ERROR: Failed to initialize OpenAI client: {str(e)}")
            sys.exit(1)

    def _populate_assessment_cache(self):
        """Cache assessment rows keyed by pdf_id for quick duplicate checks"""
        self.assessment_cache = {}
        if not self.supabase_client:
            return

        try:
            response = self.supabase_client.table("assessments")\
                .select("id, blueprint, course_id, status")\
                .execute()

            for record in response.data or []:
                pdf_id = self.extract_pdf_id(record.get("blueprint"))
                if pdf_id:
                    self.assessment_cache[pdf_id] = record
        except Exception:
            self.assessment_cache = {}

    @staticmethod
    def parse_blueprint(blueprint_value: Any) -> Optional[Dict[str, Any]]:
        """Parse blueprint JSON safely"""
        if not blueprint_value:
            return None
        try:
            if isinstance(blueprint_value, str):
                return json.loads(blueprint_value)
            return blueprint_value
        except Exception:
            return None

    def extract_pdf_id(self, blueprint_value: Any) -> Optional[str]:
        """Extract pdf_id from blueprint content"""
        blueprint_data = self.parse_blueprint(blueprint_value)
        if blueprint_data:
            pdf_id = blueprint_data.get("pdf_id")
            if isinstance(pdf_id, str) and pdf_id.strip():
                return pdf_id.strip()
        return None
    
    def fetch_all_pdf_ids(self) -> List[str]:
        """
        Fetch all unique PDF IDs from pdf_embeddings table
        
        Returns:
            List of unique PDF IDs
        """
        try:
            response = self.supabase_client.table("pdf_embeddings")\
                .select("pdf_id")\
                .execute()
            
            if not response.data:
                return []
            
            pdf_ids = list(set([row.get("pdf_id") for row in response.data if row.get("pdf_id")]))
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
            
        except Exception:
            return f"PDF {pdf_id[:8]}"
    
    def detect_course_name(self, pdf_title: Optional[str] = None, pdf_id: str = "") -> str:
        """
        Detect course name from PDF title or PDF ID
        
        Args:
            pdf_title: PDF title from pdf_embeddings table
            pdf_id: PDF ID as fallback
        
        Returns:
            Course name (Python, DevOps, etc.)
        """
        # Combine title and ID for detection
        search_text = ""
        if pdf_title:
            search_text = pdf_title.lower()
        if pdf_id:
            search_text += " " + pdf_id.lower()
        
        search_text = search_text.strip()
        
        # Detection rules - CHECK DEVOPS FIRST (more specific indicators)
        # DevOps course indicators (check first to avoid false positives)
        devops_indicators = [
            "devops", "docker", "kubernetes", "k8s", "jenkins", 
            "sonarqube", "linux", "git", "ci/cd", "terraform", 
            "ansible", "aws", "azure", "gcp", "networking", "cloud",
            "container", "orchestration", "deployment", "infrastructure"
        ]
        
        # Python course indicators (more specific to avoid conflicts)
        python_indicators = [
            "python", "datatypes", "loops", "functions", "classes",
            "list", "dict", "tuple", "set", "comprehension", "decorator",
            "generator", "iterator", "exception", "import", "package"
        ]
        
        # Check for DevOps FIRST (more specific indicators take priority)
        if any(indicator in search_text for indicator in devops_indicators):
            return "DevOps"
        
        # Check for Python (only if no DevOps indicators found)
        if any(indicator in search_text for indicator in python_indicators):
            return "Python"
        
        # Check for module patterns - need context to determine course
        # If it contains DevOps-related terms, it's DevOps
        if "module" in search_text:
            # Check if it's a DevOps module by looking for DevOps keywords
            devops_module_keywords = ["docker", "kubernetes", "sonarqube", "networking", 
                                     "cloud", "devops", "linux", "jenkins", "terraform"]
            if any(keyword in search_text for keyword in devops_module_keywords):
                return "DevOps"
            # Otherwise, assume Python for backward compatibility
            return "Python"
        
        # Default to Python if no match (for backward compatibility)
        return "Python"
    
    def get_or_create_course(self, course_name: str) -> Optional[str]:
        """
        Get course_id from courses table, create if it doesn't exist
        
        Args:
            course_name: Course name (e.g., "Python", "DevOps")
        
        Returns:
            Course ID (UUID string) if successful, None otherwise
        """
        try:
            # Normalize course name
            course_name = course_name.strip()
            if not course_name:
                print("ERROR: Course name is empty")
                return None
            
            # Try to fetch existing course
            response = self.supabase_client.table("courses")\
                .select("id")\
                .eq("name", course_name)\
                .limit(1)\
                .execute()
            
            if response.data and len(response.data) > 0:
                course_id = str(response.data[0]["id"])
                return course_id
            
            create_response = self.supabase_client.table("courses")\
                .insert({
                    "name": course_name,
                    "description": f"{course_name} course assessments"
                })\
                .execute()
            
            if create_response.data and len(create_response.data) > 0:
                course_id = str(create_response.data[0]["id"])
                return course_id
            else:
                return None
                
        except Exception as e:
            print(f"❌ ERROR: Failed to get/create course {course_name}: {str(e)}")
            return None
    
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
            return knowledge
            
        except Exception:
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
            return []
        
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
                        
                if len(valid_questions) < NUM_QUESTIONS_PER_PDF and invalid_questions and attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY)
                    continue
                
                # Accept if we have at least 18 questions (90% of target)
                min_acceptable = max(18, NUM_QUESTIONS_PER_PDF - 2)
                
                if len(valid_questions) >= NUM_QUESTIONS_PER_PDF:
                    return valid_questions[:NUM_QUESTIONS_PER_PDF]
                elif len(valid_questions) >= min_acceptable:
                    return valid_questions
                elif len(valid_questions) > 0:
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(RETRY_DELAY)
                        continue
                    else:
                        return valid_questions if len(valid_questions) >= 15 else []
                else:
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(RETRY_DELAY)
                        continue
                    else:
                        return []
                
            except json.JSONDecodeError:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY)
                else:
                    return []
            
            except Exception:
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
    
    def check_assessment_exists_by_pdf_id(self, pdf_id: str) -> Optional[Dict[str, Any]]:
        """
        Check if an assessment exists for a PDF ID using direct query
        Returns the full assessment record if found
        
        Args:
            pdf_id: PDF ID to check
            
        Returns:
            Assessment record dict if found, None otherwise
        """
        cached = self.assessment_cache.get(pdf_id)
        if cached:
            return cached

        # Cache miss - refresh cache and check again
        self._populate_assessment_cache()
        return self.assessment_cache.get(pdf_id)
    
    def check_questions_exist(self, assessment_id: str) -> bool:
        """
        Check if questions already exist for an assessment
        Returns True if ANY questions exist, False otherwise
        
        Args:
            assessment_id: Assessment ID to check
            
        Returns:
            True if questions exist, False otherwise
        """
        try:
            existing_q = self.supabase_client.table("skill_assessment_questions")\
                .select("id")\
                .eq("assessment_id", assessment_id)\
                .execute()
            
            return existing_q.data is not None and len(existing_q.data) > 0
        except Exception:
            return False
    
    def create_assessment(self, pdf_id: str, num_questions: int, pdf_title: Optional[str] = None, course_id: Optional[str] = None) -> Optional[str]:
        """
        Create assessment row in Supabase FIRST (before generating questions)
        STRICTLY checks for duplicates before creating.
        
        Args:
            pdf_id: PDF ID
            num_questions: Number of questions (expected 20)
            pdf_title: PDF title from pdf_embeddings table (optional)
            course_id: Course ID (UUID string) - optional, will be detected if not provided
        
        Returns:
            Assessment ID if successful, None otherwise
        """
        try:
            # STRICT DUPLICATE CHECK: Check if assessment already exists
            existing = self.check_assessment_exists_by_pdf_id(pdf_id)
            if existing:
                return str(existing.get("id"))
            
            # Use pdf_title for assessment title, with fallback
            if pdf_title and pdf_title.strip():
                assessment_title = pdf_title.strip()
            else:
                assessment_title = f"Assessment for {pdf_id}"
            
            if not course_id:
                course_name = self.detect_course_name(pdf_title, pdf_id)
                course_id = self.get_or_create_course(course_name)
            else:
                # Get course name for skill_domain
                try:
                    course_response = self.supabase_client.table("courses")\
                        .select("name")\
                        .eq("id", course_id)\
                        .limit(1)\
                        .execute()
                    course_name = course_response.data[0]["name"] if course_response.data else "Python"
                except:
                    course_name = "Python"
            
            # Store pdf_id in blueprint JSON field
            blueprint_data = {"pdf_id": pdf_id}
            
            # Optional: Add unique hash for extra safety
            unique_hash = hashlib.md5(pdf_id.encode()).hexdigest()
            blueprint_data["unique_hash"] = unique_hash
            
            # Use exact structure as specified by user
            assessment_data = {
                "title": assessment_title,
                "description": f"Auto-generated assessment based on: {assessment_title}",
                "skill_domain": course_name,  # Use course name as skill_domain
                "question_count": num_questions,  # Using question_count to match schema
                "status": "published",
                "difficulty": "medium",
                "blueprint": json.dumps(blueprint_data),  # Store pdf_id and hash in blueprint
                "course_id": course_id  # Add course_id for course-based grouping
            }
            
            # Supabase SDK v2: insert() returns data by default, no .select() needed
            response = self.supabase_client.table("assessments")\
                .insert(assessment_data)\
                .execute()
            
            if not response.data or len(response.data) == 0:
                raise Exception("Assessment insert returned empty data")
            
            new_record = response.data[0]
            assessment_id = new_record["id"]

            # Keep cache in sync so duplicate checks stay accurate
            self.assessment_cache[pdf_id] = new_record
            return str(assessment_id)
                
        except Exception:
            return None
    
    def insert_questions(self, assessment_id: str, questions: List[Dict[str, Any]], pdf_id: str) -> bool:
        """
        Insert all questions into skill_assessment_questions table
        STRICTLY checks for duplicates before inserting.
        
        Args:
            assessment_id: Assessment ID to link questions
            questions: List of question dictionaries
            pdf_id: PDF ID to link questions to source
        
        Returns:
            True if successful or already exists, False otherwise
        """
        try:
            # STRICT DUPLICATE CHECK: Check if questions already exist
            existing_q = self.supabase_client.table("skill_assessment_questions")\
                .select("id")\
                .eq("assessment_id", assessment_id)\
                .execute()
            
            if existing_q.data and len(existing_q.data) > 0:
                return True
            
            # No questions exist - proceed with insertion
            
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
            
            return bool(response.data)
                
        except Exception:
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
            pdf_title = None
            try:
                response = self.supabase_client.table("pdf_embeddings")\
                    .select("pdf_title")\
                    .eq("pdf_id", pdf_id)\
                    .limit(1)\
                    .execute()
                
                if response.data and response.data[0].get("pdf_title"):
                    pdf_title = response.data[0].get("pdf_title")
            except Exception:
                pass
            
            existing_assessment = self.check_assessment_exists_by_pdf_id(pdf_id)
            
            if existing_assessment:
                existing_assessment_id = str(existing_assessment.get("id"))
                existing_course_id = existing_assessment.get("course_id")
                if not existing_course_id:
                    course_name = self.detect_course_name(pdf_title, pdf_id)
                    course_id = self.get_or_create_course(course_name)
                    if course_id:
                        try:
                            self.supabase_client.table("assessments")\
                                .update({
                                    "course_id": course_id,
                                    "skill_domain": course_name
                                })\
                                .eq("id", existing_assessment_id)\
                                .execute()
                            existing_assessment["course_id"] = course_id
                            self.assessment_cache[pdf_id] = existing_assessment
                        except Exception:
                            pass
                
                assessment_id = existing_assessment_id
                
                if self.check_questions_exist(assessment_id):
                    return assessment_id
            else:
                assessment_id = self.create_assessment(pdf_id, NUM_QUESTIONS_PER_PDF, pdf_title)
                if not assessment_id:
                    return None
            
            chunks = self.fetch_pdf_chunks(pdf_id)
            if not chunks:
                return None
            
            if self.check_questions_exist(assessment_id):
                return assessment_id
            
            questions = self.generate_questions_from_pdf_content(chunks)
            min_acceptable = max(18, NUM_QUESTIONS_PER_PDF - 2)
            
            if not questions or len(questions) < min_acceptable:
                return None
            
            success = self.insert_questions(assessment_id, questions, pdf_id)
            if not success:
                return None
            
            return assessment_id
            
        except Exception:
            return None
    
    def generate_all_assessments(self):
        """
        Main function to generate assessments for all PDFs
        """
        pdf_ids = self.fetch_all_pdf_ids()
        
        if not pdf_ids:
            return
        
        pdfs_to_process, skipped_pdfs = self._filter_pdfs_requiring_processing(pdf_ids)
        
        successful = 0
        failed = 0
        
        for pdf_id in pdfs_to_process:
            try:
                assessment_id = self.generate_assessment_from_pdf(pdf_id)
                if assessment_id:
                    successful += 1
                else:
                    failed += 1
            except Exception:
                failed += 1
                continue

        # Refresh cache to include newly created assessments
        self._populate_assessment_cache()

        print(f"Total PDFs detected            : {len(pdf_ids)}")
        print(f"Already processed / up-to-date : {len(skipped_pdfs)}")
        print(f"Attempted this run             : {len(pdfs_to_process)}")
        print(f"  ✔ Successful                 : {successful}")
        print(f"  ✖ Failed                     : {failed}")

    def _filter_pdfs_requiring_processing(self, pdf_ids: List[str]) -> Tuple[List[str], List[str]]:
        """Return PDFs that still need assessments or questions"""
        remaining: List[str] = []
        skipped: List[str] = []

        for pdf_id in pdf_ids:
            existing = self.check_assessment_exists_by_pdf_id(pdf_id)

            if not existing:
                remaining.append(pdf_id)
                continue

            assessment_id = str(existing.get("id"))
            existing_course_id = existing.get("course_id")

            # Reprocess if course_id missing so course linkage is enforced
            if not existing_course_id:
                remaining.append(pdf_id)
                continue

            # Reprocess if assessment is missing questions
            if not self.check_questions_exist(assessment_id):
                remaining.append(pdf_id)
                continue

            skipped.append(pdf_id)

        return remaining, skipped


def main():
    """Main entry point"""
    try:
        generator = AssessmentGenerator()
        generator.generate_all_assessments()
    except KeyboardInterrupt:
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()

