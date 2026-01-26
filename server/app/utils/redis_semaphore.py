"""
Redis-based distributed semaphore for concurrency control.
Implements atomic acquire/release with TTL for worker failure recovery.
"""

import logging
from typing import Optional
from contextlib import contextmanager
import redis
from app.config import REDIS_URL, MAX_GLOBAL_ACTIVE_SOLVES, MAX_PER_TENANT_ACTIVE

logger = logging.getLogger(__name__)


class RedisSemaphore:
    """
    Distributed semaphore using Redis with TTL for automatic cleanup.
    Supports global and per-tenant concurrency limits.
    """
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.global_key = "solver:semaphore:global"
        self.tenant_prefix = "solver:semaphore:tenant:"
    
    def try_acquire_global(self, worker_id: str, ttl_seconds: int = 300) -> bool:
        """
        Try to acquire global semaphore slot.
        
        Args:
            worker_id: Unique worker identifier
            ttl_seconds: Time-to-live for the slot (auto-release on worker death)
        
        Returns:
            True if acquired, False if limit reached
        """
        # Use Lua script for atomic check-and-increment
        lua_script = """
        local key = KEYS[1]
        local max_count = tonumber(ARGV[1])
        local worker_id = ARGV[2]
        local ttl = tonumber(ARGV[3])
        
        local current = redis.call('SCARD', key)
        if current < max_count then
            redis.call('SADD', key, worker_id)
            redis.call('EXPIRE', key, ttl)
            return 1
        else
            return 0
        end
        """
        
        try:
            result = self.redis.eval(
                lua_script,
                1,
                self.global_key,
                MAX_GLOBAL_ACTIVE_SOLVES,
                worker_id,
                ttl_seconds
            )
            
            acquired = bool(result)
            if acquired:
                logger.info(f"Worker {worker_id} acquired global semaphore slot")
            else:
                logger.warning(f"Worker {worker_id} failed to acquire global semaphore (limit: {MAX_GLOBAL_ACTIVE_SOLVES})")
            
            return acquired
        except Exception as e:
            logger.error(f"Error acquiring global semaphore: {e}")
            return False
    
    def release_global(self, worker_id: str) -> bool:
        """Release global semaphore slot."""
        try:
            removed = self.redis.srem(self.global_key, worker_id)
            if removed:
                logger.info(f"Worker {worker_id} released global semaphore slot")
            return bool(removed)
        except Exception as e:
            logger.error(f"Error releasing global semaphore: {e}")
            return False
    
    def try_acquire_tenant(self, tenant_id: str, worker_id: str, ttl_seconds: int = 300) -> bool:
        """
        Try to acquire per-tenant semaphore slot.
        
        Args:
            tenant_id: Tenant identifier
            worker_id: Unique worker identifier
            ttl_seconds: Time-to-live for the slot
        
        Returns:
            True if acquired, False if tenant limit reached
        """
        key = f"{self.tenant_prefix}{tenant_id}"
        
        lua_script = """
        local key = KEYS[1]
        local max_count = tonumber(ARGV[1])
        local worker_id = ARGV[2]
        local ttl = tonumber(ARGV[3])
        
        local current = redis.call('SCARD', key)
        if current < max_count then
            redis.call('SADD', key, worker_id)
            redis.call('EXPIRE', key, ttl)
            return 1
        else
            return 0
        end
        """
        
        try:
            result = self.redis.eval(
                lua_script,
                1,
                key,
                MAX_PER_TENANT_ACTIVE,
                worker_id,
                ttl_seconds
            )
            
            acquired = bool(result)
            if acquired:
                logger.info(f"Worker {worker_id} acquired tenant {tenant_id} semaphore slot")
            else:
                logger.warning(f"Worker {worker_id} failed to acquire tenant {tenant_id} semaphore (limit: {MAX_PER_TENANT_ACTIVE})")
            
            return acquired
        except Exception as e:
            logger.error(f"Error acquiring tenant semaphore: {e}")
            return False
    
    def release_tenant(self, tenant_id: str, worker_id: str) -> bool:
        """Release per-tenant semaphore slot."""
        key = f"{self.tenant_prefix}{tenant_id}"
        
        try:
            removed = self.redis.srem(key, worker_id)
            if removed:
                logger.info(f"Worker {worker_id} released tenant {tenant_id} semaphore slot")
            return bool(removed)
        except Exception as e:
            logger.error(f"Error releasing tenant semaphore: {e}")
            return False
    
    def get_global_active_count(self) -> int:
        """Get current number of active global slots."""
        try:
            return self.redis.scard(self.global_key)
        except Exception as e:
            logger.error(f"Error getting global active count: {e}")
            return 0
    
    def get_tenant_active_count(self, tenant_id: str) -> int:
        """Get current number of active slots for a tenant."""
        key = f"{self.tenant_prefix}{tenant_id}"
        try:
            return self.redis.scard(key)
        except Exception as e:
            logger.error(f"Error getting tenant active count: {e}")
            return 0
    
    @contextmanager
    def acquire_both(self, tenant_id: str, worker_id: str, ttl_seconds: int = 300):
        """
        Context manager to acquire both global and tenant semaphores.
        Automatically releases on exit (success or exception).
        
        Usage:
            with semaphore.acquire_both(tenant_id, worker_id):
                # Do work
                pass
        """
        global_acquired = False
        tenant_acquired = False
        
        try:
            # Try to acquire global first
            global_acquired = self.try_acquire_global(worker_id, ttl_seconds)
            if not global_acquired:
                raise ResourceUnavailableError("Global concurrency limit reached")
            
            # Try to acquire tenant
            tenant_acquired = self.try_acquire_tenant(tenant_id, worker_id, ttl_seconds)
            if not tenant_acquired:
                raise ResourceUnavailableError(f"Tenant {tenant_id} concurrency limit reached")
            
            yield  # Work happens here
            
        finally:
            # Release in reverse order
            if tenant_acquired:
                self.release_tenant(tenant_id, worker_id)
            if global_acquired:
                self.release_global(worker_id)
    
    def cleanup_stale_slots(self) -> int:
        """
        Emergency cleanup of potentially stale slots.
        This should rarely be needed due to TTL, but useful for maintenance.
        
        Returns:
            Number of slots cleaned
        """
        cleaned = 0
        try:
            # Get all tenant keys
            pattern = f"{self.tenant_prefix}*"
            for key in self.redis.scan_iter(match=pattern):
                # Check TTL - if no TTL set, the key is stale
                ttl = self.redis.ttl(key)
                if ttl == -1:  # No expiration
                    count = self.redis.scard(key)
                    self.redis.delete(key)
                    cleaned += count
                    logger.warning(f"Cleaned stale tenant semaphore key: {key} ({count} slots)")
            
            # Check global key
            global_ttl = self.redis.ttl(self.global_key)
            if global_ttl == -1:
                count = self.redis.scard(self.global_key)
                self.redis.delete(self.global_key)
                cleaned += count
                logger.warning(f"Cleaned stale global semaphore ({count} slots)")
            
            if cleaned > 0:
                logger.info(f"Cleaned {cleaned} total stale semaphore slots")
            
            return cleaned
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            return cleaned


class ResourceUnavailableError(Exception):
    """Raised when semaphore acquisition fails due to limits."""
    pass


# Global singleton
_redis_client: Optional[redis.Redis] = None
_semaphore: Optional[RedisSemaphore] = None


def get_redis_client() -> redis.Redis:
    """Get or create Redis client singleton."""
    global _redis_client
    if _redis_client is None:
        if not REDIS_URL:
            raise ValueError("REDIS_URL not configured")
        _redis_client = redis.from_url(REDIS_URL, decode_responses=False)
        logger.info("Redis client initialized")
    return _redis_client


def get_semaphore() -> RedisSemaphore:
    """Get or create semaphore singleton."""
    global _semaphore
    if _semaphore is None:
        _semaphore = RedisSemaphore(get_redis_client())
        logger.info("Redis semaphore initialized")
    return _semaphore
