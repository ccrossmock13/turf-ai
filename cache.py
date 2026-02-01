"""
Caching utilities for the Greenside application.
Provides in-memory caching for embeddings and source URLs to reduce API calls and file system operations.
"""
import hashlib
import time
import os
import logging
from functools import lru_cache
from threading import Lock

logger = logging.getLogger(__name__)


class EmbeddingCache:
    """
    Thread-safe LRU cache for OpenAI embeddings.
    Caches embeddings by query text hash to avoid redundant API calls.
    """

    def __init__(self, max_size=500, ttl_seconds=3600):
        """
        Initialize the embedding cache.

        Args:
            max_size: Maximum number of embeddings to cache
            ttl_seconds: Time-to-live for cache entries (default 1 hour)
        """
        self._cache = {}
        self._access_times = {}
        self._max_size = max_size
        self._ttl = ttl_seconds
        self._lock = Lock()
        self._hits = 0
        self._misses = 0

    def _hash_key(self, text, model):
        """Generate a hash key for the cache."""
        content = f"{model}:{text}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def get(self, text, model):
        """
        Get an embedding from cache if available and not expired.

        Returns:
            Cached embedding or None if not found/expired
        """
        key = self._hash_key(text, model)
        with self._lock:
            if key in self._cache:
                entry_time = self._access_times.get(key, 0)
                if time.time() - entry_time < self._ttl:
                    self._hits += 1
                    logger.debug(f"Cache hit for embedding (hits: {self._hits}, misses: {self._misses})")
                    return self._cache[key]
                else:
                    # Expired
                    del self._cache[key]
                    del self._access_times[key]
            self._misses += 1
            return None

    def set(self, text, model, embedding):
        """Store an embedding in the cache."""
        key = self._hash_key(text, model)
        with self._lock:
            # Evict oldest entries if at capacity
            if len(self._cache) >= self._max_size:
                self._evict_oldest()

            self._cache[key] = embedding
            self._access_times[key] = time.time()

    def _evict_oldest(self):
        """Remove the oldest cache entries (25% of cache)."""
        if not self._access_times:
            return

        # Sort by access time and remove oldest 25%
        sorted_keys = sorted(self._access_times.items(), key=lambda x: x[1])
        num_to_remove = max(1, len(sorted_keys) // 4)

        for key, _ in sorted_keys[:num_to_remove]:
            self._cache.pop(key, None)
            self._access_times.pop(key, None)

    def stats(self):
        """Return cache statistics."""
        with self._lock:
            total = self._hits + self._misses
            hit_rate = (self._hits / total * 100) if total > 0 else 0
            return {
                'size': len(self._cache),
                'max_size': self._max_size,
                'hits': self._hits,
                'misses': self._misses,
                'hit_rate': f"{hit_rate:.1f}%"
            }

    def clear(self):
        """Clear the cache."""
        with self._lock:
            self._cache.clear()
            self._access_times.clear()
            self._hits = 0
            self._misses = 0


class SourceURLCache:
    """
    Cache for source document URL lookups.
    Builds an index of PDF files on first access, then serves from memory.
    """

    def __init__(self, search_folders, rebuild_interval=300):
        """
        Initialize the source URL cache.

        Args:
            search_folders: List of folders to index
            rebuild_interval: Seconds between index rebuilds (default 5 minutes)
        """
        self._index = {}
        self._search_folders = search_folders
        self._rebuild_interval = rebuild_interval
        self._last_build = 0
        self._lock = Lock()

    def _build_index(self):
        """Build the source name to URL index."""
        new_index = {}
        for folder in self._search_folders:
            if os.path.exists(folder):
                for root, dirs, files in os.walk(folder):
                    for file in files:
                        if file.lower().endswith('.pdf'):
                            # Key by lowercase name without extension
                            key = file.lower().replace('.pdf', '')
                            relative_path = os.path.join(root, file).replace('static/', '')
                            new_index[key] = f'/static/{relative_path}'

        with self._lock:
            self._index = new_index
            self._last_build = time.time()

        logger.info(f"Source URL cache rebuilt with {len(new_index)} entries")

    def get(self, source_name):
        """
        Get the URL for a source document.

        Args:
            source_name: Name of the source (with or without .pdf extension)

        Returns:
            URL string or None if not found
        """
        # Rebuild index if stale
        if time.time() - self._last_build > self._rebuild_interval:
            self._build_index()

        key = source_name.lower().replace('.pdf', '')
        with self._lock:
            return self._index.get(key)

    def rebuild(self):
        """Force rebuild of the index."""
        self._build_index()

    def stats(self):
        """Return cache statistics."""
        with self._lock:
            return {
                'size': len(self._index),
                'last_build': self._last_build,
                'age_seconds': time.time() - self._last_build if self._last_build > 0 else None
            }


# Global cache instances
_embedding_cache = None
_source_url_cache = None


def get_embedding_cache():
    """Get or create the global embedding cache."""
    global _embedding_cache
    if _embedding_cache is None:
        # Increased cache size for better hit rate
        # TTL of 2 hours balances freshness with performance
        _embedding_cache = EmbeddingCache(max_size=1000, ttl_seconds=7200)
    return _embedding_cache


def get_source_url_cache(search_folders=None):
    """Get or create the global source URL cache."""
    global _source_url_cache
    if _source_url_cache is None:
        if search_folders is None:
            from constants import SEARCH_FOLDERS
            search_folders = SEARCH_FOLDERS
        _source_url_cache = SourceURLCache(search_folders)
    return _source_url_cache


def get_cached_embedding(openai_client, text, model="text-embedding-3-small"):
    """
    Get an embedding, using cache when available.

    Args:
        openai_client: OpenAI client instance
        text: Text to embed
        model: Embedding model name

    Returns:
        Embedding vector
    """
    cache = get_embedding_cache()

    # Try cache first
    embedding = cache.get(text, model)
    if embedding is not None:
        return embedding

    # Generate new embedding
    response = openai_client.embeddings.create(input=text, model=model)
    embedding = response.data[0].embedding

    # Store in cache
    cache.set(text, model, embedding)
    return embedding


def get_cached_source_url(source_name, search_folders=None):
    """
    Get source URL using cache.

    Args:
        source_name: Name of the source document
        search_folders: Optional list of folders to search

    Returns:
        URL string or None
    """
    cache = get_source_url_cache(search_folders)
    return cache.get(source_name)
