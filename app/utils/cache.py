"""
In-memory caching utility with TTL support
"""

from typing import Any, Optional, Callable
from datetime import datetime, timedelta, timezone
import hashlib
import json
import asyncio
from threading import Lock

from app.utils.logger import logger


class CacheEntry:
    """Cache entry with TTL"""
    
    def __init__(self, value: Any, ttl_seconds: int = 300):
        self.value = value
        self.created_at = datetime.now(timezone.utc)
        self.ttl_seconds = ttl_seconds
    
    @property
    def is_expired(self) -> bool:
        """Check if cache entry is expired - optimized datetime reuse"""
        now = datetime.now(timezone.utc)
        age = (now - self.created_at).total_seconds()
        return age > self.ttl_seconds
    
    @property
    def expires_at(self) -> datetime:
        """Get expiration timestamp"""
        return self.created_at + timedelta(seconds=self.ttl_seconds)


class Cache:
    """Thread-safe in-memory cache with TTL"""
    
    def __init__(self, default_ttl: int = 300):
        """
        Initialize cache
        
        Args:
            default_ttl: Default TTL in seconds (default: 5 minutes)
        """
        self._cache: dict[str, CacheEntry] = {}
        self._lock = Lock()
        self.default_ttl = default_ttl
        self._cleanup_task: Optional[asyncio.Task] = None
    
    def _generate_key(self, prefix: str, *args, **kwargs) -> str:
        """Generate cache key from arguments - optimized"""
        # Optimized: avoid dict creation if no args/kwargs
        if not args and not kwargs:
            return hashlib.md5(prefix.encode()).hexdigest()
        
        key_data = {
            "prefix": prefix,
            "args": args,
            "kwargs": sorted(kwargs.items()) if kwargs else []
        }
        key_str = json.dumps(key_data, sort_keys=True, default=str)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            
            if entry.is_expired:
                del self._cache[key]
                return None
            
            return entry.value
    
    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        """Set value in cache"""
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        
        with self._lock:
            self._cache[key] = CacheEntry(value, ttl)
    
    def delete(self, key: str) -> bool:
        """Delete key from cache"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    def clear(self) -> None:
        """Clear all cache entries"""
        with self._lock:
            self._cache.clear()
    
    def get_or_set(
        self,
        key: str,
        factory: Callable[[], Any],
        ttl_seconds: Optional[int] = None
    ) -> Any:
        """
        Get value from cache or set it using factory function
        
        Args:
            key: Cache key
            factory: Function to generate value if not cached
            ttl_seconds: Optional TTL override
        
        Returns:
            Cached or newly generated value
        """
        value = self.get(key)
        if value is not None:
            return value
        
        value = factory()
        self.set(key, value, ttl_seconds)
        return value
    
    async def cleanup_expired(self) -> None:
        """Remove expired entries from cache - optimized single pass"""
        with self._lock:
            # Single pass - delete expired entries directly
            expired_count = 0
            keys_to_delete = []
            for key, entry in self._cache.items():
                if entry.is_expired:
                    keys_to_delete.append(key)
            
            for key in keys_to_delete:
                del self._cache[key]
                expired_count += 1
            
            if expired_count > 0:
                logger.debug(f"Cleaned up {expired_count} expired cache entries")
    
    def stats(self) -> dict:
        """Get cache statistics - optimized single pass"""
        with self._lock:
            total = len(self._cache)
            # Optimized: single pass with generator
            expired = sum(1 for entry in self._cache.values() if entry.is_expired)
            active = total - expired
            
            return {
                "total_entries": total,
                "expired_entries": expired,
                "active_entries": active
            }


# Global cache instance
cache = Cache(default_ttl=300)  # 5 minutes default TTL

