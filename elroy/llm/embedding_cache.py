import hashlib
import json
import os
import pickle
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..config.paths import get_cache_dir
from ..core.logging import get_logger

logger = get_logger()


class EmbeddingCache:
    """
    A filesystem-based FIFO cache for embedding responses.
    
    Features:
    - Size-limited cache (default 500MB)
    - FIFO eviction policy
    - Persistent across sessions
    - Fast lookups using hashed keys
    """
    
    def __init__(self, max_size_mb: int = 500):
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.cache_dir = get_cache_dir() / "embeddings"
        self.cache_dir.mkdir(exist_ok=True)
        self.index_file = self.cache_dir / "index.json"
        self._load_index()
    
    def _load_index(self) -> None:
        """Load the cache index from disk or create new one."""
        try:
            if self.index_file.exists():
                with open(self.index_file, 'r') as f:
                    self.index = json.load(f)
            else:
                self.index = {"entries": [], "total_size": 0}
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load cache index, creating new one: {e}")
            self.index = {"entries": [], "total_size": 0}
    
    def _save_index(self) -> None:
        """Save the cache index to disk."""
        try:
            with open(self.index_file, 'w') as f:
                json.dump(self.index, f)
        except IOError as e:
            logger.error(f"Failed to save cache index: {e}")
    
    def _get_cache_key(self, model_name: str, text: str) -> str:
        """Generate a cache key from model and text."""
        # Create a deterministic hash of model + text
        content = f"{model_name}:{text}"
        return hashlib.sha256(content.encode()).hexdigest()
    
    def _get_cache_path(self, cache_key: str) -> Path:
        """Get the file path for a cache entry."""
        return self.cache_dir / f"{cache_key}.pkl"
    
    def _evict_old_entries(self, needed_size: int) -> None:
        """Evict old entries to make space using FIFO policy."""
        while (self.index["total_size"] + needed_size > self.max_size_bytes and 
               self.index["entries"]):
            # Remove the oldest entry (FIFO)
            oldest_entry = self.index["entries"].pop(0)
            cache_path = self._get_cache_path(oldest_entry["key"])
            
            try:
                if cache_path.exists():
                    cache_path.unlink()
                self.index["total_size"] -= oldest_entry["size"]
                logger.debug(f"Evicted cache entry: {oldest_entry['key']}")
            except OSError as e:
                logger.warning(f"Failed to remove cache file {cache_path}: {e}")
    
    def get(self, model_name: str, text: str) -> Optional[List[float]]:
        """
        Retrieve a cached embedding if available.
        
        Args:
            model_name: The embedding model name
            text: The input text
            
        Returns:
            The cached embedding or None if not found
        """
        cache_key = self._get_cache_key(model_name, text)
        cache_path = self._get_cache_path(cache_key)
        
        if not cache_path.exists():
            return None
        
        try:
            with open(cache_path, 'rb') as f:
                embedding = pickle.load(f)
            logger.debug(f"Cache hit for key: {cache_key}")
            return embedding
        except (pickle.PickleError, IOError) as e:
            logger.warning(f"Failed to load cache entry {cache_key}: {e}")
            # Clean up corrupted file
            try:
                cache_path.unlink()
            except OSError:
                pass
            return None
    
    def put(self, model_name: str, text: str, embedding: List[float]) -> None:
        """
        Store an embedding in the cache.
        
        Args:
            model_name: The embedding model name
            text: The input text
            embedding: The embedding to cache
        """
        cache_key = self._get_cache_key(model_name, text)
        cache_path = self._get_cache_path(cache_key)
        
        # Serialize the embedding to calculate size
        try:
            data = pickle.dumps(embedding)
            entry_size = len(data)
            
            # Evict old entries if needed
            self._evict_old_entries(entry_size)
            
            # Write the new entry
            with open(cache_path, 'wb') as f:
                f.write(data)
            
            # Update index - remove existing entry if present
            self.index["entries"] = [
                entry for entry in self.index["entries"] 
                if entry["key"] != cache_key
            ]
            
            # Add new entry
            self.index["entries"].append({
                "key": cache_key,
                "size": entry_size,
                "timestamp": time.time()
            })
            self.index["total_size"] += entry_size
            
            self._save_index()
            logger.debug(f"Cached embedding for key: {cache_key}, size: {entry_size} bytes")
            
        except (pickle.PickleError, IOError) as e:
            logger.error(f"Failed to cache embedding: {e}")
    
    def clear(self) -> None:
        """Clear all cached entries."""
        try:
            for entry in self.index["entries"]:
                cache_path = self._get_cache_path(entry["key"])
                if cache_path.exists():
                    cache_path.unlink()
            
            self.index = {"entries": [], "total_size": 0}
            self._save_index()
            logger.info("Cleared all cache entries")
        except OSError as e:
            logger.error(f"Failed to clear cache: {e}")
    
    def get_stats(self) -> Dict:
        """Get cache statistics."""
        return {
            "total_entries": len(self.index["entries"]),
            "total_size_bytes": self.index["total_size"],
            "total_size_mb": round(self.index["total_size"] / (1024 * 1024), 2),
            "max_size_mb": round(self.max_size_bytes / (1024 * 1024), 2)
        }


# Global cache instance
_cache_instance: Optional[EmbeddingCache] = None


def get_embedding_cache(max_size_mb: int = 500) -> EmbeddingCache:
    """Get or create the global embedding cache instance."""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = EmbeddingCache(max_size_mb)
    return _cache_instance