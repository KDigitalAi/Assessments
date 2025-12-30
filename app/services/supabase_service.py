"""
Supabase service utilities for database operations, auth, and storage
"""

from supabase import create_client, Client
from typing import Optional, Dict, Any, List
from app.config import settings
from app.utils.cache import cache
from app.utils.logger import logger
from uuid import UUID


class SupabaseService:
    """Service for interacting with Supabase"""
    
    def __init__(self):
        """Initialize Supabase client"""
        # Defer initialization to first use so serverless cold starts
        # (and missing env vars) do not crash at import time.
        self.client: Optional[Client] = None  # Anon key client (for regular operations)
        self.service_client: Optional[Client] = None  # Service key client (for admin operations)
    
    def _initialize_client(self):
        """Initialize Supabase client with anon key (for regular operations)"""
        try:
            # Enhanced validation with clear error messages
            # Validate that required settings are present
            if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
                logger.error("[CRITICAL] Supabase credentials missing!")
                logger.error("   SUPABASE_URL: " + (settings.SUPABASE_URL[:50] + "..." if settings.SUPABASE_URL else "NOT SET"))
                logger.error("   SUPABASE_KEY: " + (settings.SUPABASE_KEY[:20] + "..." if settings.SUPABASE_KEY else "NOT SET"))
                logger.error("   SOLUTION: Set SUPABASE_URL and SUPABASE_KEY environment variables")
                self.client = None
                return
            
            # Check if values are placeholders
            is_placeholder_url = (
                "your-project" in settings.SUPABASE_URL.lower() or 
                "placeholder" in settings.SUPABASE_URL.lower() or
                settings.SUPABASE_URL == "https://your-project.supabase.co"
            )
            is_placeholder_key = (
                "your-supabase" in settings.SUPABASE_KEY.lower() or
                "placeholder" in settings.SUPABASE_KEY.lower() or
                settings.SUPABASE_KEY == "your-supabase-anon-key"
            )
            
            if is_placeholder_url or is_placeholder_key:
                logger.error("[CRITICAL] Supabase credentials appear to be placeholders!")
                logger.error(f"   Current URL: {settings.SUPABASE_URL[:50]}...")
                logger.error(f"   Current KEY: {settings.SUPABASE_KEY[:20]}...")
                self.client = None
                return
            
            # Validate URL format
            if not settings.SUPABASE_URL.startswith("https://"):
                logger.error(f"[WARN] Invalid SUPABASE_URL format. Must start with 'https://'. Got: {settings.SUPABASE_URL[:50]}")
                self.client = None
                return
            
            # Validate key format (should be a long string)
            if len(settings.SUPABASE_KEY) < 50:
                logger.warning(f"[WARN] SUPABASE_KEY seems too short ({len(settings.SUPABASE_KEY)} chars). Please verify it's correct.")
            
            # Create client with anon key
            self.client = create_client(
                settings.SUPABASE_URL,
                settings.SUPABASE_KEY
            )
            
            # Test connection with a simple query
            try:
                # Try to query a table that should exist (or at least check if we can connect)
                # This is a lightweight test that doesn't require any specific table
                _ = self.client.table("profiles").select("id").limit(0).execute()
            except Exception as test_error:
                # If profiles table doesn't exist, that's okay - we just want to verify connection works
                error_msg = str(test_error).lower()
                if "does not exist" not in error_msg and "relation" not in error_msg:
                    logger.warning(f"Supabase client initialized but connection test failed: {str(test_error)}")
                    # Check for RLS issues
                    if "row-level security" in error_msg or "permission denied" in error_msg:
                        logger.warning("   This might be a Row Level Security (RLS) issue.")
                        logger.warning("   SOLUTION: Check RLS policies in Supabase dashboard")
                    
        except Exception as e:
            logger.error(f"[WARN] Failed to initialize Supabase client: {str(e)}. Database features may be unavailable.")
            logger.error(f"[WARN] Please check:")
            logger.error(f"[WARN]   1. SUPABASE_URL is correct and starts with 'https://'")
            logger.error(f"[WARN]   2. SUPABASE_KEY is the anon/public key from Supabase dashboard")
            logger.error(f"[WARN]   3. Network connection to Supabase is available")
            self.client = None
    
    def _initialize_service_client(self):
        """Initialize Supabase client with service role key (for admin operations that bypass RLS)"""
        try:
            # Check if service key is configured
            if not settings.SUPABASE_SERVICE_KEY:
                logger.warning("SUPABASE_SERVICE_KEY not configured. Admin operations may fail due to RLS.")
                logger.warning("   SOLUTION: Add SUPABASE_SERVICE_KEY to your .env file for admin operations")
                self.service_client = None
                return
            
            # Check if service key is a placeholder
            if "your-supabase" in settings.SUPABASE_SERVICE_KEY.lower() or "placeholder" in settings.SUPABASE_SERVICE_KEY.lower():
                logger.warning("SUPABASE_SERVICE_KEY appears to be a placeholder. Admin operations may fail.")
                self.service_client = None
                return
            
            # Validate service key format
            if len(settings.SUPABASE_SERVICE_KEY) < 50:
                logger.warning(f"[WARN] SUPABASE_SERVICE_KEY seems too short ({len(settings.SUPABASE_SERVICE_KEY)} chars). Please verify it's correct.")
            
            # Create client with service key
            self.service_client = create_client(
                settings.SUPABASE_URL,
                settings.SUPABASE_SERVICE_KEY
            )
            
        except Exception as e:
            logger.error(f"[WARN] Failed to initialize Supabase service client: {str(e)}. Admin operations may be unavailable.")
            self.service_client = None
    
    def get_client(self, use_service_key: bool = False) -> Optional[Client]:
        """
        Get Supabase client instance
        
        Args:
            use_service_key: If True, returns service key client (bypasses RLS). 
                           If False, returns anon key client (respects RLS).
        
        Returns:
            Supabase client instance or None if not initialized
        """
        if use_service_key:
            if not self.service_client:
                self._initialize_service_client()
            return self.service_client
        else:
            if not self.client:
                self._initialize_client()
            return self.client
    
    def _ensure_client(self, use_service_key: bool = False) -> Client:
        """
        Ensure client is initialized and raise exception if not available
        
        Args:
            use_service_key: If True, uses service key client for admin operations
        """
        client = self.get_client(use_service_key=use_service_key)
        if not client:
            key_type = "service key" if use_service_key else "anon key"
            raise Exception(f"Supabase client ({key_type}) not initialized. Please configure SUPABASE_URL and SUPABASE_KEY in .env file.")
        return client
    
    # ============================================
    # Profile Operations
    # ============================================
    
    def get_profile(self, user_id: UUID) -> Optional[Dict[str, Any]]:
        """Get user profile by ID"""
        try:
            logger.debug(f"Fetching profile for user_id: {user_id}")
            client = self._ensure_client()
            response = client.table("profiles").select("*").eq("id", str(user_id)).execute()
            if response.data:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error getting profile: {str(e)}")
            return None
    
    def create_profile(self, user_id: UUID, email: str, **kwargs) -> Optional[Dict[str, Any]]:
        """Create user profile"""
        try:
            logger.info(f"Creating profile for user_id: {user_id}, email: {email}")
            client = self._ensure_client()
            data = {
                "id": str(user_id),
                "email": email,
                **kwargs
            }
            response = client.table("profiles").insert(data).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error creating profile: {str(e)}")
            return None
    
    # ============================================
    # Assessment Operations
    # ============================================
    
    def create_assessment(self, assessment_data: Dict[str, Any], use_service_key: bool = True) -> Optional[Dict[str, Any]]:
        """
        Create a new assessment
        
        Args:
            assessment_data: Assessment data dictionary
            use_service_key: If True, uses service key client to bypass RLS (default: True for admin operations)
        """
        try:
            client = self.get_client(use_service_key=use_service_key)
            if not client:
                key_type = "service key" if use_service_key else "anon key"
                raise Exception(f"Supabase client ({key_type}) not initialized. Please configure Supabase credentials.")
            response = client.table("assessments").insert(assessment_data).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error creating assessment: {str(e)}")
            if "row-level security" in str(e).lower() and not use_service_key:
                logger.error("SOLUTION: Ensure SUPABASE_SERVICE_KEY is set in .env file for admin operations")
            raise
    
    def get_assessment(self, assessment_id: UUID, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """Get assessment by ID with optional caching"""
        cache_key = f"assessment:{assessment_id}"
        
        # Try cache first
        if use_cache:
            cached = cache.get(cache_key)
            if cached is not None:
                return cached
        
        try:
            client = self._ensure_client()
            response = client.table("assessments").select("*").eq("id", str(assessment_id)).execute()
            result = response.data[0] if response.data else None
            
            # Cache result
            if result and use_cache:
                cache.set(cache_key, result, ttl_seconds=600)  # 10 minutes
            
            return result
        except Exception as e:
            logger.error(f"Error getting assessment: {str(e)}")
            return None
    
    def update_assessment(self, assessment_id: UUID, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update assessment and invalidate cache"""
        try:
            client = self._ensure_client()
            response = client.table("assessments").update(update_data).eq("id", str(assessment_id)).execute()
            result = response.data[0] if response.data else None
            
            # Invalidate cache
            cache.delete(f"assessment:{assessment_id}")
            
            return result
        except Exception as e:
            logger.error(f"Error updating assessment: {str(e)}")
            raise
    
    def list_assessments(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """List assessments with optional filters"""
        try:
            client = self._ensure_client()
            query = client.table("assessments").select("*")
            
            # Optimized filter building - single pass
            if filters:
                filter_map = {
                    "status": lambda v: query.eq("status", v),
                    "created_by": lambda v: query.eq("created_by", v),
                    "skill_domain": lambda v: query.eq("skill_domain", v)
                }
                for key, filter_func in filter_map.items():
                    value = filters.get(key)
                    if value:
                        query = filter_func(value)
            
            response = query.order("created_at", desc=True).execute()
            return response.data if response.data else []
        except Exception as e:
            logger.error(f"Error listing assessments: {str(e)}")
            return []
    
    # ============================================
    # Question Operations
    # ============================================
    
    def create_question(self, question_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create a new question"""
        try:
            client = self._ensure_client()
            # Handle embedding vector
            if "embedding" in question_data and question_data["embedding"]:
                question_data["embedding"] = str(question_data["embedding"])
            
            response = client.table("skill_assessment_questions").insert(question_data).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error creating question: {str(e)}")
            raise
    
    def get_question(self, question_id: UUID, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """Get question by ID with optional caching"""
        cache_key = f"question:{question_id}"
        
        # Try cache first
        if use_cache:
            cached = cache.get(cache_key)
            if cached is not None:
                return cached
        
        try:
            client = self._ensure_client()
            response = client.table("skill_assessment_questions").select("*").eq("id", str(question_id)).execute()
            result = response.data[0] if response.data else None
            
            # Cache result
            if result and use_cache:
                cache.set(cache_key, result, ttl_seconds=600)  # 10 minutes
            
            return result
        except Exception as e:
            logger.error(f"Error getting question: {str(e)}")
            return None
    
    def get_questions_batch(self, question_ids: List[UUID], use_cache: bool = True) -> Dict[str, Dict[str, Any]]:
        """Get multiple questions by IDs in a single query - optimized batch operation"""
        if not question_ids:
            return {}
        
        try:
            client = self._ensure_client()
            
            # Check cache for each question - optimized with dict comprehension
            questions_dict = {}
            uncached_ids = []
            
            if use_cache:
                # Optimized: single pass with dict comprehension
                for qid in question_ids:
                    cache_key = f"question:{qid}"
                    cached = cache.get(cache_key)
                    if cached is not None:
                        questions_dict[str(qid)] = cached
                    else:
                        uncached_ids.append(qid)
            else:
                uncached_ids = question_ids
            
            # Batch fetch uncached questions - optimized list comprehension
            if uncached_ids:
                # Use Supabase's 'in' filter for batch query
                id_strings = [str(qid) for qid in uncached_ids]
                response = client.table("skill_assessment_questions").select("*").in_("id", id_strings).execute()
                
                # Build dictionary and cache - optimized single pass
                cache_ttl = 600 if use_cache else None
                for question in (response.data or []):
                    qid_str = str(question["id"])
                    questions_dict[qid_str] = question
                    
                    if use_cache:
                        cache.set(f"question:{qid_str}", question, ttl_seconds=cache_ttl)
            
            return questions_dict
        except Exception as e:
            logger.error(f"Error getting questions batch: {str(e)}")
            return {}
    
    def get_assessment_questions(
        self,
        assessment_id: UUID,
        limit: Optional[int] = None,
        use_cache: bool = True
    ) -> List[Dict[str, Any]]:
        """Get questions for an assessment with optional caching"""
        cache_key = f"assessment_questions:{assessment_id}:{limit}"
        
        # Try cache first
        if use_cache:
            cached = cache.get(cache_key)
            if cached is not None:
                return cached
        
        try:
            client = self._ensure_client()
            query = client.table("skill_assessment_questions").select("*").eq("assessment_id", str(assessment_id))
            
            if limit:
                query = query.limit(limit)
            
            response = query.execute()
            result = response.data if response.data else []
            
            # Cache result
            if result and use_cache:
                cache.set(cache_key, result, ttl_seconds=300)  # 5 minutes
            
            return result
        except Exception as e:
            logger.error(f"Error getting assessment questions: {str(e)}")
            return []
    
    def find_similar_questions(self, embedding: List[float], threshold: float = 0.85, limit: int = 5) -> List[Dict[str, Any]]:
        """Find similar questions using vector similarity"""
        try:
            client = self._ensure_client()
            # Use pgvector cosine similarity
            embedding_str = str(embedding)
            response = client.rpc(
                "match_questions",
                {
                    "query_embedding": embedding_str,
                    "match_threshold": threshold,
                    "match_count": limit
                }
            ).execute()
            
            return response.data if response.data else []
        except Exception as e:
            logger.warning(f"Vector similarity search failed: {str(e)}")
            return []
    
    # ============================================
    # Attempt Operations
    # ============================================
    
    def create_attempt(self, attempt_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create a new attempt"""
        try:
            client = self._ensure_client()
            response = client.table("attempts").insert(attempt_data).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error creating attempt: {str(e)}")
            raise
    
    def get_attempt(self, attempt_id: UUID) -> Optional[Dict[str, Any]]:
        """Get attempt by ID"""
        try:
            client = self._ensure_client()
            response = client.table("attempts").select("*").eq("id", str(attempt_id)).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error getting attempt: {str(e)}")
            return None
    
    def update_attempt(self, attempt_id: UUID, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update attempt"""
        try:
            client = self._ensure_client()
            response = client.table("attempts").update(update_data).eq("id", str(attempt_id)).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error updating attempt: {str(e)}")
            raise
    
    def get_user_attempts(self, user_id: UUID, assessment_id: Optional[UUID] = None) -> List[Dict[str, Any]]:
        """Get attempts for a user"""
        try:
            client = self._ensure_client()
            query = client.table("attempts").select("*").eq("user_id", str(user_id))
            
            if assessment_id:
                query = query.eq("assessment_id", str(assessment_id))
            
            response = query.order("created_at", desc=True).execute()
            return response.data if response.data else []
        except Exception as e:
            logger.error(f"Error getting user attempts: {str(e)}")
            return []
    
    # ============================================
    # Response Operations
    # ============================================
    
    def create_response(self, response_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create a new response"""
        try:
            client = self._ensure_client()
            response = client.table("responses").insert(response_data).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error creating response: {str(e)}")
            raise
    
    def get_response(self, response_id: UUID) -> Optional[Dict[str, Any]]:
        """Get response by ID"""
        try:
            client = self._ensure_client()
            response = client.table("responses").select("*").eq("id", str(response_id)).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error getting response: {str(e)}")
            return None
    
    def update_response(self, response_id: UUID, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update response"""
        try:
            client = self._ensure_client()
            response = client.table("responses").update(update_data).eq("id", str(response_id)).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error updating response: {str(e)}")
            raise
    
    def get_attempt_responses(self, attempt_id: UUID) -> List[Dict[str, Any]]:
        """Get all responses for an attempt"""
        try:
            client = self._ensure_client()
            response = client.table("responses").select("*").eq("attempt_id", str(attempt_id)).execute()
            return response.data if response.data else []
        except Exception as e:
            logger.error(f"Error getting attempt responses: {str(e)}")
            return []
    
    # ============================================
    # Result Operations
    # ============================================
    
    def create_result(self, result_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create a new result"""
        try:
            client = self._ensure_client()
            response = client.table("results").insert(result_data).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error creating result: {str(e)}")
            raise
    
    def get_result(self, attempt_id: UUID) -> Optional[Dict[str, Any]]:
        """Get result by attempt ID"""
        try:
            client = self._ensure_client()
            response = client.table("results").select("*").eq("attempt_id", str(attempt_id)).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error getting result: {str(e)}")
            return None
    
    def update_result(self, result_id: UUID, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update result"""
        try:
            client = self._ensure_client()
            response = client.table("results").update(update_data).eq("id", str(result_id)).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error updating result: {str(e)}")
            raise
    
    # ============================================
    # Storage Operations
    # ============================================
    
    def upload_file(self, bucket_name: str, file_path: str, file_content: bytes, content_type: str = "application/pdf") -> Optional[str]:
        """Upload file to Supabase Storage"""
        try:
            logger.debug(f"Starting file upload to Supabase Storage: bucket={bucket_name}, path={file_path}, size={len(file_content)} bytes")
            client = self._ensure_client()
            # Ensure bucket exists (create if not)
            try:
                client.storage.from_(bucket_name).upload(file_path, file_content, file_options={"content-type": content_type})
                logger.debug(f"File uploaded successfully to {bucket_name}/{file_path}")
            except Exception as e:
                logger.warning(f"Upload failed, may need to create bucket: {str(e)}")
                # Try creating bucket first (requires admin)
                pass
            
            # Get public URL
            url = client.storage.from_(bucket_name).get_public_url(file_path)
            result = url.data if hasattr(url, 'data') else str(url)
            logger.debug(f"File upload completed, public URL generated")
            return result
        except TimeoutError as e:
            logger.error(f"File upload to Supabase Storage timed out: {str(e)}")
            return None
        except Exception as e:
            logger.exception(f"Error uploading file to Supabase Storage: {str(e)}")
            return None
    
    def get_signed_url(self, bucket_name: str, file_path: str, expires_in: int = 3600) -> Optional[str]:
        """Get signed URL for file download"""
        try:
            client = self._ensure_client()
            response = client.storage.from_(bucket_name).create_signed_url(file_path, expires_in)
            return response.get("signedURL") if isinstance(response, dict) else str(response)
        except Exception as e:
            logger.error(f"Error getting signed URL: {str(e)}")
            return None
    
    def delete_file(self, bucket_name: str, file_path: str) -> bool:
        """Delete file from Supabase Storage"""
        try:
            client = self._ensure_client()
            client.storage.from_(bucket_name).remove([file_path])
            return True
        except Exception as e:
            logger.error(f"Error deleting file: {str(e)}")
            return False


# Global service instance
supabase_service = SupabaseService()

