"""
Caching utilities for the Greenside application.
Provides Redis-backed caching with automatic fallback to disk-backed caching
(via diskcache) for embeddings, source URLs, search results, and answers —
shared across Gunicorn workers.
"""
import hashlib
import pickle
import time
import os
import json
import logging
import re
from functools import lru_cache
from threading import Lock

import diskcache

try:
    import redis as redis_lib
except ImportError:
    redis_lib = None

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Redis connection (optional — falls back to diskcache when unavailable)
# ---------------------------------------------------------------------------
_REDIS_URL = os.environ.get('REDIS_URL')
_redis_client = None


def _get_redis():
    """Return a connected Redis client, or None if Redis is unavailable."""
    global _redis_client
    if _redis_client is None and _REDIS_URL and redis_lib is not None:
        try:
            _redis_client = redis_lib.Redis.from_url(
                _REDIS_URL, decode_responses=False
            )
            _redis_client.ping()
            logger.info("Redis cache backend connected")
        except Exception:
            logger.info("Redis unavailable, falling back to diskcache")
            _redis_client = None
    return _redis_client

DATA_DIR = os.environ.get('DATA_DIR', 'data' if os.path.exists('data') else '.')
CACHE_DIR = os.path.join(DATA_DIR, 'cache')


class EmbeddingCache:
    """
    Cache for OpenAI embeddings.
    Uses Redis when available, otherwise falls back to diskcache.
    Caches embeddings by query text hash to avoid redundant API calls.
    Shared across Gunicorn workers.
    """

    _PREFIX = 'emb:'

    def __init__(self, max_size=500, ttl_seconds=3600):
        """
        Initialize the embedding cache.

        Args:
            max_size: Maximum number of embeddings to cache (maps to diskcache size_limit heuristic)
            ttl_seconds: Time-to-live for cache entries (default 1 hour)
        """
        cache_path = os.path.join(CACHE_DIR, 'embeddings')
        os.makedirs(cache_path, exist_ok=True)
        # Estimate ~6KB per embedding (1536 floats) — size_limit is in bytes
        self._cache = diskcache.Cache(cache_path, size_limit=max_size * 6 * 1024)
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
        r = _get_redis()
        if r:
            try:
                data = r.get(f'{self._PREFIX}{key}')
                with self._lock:
                    if data is not None:
                        self._hits += 1
                        logger.debug(f"Cache hit for embedding [redis] (hits: {self._hits}, misses: {self._misses})")
                        return pickle.loads(data)
                    self._misses += 1
                    return None
            except Exception:
                logger.debug("Redis get failed for embedding, falling back to diskcache")

        # Fall back to diskcache
        value = self._cache.get(key, default=None)
        with self._lock:
            if value is not None:
                self._hits += 1
                logger.debug(f"Cache hit for embedding (hits: {self._hits}, misses: {self._misses})")
                return value
            self._misses += 1
            return None

    def set(self, text, model, embedding):
        """Store an embedding in the cache."""
        key = self._hash_key(text, model)
        r = _get_redis()
        if r:
            try:
                r.setex(f'{self._PREFIX}{key}', self._ttl, pickle.dumps(embedding))
                return
            except Exception:
                logger.debug("Redis set failed for embedding, falling back to diskcache")

        # Fall back to diskcache
        self._cache.set(key, embedding, expire=self._ttl)

    def stats(self):
        """Return cache statistics."""
        with self._lock:
            total = self._hits + self._misses
            hit_rate = (self._hits / total * 100) if total > 0 else 0
            backend = 'redis' if _get_redis() else 'diskcache'
            return {
                'size': len(self._cache),
                'max_size': self._max_size,
                'hits': self._hits,
                'misses': self._misses,
                'hit_rate': f"{hit_rate:.1f}%",
                'backend': backend,
            }

    def clear(self):
        """Clear the cache."""
        r = _get_redis()
        if r:
            try:
                cursor = 0
                while True:
                    cursor, keys = r.scan(cursor, match=f'{self._PREFIX}*', count=100)
                    if keys:
                        r.delete(*keys)
                    if cursor == 0:
                        break
            except Exception:
                logger.debug("Redis clear failed for embeddings")

        self._cache.clear()
        with self._lock:
            self._hits = 0
            self._misses = 0


class SourceURLCache:
    """
    Cache for source document URL lookups.
    Uses Redis when available, otherwise falls back to diskcache.
    Builds an index of PDF files on first access, then serves from cache.
    """

    _PREFIX = 'src:'

    def __init__(self, search_folders, rebuild_interval=300):
        """
        Initialize the source URL cache.

        Args:
            search_folders: List of folders to index
            rebuild_interval: Seconds between index rebuilds (default 5 minutes)
        """
        cache_path = os.path.join(CACHE_DIR, 'source_urls')
        os.makedirs(cache_path, exist_ok=True)
        self._cache = diskcache.Cache(cache_path, size_limit=50 * 1024 * 1024)  # 50MB
        self._search_folders = search_folders
        self._rebuild_interval = rebuild_interval
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

        r = _get_redis()
        if r:
            try:
                # Clear existing source keys
                cursor = 0
                while True:
                    cursor, keys = r.scan(cursor, match=f'{self._PREFIX}*', count=100)
                    if keys:
                        r.delete(*keys)
                    if cursor == 0:
                        break
                # Store each entry with prefix
                pipe = r.pipeline()
                for key, url in new_index.items():
                    pipe.set(f'{self._PREFIX}{key}', url.encode())
                pipe.set(f'{self._PREFIX}__last_build__', pickle.dumps(time.time()))
                pipe.set(f'{self._PREFIX}__index_size__', pickle.dumps(len(new_index)))
                pipe.execute()
                logger.info(f"Source URL cache rebuilt with {len(new_index)} entries [redis]")
                return
            except Exception:
                logger.debug("Redis build_index failed, falling back to diskcache")

        # Fall back to diskcache
        self._cache.clear()
        for key, url in new_index.items():
            self._cache.set(key, url)
        self._cache.set('__last_build__', time.time())
        self._cache.set('__index_size__', len(new_index))

        logger.info(f"Source URL cache rebuilt with {len(new_index)} entries")

    def _needs_rebuild(self):
        """Check if the index needs to be rebuilt."""
        r = _get_redis()
        if r:
            try:
                data = r.get(f'{self._PREFIX}__last_build__')
                last_build = pickle.loads(data) if data else 0
                return time.time() - last_build > self._rebuild_interval
            except Exception:
                pass

        # Fall back to diskcache
        last_build = self._cache.get('__last_build__', default=0)
        return time.time() - last_build > self._rebuild_interval

    def get(self, source_name):
        """
        Get the URL for a source document.

        Args:
            source_name: Name of the source (with or without .pdf extension)

        Returns:
            URL string or None if not found
        """
        # Rebuild index if stale
        if self._needs_rebuild():
            self._build_index()

        key = source_name.lower().replace('.pdf', '')

        r = _get_redis()
        if r:
            try:
                data = r.get(f'{self._PREFIX}{key}')
                if data is not None:
                    return data.decode()
                return None
            except Exception:
                logger.debug("Redis get failed for source URL, falling back to diskcache")

        # Fall back to diskcache
        return self._cache.get(key, default=None)

    def rebuild(self):
        """Force rebuild of the index."""
        self._build_index()

    def stats(self):
        """Return cache statistics."""
        r = _get_redis()
        if r:
            try:
                lb_data = r.get(f'{self._PREFIX}__last_build__')
                is_data = r.get(f'{self._PREFIX}__index_size__')
                last_build = pickle.loads(lb_data) if lb_data else 0
                index_size = pickle.loads(is_data) if is_data else 0
                return {
                    'size': index_size,
                    'last_build': last_build,
                    'age_seconds': time.time() - last_build if last_build > 0 else None,
                    'backend': 'redis',
                }
            except Exception:
                pass

        # Fall back to diskcache
        last_build = self._cache.get('__last_build__', default=0)
        index_size = self._cache.get('__index_size__', default=0)
        return {
            'size': index_size,
            'last_build': last_build,
            'age_seconds': time.time() - last_build if last_build > 0 else None,
            'backend': 'diskcache',
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
    try:
        response = openai_client.embeddings.create(input=text, model=model)
        embedding = response.data[0].embedding
    except Exception as e:
        logging.getLogger(__name__).error(f"Embedding API call failed: {e}")
        raise

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


class SearchResultCache:
    """
    Cache for Pinecone search results.
    Uses Redis when available, otherwise falls back to diskcache.
    Caches complete search results to avoid redundant vector database calls.
    Uses query hash + parameters as key. Shared across Gunicorn workers.
    """

    _PREFIX = 'search:'

    def __init__(self, max_size=200, ttl_seconds=300):
        """
        Initialize the search result cache.

        Args:
            max_size: Maximum number of queries to cache
            ttl_seconds: Time-to-live for cache entries (default 5 minutes)
        """
        cache_path = os.path.join(CACHE_DIR, 'search_results')
        os.makedirs(cache_path, exist_ok=True)
        # Estimate ~10KB per search result set
        self._cache = diskcache.Cache(cache_path, size_limit=max_size * 10 * 1024)
        self._max_size = max_size
        self._ttl = ttl_seconds
        self._lock = Lock()
        self._hits = 0
        self._misses = 0

    def _hash_key(self, query, search_type, filters=None):
        """Generate a hash key for the cache."""
        content = f"{search_type}:{query}:{json.dumps(filters or {}, sort_keys=True)}"
        return hashlib.sha256(content.encode()).hexdigest()[:20]

    def get(self, query, search_type, filters=None):
        """
        Get search results from cache if available and not expired.

        Returns:
            Cached results dict or None if not found/expired
        """
        key = self._hash_key(query, search_type, filters)
        r = _get_redis()
        if r:
            try:
                data = r.get(f'{self._PREFIX}{key}')
                with self._lock:
                    if data is not None:
                        self._hits += 1
                        logger.debug(f"Search cache hit [redis] (hits: {self._hits}, misses: {self._misses})")
                        return pickle.loads(data)
                    self._misses += 1
                    return None
            except Exception:
                logger.debug("Redis get failed for search results, falling back to diskcache")

        # Fall back to diskcache
        value = self._cache.get(key, default=None)
        with self._lock:
            if value is not None:
                self._hits += 1
                logger.debug(f"Search cache hit (hits: {self._hits}, misses: {self._misses})")
                return value
            self._misses += 1
            return None

    def set(self, query, search_type, results, filters=None):
        """Store search results in the cache."""
        key = self._hash_key(query, search_type, filters)
        r = _get_redis()
        if r:
            try:
                r.setex(f'{self._PREFIX}{key}', self._ttl, pickle.dumps(results))
                return
            except Exception:
                logger.debug("Redis set failed for search results, falling back to diskcache")

        # Fall back to diskcache
        self._cache.set(key, results, expire=self._ttl)

    def stats(self):
        """Return cache statistics."""
        with self._lock:
            total = self._hits + self._misses
            hit_rate = (self._hits / total * 100) if total > 0 else 0
            backend = 'redis' if _get_redis() else 'diskcache'
            return {
                'size': len(self._cache),
                'max_size': self._max_size,
                'hits': self._hits,
                'misses': self._misses,
                'hit_rate': f"{hit_rate:.1f}%",
                'backend': backend,
            }

    def clear(self):
        """Clear the cache."""
        r = _get_redis()
        if r:
            try:
                cursor = 0
                while True:
                    cursor, keys = r.scan(cursor, match=f'{self._PREFIX}*', count=100)
                    if keys:
                        r.delete(*keys)
                    if cursor == 0:
                        break
            except Exception:
                logger.debug("Redis clear failed for search results")

        self._cache.clear()
        with self._lock:
            self._hits = 0
            self._misses = 0


class AnswerCache:
    """
    Cache for complete answer responses.
    Uses Redis when available, otherwise falls back to diskcache.
    Caches final answers by normalized question hash to avoid redundant LLM calls
    for repeat/similar questions. Shared across Gunicorn workers.
    """

    _PREFIX = 'ans:'

    def __init__(self, max_size=300, ttl_seconds=3600):
        cache_path = os.path.join(CACHE_DIR, 'answers')
        os.makedirs(cache_path, exist_ok=True)
        # Estimate ~5KB per answer
        self._cache = diskcache.Cache(cache_path, size_limit=max_size * 5 * 1024)
        self._max_size = max_size
        self._ttl = ttl_seconds
        self._lock = Lock()
        self._hits = 0
        self._misses = 0

    def _normalize_query(self, query):
        """Normalize query for cache key: lowercase, strip, collapse whitespace."""
        normalized = query.lower().strip()
        normalized = re.sub(r'\s+', ' ', normalized)
        # Remove trailing punctuation
        normalized = re.sub(r'[?.!]+$', '', normalized)
        return normalized

    def _hash_key(self, query, course_id=None):
        """Generate hash key from normalized query + course context."""
        normalized = self._normalize_query(query)
        content = f"{course_id or 'default'}:{normalized}"
        return hashlib.sha256(content.encode()).hexdigest()[:20]

    def get(self, query, course_id=None):
        """Get a cached answer if available and not expired."""
        key = self._hash_key(query, course_id)
        r = _get_redis()
        if r:
            try:
                data = r.get(f'{self._PREFIX}{key}')
                with self._lock:
                    if data is not None:
                        self._hits += 1
                        logger.debug(f"Answer cache hit [redis] (hits: {self._hits}, misses: {self._misses})")
                        return pickle.loads(data)
                    self._misses += 1
                    return None
            except Exception:
                logger.debug("Redis get failed for answer, falling back to diskcache")

        # Fall back to diskcache
        value = self._cache.get(key, default=None)
        with self._lock:
            if value is not None:
                self._hits += 1
                logger.debug(f"Answer cache hit (hits: {self._hits}, misses: {self._misses})")
                return value
            self._misses += 1
            return None

    def set(self, query, answer_data, course_id=None):
        """Store an answer in the cache. answer_data should be a dict with answer, sources, confidence, etc."""
        key = self._hash_key(query, course_id)
        r = _get_redis()
        if r:
            try:
                r.setex(f'{self._PREFIX}{key}', self._ttl, pickle.dumps(answer_data))
                return
            except Exception:
                logger.debug("Redis set failed for answer, falling back to diskcache")

        # Fall back to diskcache
        self._cache.set(key, answer_data, expire=self._ttl)

    def invalidate(self, query, course_id=None):
        """Remove a specific entry from cache (e.g., after feedback)."""
        key = self._hash_key(query, course_id)
        r = _get_redis()
        if r:
            try:
                r.delete(f'{self._PREFIX}{key}')
                return
            except Exception:
                logger.debug("Redis delete failed for answer, falling back to diskcache")

        # Fall back to diskcache
        self._cache.delete(key)

    def stats(self):
        """Return cache statistics."""
        with self._lock:
            total = self._hits + self._misses
            hit_rate = (self._hits / total * 100) if total > 0 else 0
            backend = 'redis' if _get_redis() else 'diskcache'
            return {
                'size': len(self._cache),
                'max_size': self._max_size,
                'hits': self._hits,
                'misses': self._misses,
                'hit_rate': f"{hit_rate:.1f}%",
                'backend': backend,
            }

    def clear(self):
        """Clear the cache."""
        r = _get_redis()
        if r:
            try:
                cursor = 0
                while True:
                    cursor, keys = r.scan(cursor, match=f'{self._PREFIX}*', count=100)
                    if keys:
                        r.delete(*keys)
                    if cursor == 0:
                        break
            except Exception:
                logger.debug("Redis clear failed for answers")

        self._cache.clear()
        with self._lock:
            self._hits = 0
            self._misses = 0


# Global answer cache instance
_answer_cache = None


def get_answer_cache():
    """Get or create the global answer cache."""
    global _answer_cache
    if _answer_cache is None:
        _answer_cache = AnswerCache(max_size=300, ttl_seconds=3600)
    return _answer_cache


# Global search cache instance
_search_cache = None


def get_search_cache():
    """Get or create the global search result cache."""
    global _search_cache
    if _search_cache is None:
        _search_cache = SearchResultCache(max_size=200, ttl_seconds=300)
    return _search_cache


def get_cached_search_results(index, embedding, search_type, top_k, filters=None, query_text=""):
    """
    Get search results, using cache when available.

    Args:
        index: Pinecone index
        embedding: Query embedding vector
        search_type: Type of search (general, product, timing)
        top_k: Number of results
        filters: Optional Pinecone filter dict
        query_text: Original query text for cache key

    Returns:
        Search results dict
    """
    cache = get_search_cache()

    # Try cache first
    cached = cache.get(query_text, search_type, filters)
    if cached is not None:
        return cached

    # Execute search
    try:
        if filters:
            results = index.query(
                vector=embedding,
                top_k=top_k,
                filter=filters,
                include_metadata=True
            )
        else:
            results = index.query(
                vector=embedding,
                top_k=top_k,
                include_metadata=True
            )

        # Convert to serializable dict and cache
        results_dict = {'matches': []}
        for match in results.get('matches', []):
            results_dict['matches'].append({
                'id': match.get('id', ''),
                'score': match.get('score', 0),
                'metadata': dict(match.get('metadata', {}))
            })

        cache.set(query_text, search_type, results_dict, filters)
        return results_dict

    except Exception as e:
        logger.error(f"Search failed: {e}")
        return {'matches': []}
