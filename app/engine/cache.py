"""
Response Caching — Tiered caching (L1 exact-match, L2 semantic, L3 TTL)
to balance response latency with RAG retrieval quality.
"""

import hashlib
import time
from typing import Any, Dict, Optional, Tuple
from dataclasses import dataclass, field
from collections import OrderedDict
from datetime import datetime, timedelta
import threading

from app.core.logging import logger

#  CONFIGURATION

# Cache size limits
L1_MAX_SIZE = 500  # Max entries in exact-match cache
L2_MAX_SIZE = 200  # Max entries in semantic cache
L3_TTL_SECONDS = 300  # RAG retrieval cache TTL

# Question patterns that should NEVER be cached
NO_CACHE_PATTERNS = [
    "my proposal",
    "my plan",
    "i think",
    "should i",
    "what if",
    "how do you feel",
    "remember when",
    "last time",
    "you said",
]

# Question patterns that are SAFE to cache
CACHEABLE_PATTERNS = [
    "what is",
    "define",
    "explain",
    "what are the",
    "list the",
    "describe",
    "who is",
    "vept framework",
    "competency",
]

@dataclass
class CacheEntry:
    """A single cache entry with metadata."""
    key: str
    value: str
    agent_id: str
    created_at: datetime
    access_count: int = 0
    last_accessed: datetime = field(default_factory=datetime.now)

class LRUCache:
    """Thread-safe LRU cache with size limit."""
    
    def __init__(self, max_size: int):
        self.max_size = max_size
        self.cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self.lock = threading.RLock()
        self.hits = 0
        self.misses = 0
    
    def get(self, key: str) -> Optional[CacheEntry]:
        """Get entry and move to end (most recently used)."""
        with self.lock:
            if key in self.cache:
                self.cache.move_to_end(key)
                entry = self.cache[key]
                entry.access_count += 1
                entry.last_accessed = datetime.now()
                self.hits += 1
                return entry
            self.misses += 1
            return None
    
    def put(self, key: str, value: str, agent_id: str):
        """Add entry, evicting oldest if at capacity."""
        with self.lock:
            if key in self.cache:
                self.cache.move_to_end(key)
            else:
                if len(self.cache) >= self.max_size:
                    self.cache.popitem(last=False)
                self.cache[key] = CacheEntry(
                    key=key,
                    value=value,
                    agent_id=agent_id,
                    created_at=datetime.now(),
                )
    
    def invalidate(self, key: str = None):
        """Invalidate specific key or entire cache."""
        with self.lock:
            if key:
                self.cache.pop(key, None)
            else:
                self.cache.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self.lock:
            total = self.hits + self.misses
            return {
                "size": len(self.cache),
                "max_size": self.max_size,
                "hits": self.hits,
                "misses": self.misses,
                "hit_rate": self.hits / total if total > 0 else 0,
            }

#  RESPONSE CACHE MANAGER

class ResponseCacheManager:
    """
    Multi-tier response caching system.
    
    L1 (Exact Match): Hash of normalized question → response
    L2 (Semantic): Embedding similarity → response (placeholder for production)
    L3 (RAG Cache): Query → retrieved documents (with TTL)
    """
    
    def __init__(self):
        self.l1_cache = LRUCache(L1_MAX_SIZE)
        self.l2_cache = LRUCache(L2_MAX_SIZE)  # Placeholder for semantic cache
        self.l3_cache: Dict[str, Tuple[Any, datetime]] = {}  # RAG cache with TTL
        self.l3_lock = threading.RLock()
    
    def _normalize_question(self, question: str) -> str:
        """Normalize question for cache key generation."""
        # Lowercase, strip, remove extra whitespace
        normalized = " ".join(question.lower().strip().split())
        return normalized
    
    def _hash_question(self, question: str, agent_id: str) -> str:
        """Generate cache key from question + agent."""
        normalized = self._normalize_question(question)
        combined = f"{agent_id}:{normalized}"
        return hashlib.sha256(combined.encode()).hexdigest()[:16]
    
    def _is_cacheable(self, question: str) -> bool:
        """
        Determine if a question should be cached.
        
        Caching Strategy:
        - Cache: Factual questions about frameworks, definitions, processes
        - Don't Cache: Personalized, context-dependent, or emotional questions
        """
        question_lower = question.lower()
        
        # Never cache if contains personal context
        if any(pattern in question_lower for pattern in NO_CACHE_PATTERNS):
            return False
        
        # Safe to cache if matches factual patterns
        if any(pattern in question_lower for pattern in CACHEABLE_PATTERNS):
            return True
        
        # Default: don't cache (prefer quality over speed)
        return False
    
    def get_cached_response(
        self,
        question: str,
        agent_id: str,
    ) -> Optional[Tuple[str, str]]:
        """
        Try to get cached response.
        
        Args:
            question: User's question
            agent_id: Which agent is responding
        
        Returns:
            Tuple of (response, cache_tier) if hit, None if miss
        """
        if not self._is_cacheable(question):
            logger.debug(f"Question not cacheable: {question[:50]}...")
            return None
        
        cache_key = self._hash_question(question, agent_id)
        
        # L1: Exact match
        l1_entry = self.l1_cache.get(cache_key)
        if l1_entry:
            logger.info(f"L1 Cache HIT for {agent_id}")
            return (l1_entry.value, "L1")
        
        # L2: Semantic similarity (placeholder - would use embeddings in production)
        # In production, this would compute embedding similarity
        # For now, we skip L2
        
        logger.debug(f"Cache MISS for {agent_id}: {question[:50]}...")
        return None
    
    def cache_response(
        self,
        question: str,
        agent_id: str,
        response: str,
    ):
        """Cache a response for future use."""
        if not self._is_cacheable(question):
            return
        
        cache_key = self._hash_question(question, agent_id)
        self.l1_cache.put(cache_key, response, agent_id)
        logger.debug(f"Cached response for {agent_id}: {question[:50]}...")
    
    def get_rag_cache(self, query: str) -> Optional[Any]:
        """Get cached RAG retrieval result."""
        with self.l3_lock:
            if query in self.l3_cache:
                result, timestamp = self.l3_cache[query]
                if datetime.now() - timestamp < timedelta(seconds=L3_TTL_SECONDS):
                    logger.debug(f"L3 RAG Cache HIT")
                    return result
                else:
                    # Expired
                    del self.l3_cache[query]
            return None
    
    def cache_rag_result(self, query: str, result: Any):
        """Cache RAG retrieval result with TTL."""
        with self.l3_lock:
            self.l3_cache[query] = (result, datetime.now())
            
            # Clean up expired entries periodically
            if len(self.l3_cache) > 100:
                self._cleanup_l3_cache()
    
    def _cleanup_l3_cache(self):
        """Remove expired L3 cache entries."""
        now = datetime.now()
        expired = [
            k for k, (_, ts) in self.l3_cache.items()
            if now - ts > timedelta(seconds=L3_TTL_SECONDS)
        ]
        for k in expired:
            del self.l3_cache[k]
    
    def invalidate_all(self):
        """Invalidate all caches (e.g., after knowledge base update)."""
        self.l1_cache.invalidate()
        self.l2_cache.invalidate()
        with self.l3_lock:
            self.l3_cache.clear()
        logger.info("All caches invalidated")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics."""
        with self.l3_lock:
            l3_size = len(self.l3_cache)
        
        return {
            "l1": self.l1_cache.get_stats(),
            "l2": self.l2_cache.get_stats(),
            "l3": {"size": l3_size, "ttl_seconds": L3_TTL_SECONDS},
        }

#  STREAMING RESPONSE UTILITIES

async def stream_response_tokens(
    response_text: str,
    chunk_size: int = 10,
    delay_ms: float = 30,
):
    """
    Generator for streaming response tokens with simulated typing effect.
    
    This improves perceived latency by showing text incrementally
    while the full response is being generated.
    
    Args:
        response_text: Full response text
        chunk_size: Number of characters per chunk
        delay_ms: Delay between chunks in milliseconds
    
    Yields:
        Text chunks for streaming
    """
    import asyncio
    
    words = response_text.split(' ')
    current_chunk = []
    
    for word in words:
        current_chunk.append(word)
        if len(' '.join(current_chunk)) >= chunk_size:
            yield ' '.join(current_chunk) + ' '
            current_chunk = []
            await asyncio.sleep(delay_ms / 1000)
    
    if current_chunk:
        yield ' '.join(current_chunk)

#  LATENCY METRICS TRACKING

class LatencyTracker:
    """Track latency metrics for optimization."""
    
    def __init__(self):
        self.metrics: Dict[str, list] = {
            "l1_hits": [],
            "l2_hits": [],
            "full_rag": [],
            "llm_inference": [],
            "total": [],
        }
        self.lock = threading.Lock()
    
    def record(self, metric_name: str, latency_ms: float):
        """Record a latency measurement."""
        with self.lock:
            if metric_name not in self.metrics:
                self.metrics[metric_name] = []
            
            self.metrics[metric_name].append(latency_ms)
            
            # Keep only last 1000 measurements
            if len(self.metrics[metric_name]) > 1000:
                self.metrics[metric_name] = self.metrics[metric_name][-1000:]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get latency statistics."""
        with self.lock:
            stats = {}
            for name, values in self.metrics.items():
                if values:
                    stats[name] = {
                        "count": len(values),
                        "avg_ms": sum(values) / len(values),
                        "min_ms": min(values),
                        "max_ms": max(values),
                        "p50_ms": sorted(values)[len(values) // 2],
                        "p95_ms": sorted(values)[int(len(values) * 0.95)] if len(values) > 20 else max(values),
                    }
            return stats

#  GLOBAL INSTANCES

# Global cache manager instance
response_cache = ResponseCacheManager()

# Global latency tracker
latency_tracker = LatencyTracker()

def get_cache_manager() -> ResponseCacheManager:
    """Get the global response cache manager."""
    return response_cache

def get_latency_tracker() -> LatencyTracker:
    """Get the global latency tracker."""
    return latency_tracker
