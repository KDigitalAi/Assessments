"""
Embedding service for generating query embeddings only
Uses OpenAI embeddings API for topic search (does not store new embeddings)
"""

from typing import List, Optional
from openai import OpenAI
from openai import APITimeoutError, APIConnectionError, RateLimitError, APIError
import time
from app.config import settings
from app.utils.logger import logger


class EmbeddingService:
    """Service for generating query embeddings (only for topic search, not for storing)"""
    
    def __init__(self):
        """Initialize embedding service"""
        self.client = None
        self._initialize_openai_client()
    
    def _initialize_openai_client(self):
        """Initialize OpenAI client with timeout configuration"""
        try:
            if settings.OPENAI_API_KEY and "your-openai" not in settings.OPENAI_API_KEY:
                # Configure timeout: 60s connect, 300s read/write (5 minutes for large batches)
                from openai import Timeout
                timeout = Timeout(connect=60.0, read=300.0, write=300.0, pool=300.0)
                self.client = OpenAI(
                    api_key=settings.OPENAI_API_KEY,
                    timeout=timeout
                )
            else:
                logger.warning("OpenAI API key not configured. Embedding features will not work.")
                self.client = None
        except Exception as e:
            logger.error(f"Error initializing OpenAI client: {str(e)}")
            self.client = None
    
    def generate_embedding(self, text: str) -> Optional[List[float]]:
        """
        Generate embedding for a single text
        
        Args:
            text: Text to embed
        
        Returns:
            Embedding vector or None
        """
        try:
            if not self.client:
                logger.error("OpenAI client not initialized")
                return None
            
            # Ensure text is not empty
            if not text or not text.strip():
                logger.warning("Empty text provided for embedding")
                return None
            
            # Truncate very long texts (OpenAI has token limits)
            # text-embedding-3-small supports up to 8191 tokens
            # Roughly 1 token = 4 characters, so ~32k characters
            max_chars = 30000
            if len(text) > max_chars:
                text = text[:max_chars]
                logger.warning(f"Text truncated to {max_chars} characters for embedding")
            
            logger.debug(f"Generating embedding for text (length: {len(text)} chars)")
            response = self.client.embeddings.create(
                model=settings.OPENAI_EMBEDDING_MODEL,
                input=text
            )
            
            if not response.data or len(response.data) == 0:
                logger.error("OpenAI embedding API returned empty data")
                return None
            
            return response.data[0].embedding
            
        except APITimeoutError as e:
            logger.error(f"Timeout error generating embedding: {str(e)}")
            logger.error("Request took too long - consider reducing chunk size or checking network")
            return None
        except APIConnectionError as e:
            logger.error(f"Connection error generating embedding: {str(e)}")
            logger.error("Network connectivity issue - check internet connection")
            return None
        except RateLimitError as e:
            logger.error(f"Rate limit error generating embedding: {str(e)}")
            logger.error("API rate limit exceeded - wait before retrying")
            return None
        except APIError as e:
            logger.error(f"OpenAI API error generating embedding: {str(e)}")
            logger.error(f"API error type: {type(e).__name__}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error generating embedding: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            return None
    
    def generate_embeddings_batch(self, texts: List[str], batch_size: int = 100) -> List[Optional[List[float]]]:
        """
        Generate embeddings for multiple texts in batches
        
        Args:
            texts: List of texts to embed
            batch_size: Number of texts to process per batch
        
        Returns:
            List of embedding vectors (None for failed embeddings)
        """
        try:
            if not self.client:
                logger.error("OpenAI client not initialized")
                return [None] * len(texts)
            
            embeddings = []
            
            # Process in batches
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                
                # Filter out empty texts
                valid_texts = []
                valid_indices = []
                for idx, text in enumerate(batch):
                    if text and text.strip():
                        # Truncate if needed
                        if len(text) > 30000:
                            text = text[:30000]
                        valid_texts.append(text)
                        valid_indices.append(idx)
                
                if not valid_texts:
                    embeddings.extend([None] * len(batch))
                    continue
                
                # Retry logic for network issues
                max_retries = 3
                retry_delay = 2  # Start with 2 seconds
                batch_num = i//batch_size + 1
                
                for attempt in range(max_retries):
                    try:
                        if attempt > 0:
                            logger.info(f"  Retry attempt {attempt}/{max_retries-1} for batch {batch_num}...")
                            time.sleep(retry_delay * attempt)  # Exponential backoff
                        
                        logger.info(f"  Calling OpenAI API for batch {batch_num} ({len(valid_texts)} texts)...")
                        response = self.client.embeddings.create(
                            model=settings.OPENAI_EMBEDDING_MODEL,
                            input=valid_texts
                        )
                        
                        # Map embeddings back to original positions
                        batch_embeddings = [None] * len(batch)
                        for idx, embedding_data in enumerate(response.data):
                            original_idx = valid_indices[idx]
                            batch_embeddings[original_idx] = embedding_data.embedding
                        
                        embeddings.extend(batch_embeddings)
                        logger.info(f"  Successfully generated {len(valid_texts)} embeddings for batch {batch_num}")
                        break  # Success, exit retry loop
                        
                    except APITimeoutError as e:
                        if attempt < max_retries - 1:
                            logger.warning(f"  Timeout on batch {batch_num}, attempt {attempt+1}/{max_retries}: {str(e)}")
                            continue
                        else:
                            logger.error(f"  [FAILED] Timeout error in batch {batch_num} after {max_retries} attempts: {str(e)}")
                            logger.error("  Request timed out - network may be slow or batch too large")
                            embeddings.extend([None] * len(batch))
                    except APIConnectionError as e:
                        if attempt < max_retries - 1:
                            logger.warning(f"  Connection error on batch {batch_num}, attempt {attempt+1}/{max_retries}: {str(e)}")
                            continue
                        else:
                            logger.error(f"  [FAILED] Connection error in batch {batch_num} after {max_retries} attempts: {str(e)}")
                            logger.error("  Network connectivity issue - check internet connection")
                            embeddings.extend([None] * len(batch))
                    except RateLimitError as e:
                        # Rate limits need longer wait
                        wait_time = retry_delay * (2 ** attempt) * 5  # Longer wait for rate limits
                        if attempt < max_retries - 1:
                            logger.warning(f"  Rate limit on batch {batch_num}, waiting {wait_time}s before retry {attempt+1}/{max_retries}")
                            time.sleep(wait_time)
                            continue
                        else:
                            logger.error(f"  [FAILED] Rate limit error in batch {batch_num} after {max_retries} attempts: {str(e)}")
                            logger.error("  API rate limit exceeded - wait before processing more")
                            embeddings.extend([None] * len(batch))
                    except APIError as e:
                        logger.error(f"  [FAILED] OpenAI API error in batch {batch_num}: {str(e)}")
                        logger.error(f"  API error type: {type(e).__name__}")
                        embeddings.extend([None] * len(batch))
                        break  # Don't retry API errors (they won't succeed on retry)
                    except Exception as e:
                        import traceback
                        logger.error(f"  [FAILED] Unexpected error in batch {batch_num}: {str(e)}")
                        logger.error(f"  Error type: {type(e).__name__}")
                        logger.error(f"  Full traceback:\n{traceback.format_exc()}")
                        embeddings.extend([None] * len(batch))
                        break  # Don't retry unexpected errors
            
            return embeddings
            
        except Exception as e:
            logger.error(f"Error generating batch embeddings: {str(e)}")
            return [None] * len(texts)


# Global service instance
embedding_service = EmbeddingService()

