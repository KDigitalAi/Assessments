"""
Embedding service for generating query embeddings only
Uses OpenAI embeddings API for topic search (does not store new embeddings)
"""

from typing import List, Optional
from openai import OpenAI
from app.config import settings
from app.utils.logger import logger


class EmbeddingService:
    """Service for generating query embeddings (only for topic search, not for storing)"""
    
    def __init__(self):
        """Initialize embedding service"""
        self.client = None
        self._initialize_openai_client()
    
    def _initialize_openai_client(self):
        """Initialize OpenAI client"""
        try:
            if settings.OPENAI_API_KEY and "your-openai" not in settings.OPENAI_API_KEY:
                self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
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
            
            response = self.client.embeddings.create(
                model=settings.OPENAI_EMBEDDING_MODEL,
                input=text
            )
            
            return response.data[0].embedding
            
        except Exception as e:
            logger.error(f"Error generating embedding: {str(e)}")
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
                
                try:
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
                    
                except Exception as e:
                    logger.error(f"Error in batch embedding generation: {str(e)}")
                    embeddings.extend([None] * len(batch))
            
            return embeddings
            
        except Exception as e:
            logger.error(f"Error generating batch embeddings: {str(e)}")
            return [None] * len(texts)


# Global service instance
embedding_service = EmbeddingService()

