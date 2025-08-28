"""
Embeddings response caching system using JSON format.

Provides a local filesystem cache for embeddings responses to avoid redundant API calls
and reduce costs. Uses FIFO eviction policy with configurable size limits.
"""

import hashlib
import json
import os
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..config.paths import get_cache_dir
from ..core.logging import get_logger

logger = get_logger()


class EmbeddingCache:
    """
    Local filesystem cache for embedding responses with FIFO eviction policy.
    
    Features:
    - JSON-based storage for portability and human-readable format
    - Configurable size limit (default 500MB)
    - FIFO eviction when size limit is reached
    - Thread-safe operations
    - Persistent across application restarts
    """
    
    def __init__(self, max_size_mb: int = 500):
        """
        Initialize the embedding cache.
        
        Args:
            max_size_mb: Maximum cache size in megabytes (default 500MB)
        """
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.cache_dir = get_cache_dir() / "embeddings"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.cache_dir / "index.json"
        self._lock = threading.Lock()
        
        # Load existing cache index or create new one
        self._load_index()
    
    def _load_index(self) -> None:
        """Load the cache index from disk."""
        try:
            if self.index_file.exists():
                with open(self.index_file, 'r') as f:
                    data = json.load(f)
                    self.index = data.get('entries', {})
                    self.access_order = data.get('access_order', [])
            else:
                self.index = {}
                self.access_order = []
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load cache index: {e}. Starting with empty cache.")
            self.index = {}
            self.access_order = []
    
    def _save_index(self) -> None:
        """Save the cache index to disk."""
        try:
            index_data = {
                'entries': self.index,
                'access_order': self.access_order
            }
            with open(self.index_file, 'w') as f:
                json.dump(index_data, f, indent=2)
        except IOError as e:
            logger.error(f"Failed to save cache index: {e}")
    
    def _get_cache_key(self, model: str, text: str) -> str:
        """Generate a cache key from model and text using SHA256."""
        content = f"{model}:{text}"
        return hashlib.sha256(content.encode()).hexdigest()
    
    def _get_cache_file_path(self, cache_key: str) -> Path:
        """Get the file path for a cache entry."""
        return self.cache_dir / f"{cache_key}.json"
    
    def _get_current_size(self) -> int:
        """Calculate total size of cache files in bytes."""
        total_size = 0
        try:
            if self.index_file.exists():
                total_size += self.index_file.stat().st_size
            
            for cache_key in self.index:
                cache_file = self._get_cache_file_path(cache_key)
                if cache_file.exists():
                    total_size += cache_file.stat().st_size
        except OSError as e:
            logger.warning(f"Error calculating cache size: {e}")
        
        return total_size
    
    def _evict_oldest(self) -> None:
        """Evict the oldest cache entry (FIFO)."""
        if not self.access_order:
            return
        
        oldest_key = self.access_order.pop(0)
        if oldest_key in self.index:
            cache_file = self._get_cache_file_path(oldest_key)
            try:
                if cache_file.exists():
                    cache_file.unlink()
                del self.index[oldest_key]
                logger.debug(f"Evicted cache entry: {oldest_key}")
            except OSError as e:
                logger.error(f"Failed to evict cache entry {oldest_key}: {e}")
    
    def _enforce_size_limit(self) -> None:
        """Enforce cache size limit by evicting oldest entries."""
        while self._get_current_size() > self.max_size_bytes and self.access_order:
            self._evict_oldest()
    
    def get(self, model: str, text: str) -> Optional[List[float]]:
        """
        Retrieve embedding from cache.
        
        Args:
            model: The embedding model name
            text: The input text
            
        Returns:
            The cached embedding as List[float], or None if not found
        """
        cache_key = self._get_cache_key(model, text)
        
        with self._lock:
            if cache_key not in self.index:
                return None
            
            cache_file = self._get_cache_file_path(cache_key)
            if not cache_file.exists():
                # Clean up stale index entry
                del self.index[cache_key]
                if cache_key in self.access_order:
                    self.access_order.remove(cache_key)
                self._save_index()
                return None
            
            try:
                with open(cache_file, 'r') as f:
                    data = json.load(f)
                
                # Update access order (move to end for FIFO)
                if cache_key in self.access_order:
                    self.access_order.remove(cache_key)
                self.access_order.append(cache_key)
                
                # Update access time in index
                self.index[cache_key]['last_accessed'] = time.time()
                self._save_index()
                
                logger.debug(f"Cache hit for key: {cache_key}")
                return data['embedding']
                
            except (json.JSONDecodeError, KeyError, IOError) as e:
                logger.error(f"Failed to read cache entry {cache_key}: {e}")
                return None
    
    def put(self, model: str, text: str, embedding: List[float]) -> None:
        """
        Store embedding in cache.
        
        Args:
            model: The embedding model name
            text: The input text
            embedding: The embedding to cache
        """
        cache_key = self._get_cache_key(model, text)
        cache_file = self._get_cache_file_path(cache_key)
        
        with self._lock:
            try:
                # Prepare cache entry data
                cache_data = {
                    'model': model,
                    'text': text,
                    'embedding': embedding,
                    'created_at': time.time()
                }
                
                # Write cache file
                with open(cache_file, 'w') as f:
                    json.dump(cache_data, f)
                
                # Update index
                self.index[cache_key] = {
                    'created_at': cache_data['created_at'],
                    'last_accessed': cache_data['created_at'],
                    'model': model
                }
                
                # Update access order
                if cache_key in self.access_order:
                    self.access_order.remove(cache_key)
                self.access_order.append(cache_key)
                
                self._save_index()
                logger.debug(f"Cached embedding for key: {cache_key}")
                
                # Enforce size limit after adding new entry
                self._enforce_size_limit()
                
            except IOError as e:
                logger.error(f"Failed to cache embedding {cache_key}: {e}")
    
    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            try:
                # Remove all cache files
                for cache_key in list(self.index.keys()):
                    cache_file = self._get_cache_file_path(cache_key)
                    if cache_file.exists():
                        cache_file.unlink()
                
                # Clear index
                self.index.clear()
                self.access_order.clear()
                self._save_index()
                
                logger.info("Cache cleared")
                
            except OSError as e:
                logger.error(f"Failed to clear cache: {e}")
    
    def get_stats(self) -> Dict[str, any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary containing cache statistics
        """
        with self._lock:
            return {
                'entries': len(self.index),
                'size_bytes': self._get_current_size(),
                'size_mb': round(self._get_current_size() / (1024 * 1024), 2),
                'max_size_mb': round(self.max_size_bytes / (1024 * 1024), 2),
                'utilization_percent': round(
                    (self._get_current_size() / self.max_size_bytes) * 100, 2
                ) if self.max_size_bytes > 0 else 0
            }


# Global cache instance
_cache_instance: Optional[EmbeddingCache] = None
_cache_lock = threading.Lock()


def get_cache(max_size_mb: int = 500) -> EmbeddingCache:
    """
    Get or create the global cache instance.
    
    Args:
        max_size_mb: Maximum cache size in megabytes (only used for first call)
        
    Returns:
        The global EmbeddingCache instance
    """
    global _cache_instance
    
    if _cache_instance is None:
        with _cache_lock:
            if _cache_instance is None:
                _cache_instance = EmbeddingCache(max_size_mb)
    
    return _cache_instance