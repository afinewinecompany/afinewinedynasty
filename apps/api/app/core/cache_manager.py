"""Cache Manager for ML Inference Service

Provides Redis-based caching for models, predictions, and feature data
with configurable TTL and cache invalidation strategies.
"""

import json
import pickle
import time
from typing import Any, Dict, List, Optional, Union
import logging

import redis.asyncio as redis
from redis.asyncio import ConnectionPool

from .config import settings

logger = logging.getLogger(__name__)


class CacheManager:
    """Redis-based cache manager for ML inference service."""

    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.connection_pool: Optional[ConnectionPool] = None
        self._metrics = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
            "errors": 0
        }

    async def initialize(self):
        """Initialize Redis connection pool and client."""
        try:
            # Create connection pool for better performance
            self.connection_pool = ConnectionPool.from_url(
                settings.REDIS_URL,
                max_connections=20,
                retry_on_timeout=True,
                health_check_interval=30
            )

            # Create Redis client
            self.redis_client = redis.Redis(
                connection_pool=self.connection_pool,
                decode_responses=False  # Keep binary for pickle data
            )

            # Test connection
            await self.redis_client.ping()
            logger.info("Cache manager initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize cache manager: {e}")
            raise

    async def close(self):
        """Close Redis connections."""
        if self.redis_client:
            await self.redis_client.close()
        if self.connection_pool:
            await self.connection_pool.disconnect()

    async def health_check(self) -> Dict[str, Any]:
        """Health check for Redis connection."""
        try:
            if not self.redis_client:
                return {"status": "unhealthy", "error": "Redis client not initialized"}

            # Test ping
            await self.redis_client.ping()

            # Get basic info
            info = await self.redis_client.info()

            return {
                "status": "healthy",
                "connected_clients": info.get("connected_clients", 0),
                "used_memory_human": info.get("used_memory_human", "unknown"),
                "hits": self._metrics["hits"],
                "misses": self._metrics["misses"]
            }

        except Exception as e:
            logger.error(f"Cache health check failed: {e}")
            return {"status": "unhealthy", "error": str(e)}

    async def get_metrics(self) -> Dict[str, Any]:
        """Get cache performance metrics."""
        hit_rate = 0
        if self._metrics["hits"] + self._metrics["misses"] > 0:
            hit_rate = self._metrics["hits"] / (self._metrics["hits"] + self._metrics["misses"])

        return {
            **self._metrics,
            "hit_rate": hit_rate,
            "timestamp": time.time()
        }

    # Model caching methods
    async def cache_model(self, model_key: str, model_data: bytes, ttl: int = 3600):
        """Cache model data with specified TTL (default 1 hour)."""
        try:
            await self.redis_client.setex(
                f"model:{model_key}",
                ttl,
                model_data
            )
            self._metrics["sets"] += 1
            logger.info(f"Model cached: {model_key} (TTL: {ttl}s)")

        except Exception as e:
            self._metrics["errors"] += 1
            logger.error(f"Failed to cache model {model_key}: {e}")
            raise

    async def get_cached_model(self, model_key: str) -> Optional[bytes]:
        """Retrieve cached model data."""
        try:
            data = await self.redis_client.get(f"model:{model_key}")
            if data:
                self._metrics["hits"] += 1
                logger.debug(f"Model cache hit: {model_key}")
                return data
            else:
                self._metrics["misses"] += 1
                logger.debug(f"Model cache miss: {model_key}")
                return None

        except Exception as e:
            self._metrics["errors"] += 1
            logger.error(f"Failed to get cached model {model_key}: {e}")
            return None

    # Prediction caching methods
    async def cache_prediction(
        self,
        prospect_id: int,
        model_version: str,
        prediction_data: Dict[str, Any],
        ttl: int = 86400
    ):
        """Cache prediction result with 24-hour TTL."""
        try:
            cache_key = f"prediction:{prospect_id}:{model_version}"
            prediction_json = json.dumps(prediction_data)

            await self.redis_client.setex(
                cache_key,
                ttl,
                prediction_json
            )
            self._metrics["sets"] += 1
            logger.debug(f"Prediction cached: {cache_key}")

        except Exception as e:
            self._metrics["errors"] += 1
            logger.error(f"Failed to cache prediction for prospect {prospect_id}: {e}")

    async def get_cached_prediction(
        self,
        prospect_id: int,
        model_version: str
    ) -> Optional[Dict[str, Any]]:
        """Retrieve cached prediction result."""
        try:
            cache_key = f"prediction:{prospect_id}:{model_version}"
            data = await self.redis_client.get(cache_key)

            if data:
                self._metrics["hits"] += 1
                logger.debug(f"Prediction cache hit: {cache_key}")
                return json.loads(data.decode('utf-8'))
            else:
                self._metrics["misses"] += 1
                logger.debug(f"Prediction cache miss: {cache_key}")
                return None

        except Exception as e:
            self._metrics["errors"] += 1
            logger.error(f"Failed to get cached prediction for prospect {prospect_id}: {e}")
            return None

    # Feature caching methods
    async def cache_prospect_features(
        self,
        prospect_id: int,
        features: Dict[str, Any],
        ttl: int = 1800  # 30 minutes
    ):
        """Cache prospect features for reuse."""
        try:
            cache_key = f"features:{prospect_id}"
            features_json = json.dumps(features)

            await self.redis_client.setex(
                cache_key,
                ttl,
                features_json
            )
            self._metrics["sets"] += 1
            logger.debug(f"Features cached: {cache_key}")

        except Exception as e:
            self._metrics["errors"] += 1
            logger.error(f"Failed to cache features for prospect {prospect_id}: {e}")

    async def get_cached_features(self, cache_key: Union[int, str]) -> Optional[Dict[str, Any]]:
        """Retrieve cached prospect features or generic cached data.

        Args:
            cache_key: Either a prospect_id (int) or a custom cache key (str)
        """
        try:
            # Check if Redis client is initialized
            if not self.redis_client:
                logger.warning("Redis client not initialized, skipping cache lookup")
                return None

            # Handle both int (prospect_id) and string (custom key) inputs
            if isinstance(cache_key, int):
                final_key = f"features:{cache_key}"
            else:
                final_key = cache_key

            data = await self.redis_client.get(final_key)

            if data:
                self._metrics["hits"] += 1
                logger.debug(f"Features cache hit: {final_key}")
                return json.loads(data.decode('utf-8'))
            else:
                self._metrics["misses"] += 1
                logger.debug(f"Features cache miss: {final_key}")
                return None

        except Exception as e:
            self._metrics["errors"] += 1
            logger.error(f"Failed to get cached features for {cache_key}: {e}")
            return None

    async def cache_features(
        self,
        cache_key: str,
        features: Dict[str, Any],
        ttl: int = 1800  # 30 minutes
    ):
        """Cache generic feature data with custom key.

        Args:
            cache_key: Custom cache key (string)
            features: Data to cache
            ttl: Time to live in seconds (default 30 minutes)
        """
        try:
            # Check if Redis client is initialized
            if not self.redis_client:
                logger.warning("Redis client not initialized, skipping cache write")
                return

            features_json = json.dumps(features)

            await self.redis_client.setex(
                cache_key,
                ttl,
                features_json
            )
            self._metrics["sets"] += 1
            logger.debug(f"Features cached: {cache_key}")

        except Exception as e:
            self._metrics["errors"] += 1
            logger.error(f"Failed to cache features for {cache_key}: {e}")

    # Cache invalidation methods
    async def invalidate_model_cache(self, model_key: str):
        """Invalidate cached model data."""
        try:
            await self.redis_client.delete(f"model:{model_key}")
            self._metrics["deletes"] += 1
            logger.info(f"Model cache invalidated: {model_key}")

        except Exception as e:
            self._metrics["errors"] += 1
            logger.error(f"Failed to invalidate model cache {model_key}: {e}")

    async def invalidate_prospect_predictions(self, prospect_id: int):
        """Invalidate all cached predictions for a prospect."""
        try:
            # Find all prediction keys for this prospect
            pattern = f"prediction:{prospect_id}:*"
            keys = await self.redis_client.keys(pattern)

            if keys:
                await self.redis_client.delete(*keys)
                self._metrics["deletes"] += len(keys)
                logger.info(f"Invalidated {len(keys)} prediction caches for prospect {prospect_id}")

        except Exception as e:
            self._metrics["errors"] += 1
            logger.error(f"Failed to invalidate predictions for prospect {prospect_id}: {e}")

    async def invalidate_all_predictions(self):
        """Invalidate all cached predictions (use with model updates)."""
        try:
            pattern = "prediction:*"
            keys = await self.redis_client.keys(pattern)

            if keys:
                # Delete in batches to avoid blocking
                batch_size = 1000
                for i in range(0, len(keys), batch_size):
                    batch = keys[i:i + batch_size]
                    await self.redis_client.delete(*batch)

                self._metrics["deletes"] += len(keys)
                logger.info(f"Invalidated {len(keys)} prediction caches")

        except Exception as e:
            self._metrics["errors"] += 1
            logger.error(f"Failed to invalidate all predictions: {e}")

    # Narrative caching methods
    async def cache_narrative(
        self,
        prospect_id: int,
        model_version: str,
        user_id: Optional[int],
        narrative_data: str,
        template_version: str = "v1.0",
        ttl: int = 86400  # 24 hours
    ):
        """Cache generated narrative with 24-hour TTL."""
        try:
            # Create composite cache key including user context
            user_suffix = f":{user_id}" if user_id else ":default"
            cache_key = f"narrative:{prospect_id}:{model_version}:{template_version}{user_suffix}"

            # Store narrative with metadata
            narrative_cache = {
                "narrative": narrative_data,
                "template_version": template_version,
                "model_version": model_version,
                "cached_at": time.time()
            }

            narrative_json = json.dumps(narrative_cache)

            await self.redis_client.setex(
                cache_key,
                ttl,
                narrative_json
            )
            self._metrics["sets"] += 1
            logger.debug(f"Narrative cached: {cache_key}")

        except Exception as e:
            self._metrics["errors"] += 1
            logger.error(f"Failed to cache narrative for prospect {prospect_id}: {e}")

    async def get_cached_narrative(
        self,
        prospect_id: int,
        model_version: str,
        user_id: Optional[int] = None,
        template_version: str = "v1.0"
    ) -> Optional[str]:
        """Retrieve cached narrative."""
        try:
            user_suffix = f":{user_id}" if user_id else ":default"
            cache_key = f"narrative:{prospect_id}:{model_version}:{template_version}{user_suffix}"
            data = await self.redis_client.get(cache_key)

            if data:
                self._metrics["hits"] += 1
                logger.debug(f"Narrative cache hit: {cache_key}")
                narrative_cache = json.loads(data.decode('utf-8'))
                return narrative_cache["narrative"]
            else:
                self._metrics["misses"] += 1
                logger.debug(f"Narrative cache miss: {cache_key}")
                return None

        except Exception as e:
            self._metrics["errors"] += 1
            logger.error(f"Failed to get cached narrative for prospect {prospect_id}: {e}")
            return None

    async def invalidate_prospect_narratives(self, prospect_id: int):
        """Invalidate all cached narratives for a prospect."""
        try:
            pattern = f"narrative:{prospect_id}:*"
            keys = await self.redis_client.keys(pattern)

            if keys:
                await self.redis_client.delete(*keys)
                self._metrics["deletes"] += len(keys)
                logger.info(f"Invalidated {len(keys)} narrative caches for prospect {prospect_id}")

        except Exception as e:
            self._metrics["errors"] += 1
            logger.error(f"Failed to invalidate narratives for prospect {prospect_id}: {e}")

    async def invalidate_template_caches(self, template_version: str):
        """Invalidate all narratives using a specific template version."""
        try:
            pattern = f"narrative:*:{template_version}:*"
            keys = await self.redis_client.keys(pattern)

            if keys:
                # Delete in batches to avoid blocking
                batch_size = 1000
                for i in range(0, len(keys), batch_size):
                    batch = keys[i:i + batch_size]
                    await self.redis_client.delete(*batch)

                self._metrics["deletes"] += len(keys)
                logger.info(f"Invalidated {len(keys)} narrative caches for template {template_version}")

        except Exception as e:
            self._metrics["errors"] += 1
            logger.error(f"Failed to invalidate template caches for {template_version}: {e}")

    async def cache_user_preferences(
        self,
        user_id: int,
        preferences: Dict[str, Any],
        ttl: int = 3600  # 1 hour
    ):
        """Cache user preferences for personalization."""
        try:
            cache_key = f"user_prefs:{user_id}"
            prefs_json = json.dumps(preferences)

            await self.redis_client.setex(
                cache_key,
                ttl,
                prefs_json
            )
            self._metrics["sets"] += 1
            logger.debug(f"User preferences cached: {cache_key}")

        except Exception as e:
            self._metrics["errors"] += 1
            logger.error(f"Failed to cache user preferences for user {user_id}: {e}")

    async def get_cached_user_preferences(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve cached user preferences."""
        try:
            cache_key = f"user_prefs:{user_id}"
            data = await self.redis_client.get(cache_key)

            if data:
                self._metrics["hits"] += 1
                logger.debug(f"User preferences cache hit: {cache_key}")
                return json.loads(data.decode('utf-8'))
            else:
                self._metrics["misses"] += 1
                logger.debug(f"User preferences cache miss: {cache_key}")
                return None

        except Exception as e:
            self._metrics["errors"] += 1
            logger.error(f"Failed to get cached user preferences for user {user_id}: {e}")
            return None

    async def cache_popular_prospects(
        self,
        prospect_ids: List[int],
        ttl: int = 7200  # 2 hours
    ):
        """Cache list of popular prospects for warming."""
        try:
            cache_key = "popular_prospects"
            prospects_json = json.dumps(prospect_ids)

            await self.redis_client.setex(
                cache_key,
                ttl,
                prospects_json
            )
            self._metrics["sets"] += 1
            logger.debug(f"Popular prospects cached: {len(prospect_ids)} prospects")

        except Exception as e:
            self._metrics["errors"] += 1
            logger.error(f"Failed to cache popular prospects: {e}")

    async def get_popular_prospects(self) -> List[int]:
        """Retrieve cached popular prospects list."""
        try:
            cache_key = "popular_prospects"
            data = await self.redis_client.get(cache_key)

            if data:
                self._metrics["hits"] += 1
                return json.loads(data.decode('utf-8'))
            else:
                self._metrics["misses"] += 1
                return []

        except Exception as e:
            self._metrics["errors"] += 1
            logger.error(f"Failed to get cached popular prospects: {e}")
            return []

    # Cache warming methods
    async def warm_cache_for_prospects(self, prospect_ids: List[int]):
        """Pre-warm cache for frequently accessed prospects."""
        try:
            logger.info(f"Starting cache warming for {len(prospect_ids)} prospects")
            # This would trigger feature extraction and caching
            # Implementation depends on the feature extraction service
            # For now, just log the intent
            logger.info("Cache warming completed")

        except Exception as e:
            logger.error(f"Cache warming failed: {e}")

    async def warm_narrative_cache(
        self,
        prospect_ids: List[int],
        model_version: str = "v1.0",
        template_version: str = "v1.0"
    ):
        """Pre-warm narrative cache for popular prospects."""
        try:
            logger.info(f"Starting narrative cache warming for {len(prospect_ids)} prospects")

            # Store warming queue for processing
            warming_data = {
                "prospect_ids": prospect_ids,
                "model_version": model_version,
                "template_version": template_version,
                "queued_at": time.time()
            }

            await self.redis_client.setex(
                "narrative_warming_queue",
                3600,  # 1 hour
                json.dumps(warming_data)
            )

            logger.info(f"Narrative cache warming queued for {len(prospect_ids)} prospects")

        except Exception as e:
            logger.error(f"Narrative cache warming failed: {e}")

    # Utility methods
    async def get_cache_info(self) -> Dict[str, Any]:
        """Get general cache information and statistics."""
        try:
            info = await self.redis_client.info()
            return {
                "connected_clients": info.get("connected_clients", 0),
                "used_memory": info.get("used_memory", 0),
                "used_memory_human": info.get("used_memory_human", "unknown"),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "total_commands_processed": info.get("total_commands_processed", 0)
            }

        except Exception as e:
            logger.error(f"Failed to get cache info: {e}")
            return {}


# Singleton instance
cache_manager = CacheManager()