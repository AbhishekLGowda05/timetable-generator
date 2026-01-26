"""
Redis-backed persistent job queue.

Provides durable job storage with:
- Job persistence across server restarts
- Distributed worker support
- Status streaming via pub/sub
- Cancellation support
- Timeout handling
"""

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
import threading

logger = logging.getLogger(__name__)

# Try to import redis, fall back to mock if not available
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis not available, using in-memory fallback")


class JobStatus(Enum):
    """Possible states for a solver job."""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Job:
    """Represents a timetable solver job."""
    job_id: str
    status: JobStatus = JobStatus.QUEUED
    progress: int = 0
    solver_input: dict = field(default_factory=dict)
    result: Optional[dict] = None
    error: Optional[str] = None
    logs: list = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    school_id: Optional[str] = None
    cancelled: bool = False
    
    def to_dict(self) -> dict:
        """Convert job to dictionary for storage/API responses."""
        return {
            "job_id": self.job_id,
            "status": self.status.value if isinstance(self.status, JobStatus) else self.status,
            "progress": self.progress,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error": self.error,
            "logs": self.logs,
            "school_id": self.school_id,
            "cancelled": self.cancelled,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Job":
        """Create Job from dictionary."""
        status = data.get("status", "queued")
        if isinstance(status, str):
            status = JobStatus(status)
        
        return cls(
            job_id=data["job_id"],
            status=status,
            progress=data.get("progress", 0),
            solver_input=data.get("solver_input", {}),
            result=data.get("result"),
            error=data.get("error"),
            logs=data.get("logs", []),
            created_at=data.get("created_at", datetime.utcnow().isoformat()),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            school_id=data.get("school_id"),
            cancelled=data.get("cancelled", False),
        )


class RedisJobQueue:
    """
    Redis-backed job queue with persistence and pub/sub for status updates.
    
    Key structure:
    - job:{job_id} - Hash containing job metadata
    - job:{job_id}:input - String containing solver input JSON
    - job:{job_id}:result - String containing result JSON
    - job:{job_id}:logs - List of log entries
    - jobs:pending - List of pending job IDs (FIFO queue)
    - jobs:active - Set of currently running job IDs
    - jobs:all - Set of all job IDs
    - job:{job_id}:cancel - Flag for cancellation
    """
    
    # Key prefixes
    JOB_KEY = "job:{}"
    JOB_INPUT_KEY = "job:{}:input"
    JOB_RESULT_KEY = "job:{}:result"
    JOB_LOGS_KEY = "job:{}:logs"
    JOB_CANCEL_KEY = "job:{}:cancel"
    PENDING_QUEUE = "jobs:pending"
    ACTIVE_SET = "jobs:active"
    ALL_JOBS_SET = "jobs:all"
    STATUS_CHANNEL = "jobs:status:{}"
    
    # TTLs
    JOB_TTL_SECONDS = 86400 * 7  # 7 days
    RESULT_TTL_SECONDS = 86400 * 30  # 30 days
    
    def __init__(
        self,
        redis_url: Optional[str] = None,
        max_jobs: int = 100,
    ):
        """
        Initialize the Redis job queue.
        
        Args:
            redis_url: Redis connection URL (defaults to localhost)
            max_jobs: Maximum jobs to retain
        """
        self.max_jobs = max_jobs
        self._redis: Optional[redis.Redis] = None
        self._fallback_store: dict = {}
        self._fallback_queue: list = []
        self._fallback_lock = threading.Lock()
        
        if REDIS_AVAILABLE and redis_url:
            try:
                self._redis = redis.from_url(
                    redis_url,
                    decode_responses=True,
                    socket_timeout=5,
                    socket_connect_timeout=5,
                )
                # Test connection
                self._redis.ping()
                logger.info(f"Connected to Redis: {redis_url}")
            except Exception as e:
                logger.warning(f"Failed to connect to Redis: {e}, using in-memory fallback")
                self._redis = None
        else:
            logger.info("Using in-memory job queue (Redis not configured)")
    
    @property
    def is_redis_available(self) -> bool:
        """Check if Redis is connected."""
        return self._redis is not None
    
    def _get_redis(self):
        """Get Redis client, reconnecting if needed."""
        if self._redis:
            try:
                self._redis.ping()
                return self._redis
            except Exception:
                logger.warning("Redis connection lost")
                self._redis = None
        return None
    
    def create_job(
        self,
        solver_input: dict,
        job_id: Optional[str] = None,
        school_id: Optional[str] = None,
    ) -> Job:
        """
        Create a new job and add it to the queue.
        
        Args:
            solver_input: The solver input data
            job_id: Optional custom job ID
            school_id: Optional school identifier
        
        Returns:
            The created Job object
        """
        if job_id is None:
            job_id = str(uuid.uuid4())
        
        job = Job(
            job_id=job_id,
            status=JobStatus.QUEUED,
            solver_input=solver_input,
            school_id=school_id,
            created_at=datetime.utcnow().isoformat(),
        )
        
        r = self._get_redis()
        if r:
            pipe = r.pipeline()
            
            # Store job metadata
            job_key = self.JOB_KEY.format(job_id)
            pipe.hset(job_key, mapping={
                "job_id": job_id,
                "status": job.status.value,
                "progress": 0,
                "created_at": job.created_at,
                "school_id": school_id or "",
                "cancelled": "0",
            })
            pipe.expire(job_key, self.JOB_TTL_SECONDS)
            
            # Store solver input separately (may be large)
            input_key = self.JOB_INPUT_KEY.format(job_id)
            pipe.set(input_key, json.dumps(solver_input))
            pipe.expire(input_key, self.JOB_TTL_SECONDS)
            
            # Add to queue and tracking sets
            pipe.lpush(self.PENDING_QUEUE, job_id)
            pipe.sadd(self.ALL_JOBS_SET, job_id)
            
            pipe.execute()
            logger.info(f"Created job {job_id} in Redis queue")
        else:
            # Fallback to in-memory
            with self._fallback_lock:
                self._fallback_store[job_id] = job
                self._fallback_queue.append(job_id)
                logger.info(f"Created job {job_id} in memory queue (total jobs: {len(self._fallback_store)})")
        
        return job
    
    def get_job(self, job_id: str) -> Optional[Job]:
        """
        Retrieve a job by its ID.
        
        Args:
            job_id: The job identifier
        
        Returns:
            The Job object if found, None otherwise
        """
        r = self._get_redis()
        if r:
            job_key = self.JOB_KEY.format(job_id)
            data = r.hgetall(job_key)
            
            if not data:
                return None
            
            # Get solver input
            input_key = self.JOB_INPUT_KEY.format(job_id)
            input_json = r.get(input_key)
            solver_input = json.loads(input_json) if input_json else {}
            
            # Get result if completed
            result_key = self.JOB_RESULT_KEY.format(job_id)
            result_json = r.get(result_key)
            result = json.loads(result_json) if result_json else None
            
            # Get logs
            logs_key = self.JOB_LOGS_KEY.format(job_id)
            logs = r.lrange(logs_key, 0, -1)
            logs = [json.loads(log) for log in logs] if logs else []
            
            return Job(
                job_id=data.get("job_id", job_id),
                status=JobStatus(data.get("status", "queued")),
                progress=int(data.get("progress", 0)),
                solver_input=solver_input,
                result=result,
                error=data.get("error"),
                logs=logs,
                created_at=data.get("created_at"),
                started_at=data.get("started_at"),
                completed_at=data.get("completed_at"),
                school_id=data.get("school_id") or None,
                cancelled=data.get("cancelled") == "1",
            )
        else:
            with self._fallback_lock:
                return self._fallback_store.get(job_id)
    
    def get_next_pending_job(self) -> Optional[str]:
        """
        Get the next pending job ID from the queue (FIFO).
        
        Returns:
            Job ID or None if queue is empty
        """
        r = self._get_redis()
        if r:
            # Block pop with timeout
            result = r.brpop(self.PENDING_QUEUE, timeout=1)
            if result:
                return result[1]
            return None
        else:
            with self._fallback_lock:
                if self._fallback_queue:
                    return self._fallback_queue.pop(0)
                return None
    
    def update_status(
        self,
        job_id: str,
        status: JobStatus,
        progress: int = 0,
        error: Optional[str] = None,
    ) -> bool:
        """
        Update job status and progress.
        
        Args:
            job_id: The job identifier
            status: New job status
            progress: Progress percentage (0-100)
            error: Optional error message
        
        Returns:
            True if job was found and updated
        """
        r = self._get_redis()
        if r:
            job_key = self.JOB_KEY.format(job_id)
            
            # Check job exists
            if not r.exists(job_key):
                return False
            
            updates = {
                "status": status.value,
                "progress": progress,
            }
            
            if status == JobStatus.RUNNING:
                updates["started_at"] = datetime.utcnow().isoformat()
                r.sadd(self.ACTIVE_SET, job_id)
            elif status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
                updates["completed_at"] = datetime.utcnow().isoformat()
                r.srem(self.ACTIVE_SET, job_id)
            
            if error:
                updates["error"] = error
            
            r.hset(job_key, mapping=updates)
            
            # Publish status update
            channel = self.STATUS_CHANNEL.format(job_id)
            r.publish(channel, json.dumps({
                "job_id": job_id,
                "status": status.value,
                "progress": progress,
            }))
            
            return True
        else:
            with self._fallback_lock:
                job = self._fallback_store.get(job_id)
                if job:
                    job.status = status
                    job.progress = progress
                    if error:
                        job.error = error
                    if status == JobStatus.RUNNING:
                        job.started_at = datetime.utcnow().isoformat()
                    elif status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
                        job.completed_at = datetime.utcnow().isoformat()
                    return True
                return False
    
    def store_result(self, job_id: str, result: dict) -> bool:
        """
        Store the solver result for a completed job.
        
        Args:
            job_id: The job identifier
            result: The solver result dictionary
        
        Returns:
            True if result was stored successfully
        """
        r = self._get_redis()
        if r:
            result_key = self.JOB_RESULT_KEY.format(job_id)
            r.set(result_key, json.dumps(result))
            r.expire(result_key, self.RESULT_TTL_SECONDS)
            
            # Update status to completed
            self.update_status(job_id, JobStatus.COMPLETED, progress=100)
            
            logger.info(f"Stored result for job {job_id}")
            return True
        else:
            with self._fallback_lock:
                job = self._fallback_store.get(job_id)
                if job:
                    job.result = result
                    job.status = JobStatus.COMPLETED
                    job.progress = 100
                    job.completed_at = datetime.utcnow().isoformat()
                    return True
                return False
    
    def store_error(self, job_id: str, error: str) -> bool:
        """
        Store an error for a failed job.
        
        Args:
            job_id: The job identifier
            error: The error message
        
        Returns:
            True if error was stored successfully
        """
        r = self._get_redis()
        if r:
            job_key = self.JOB_KEY.format(job_id)
            r.hset(job_key, "error", error)
            self.update_status(job_id, JobStatus.FAILED, error=error)
            return True
        else:
            with self._fallback_lock:
                job = self._fallback_store.get(job_id)
                if job:
                    job.error = error
                    job.status = JobStatus.FAILED
                    job.completed_at = datetime.utcnow().isoformat()
                    return True
                return False
    
    def add_log(self, job_id: str, message: str, level: str = "info") -> None:
        """
        Add a log entry for a job.
        
        Args:
            job_id: The job identifier
            message: Log message
            level: Log level (info, warning, error)
        """
        log_entry = {
            "t": datetime.utcnow().isoformat(),
            "level": level,
            "message": message,
        }
        
        r = self._get_redis()
        if r:
            logs_key = self.JOB_LOGS_KEY.format(job_id)
            r.rpush(logs_key, json.dumps(log_entry))
            r.expire(logs_key, self.JOB_TTL_SECONDS)
            
            # Also publish for real-time streaming
            channel = self.STATUS_CHANNEL.format(job_id)
            r.publish(channel, json.dumps({
                "type": "log",
                "job_id": job_id,
                "log": log_entry,
            }))
        else:
            with self._fallback_lock:
                job = self._fallback_store.get(job_id)
                if job:
                    job.logs.append(log_entry)
    
    def request_cancellation(self, job_id: str) -> bool:
        """
        Request cancellation of a running job.
        
        Args:
            job_id: The job identifier
        
        Returns:
            True if cancellation was requested
        """
        r = self._get_redis()
        if r:
            cancel_key = self.JOB_CANCEL_KEY.format(job_id)
            r.set(cancel_key, "1", ex=3600)  # 1 hour TTL
            
            job_key = self.JOB_KEY.format(job_id)
            r.hset(job_key, "cancelled", "1")
            
            logger.info(f"Cancellation requested for job {job_id}")
            return True
        else:
            with self._fallback_lock:
                job = self._fallback_store.get(job_id)
                if job:
                    job.cancelled = True
                    return True
                return False
    
    def is_cancellation_requested(self, job_id: str) -> bool:
        """
        Check if cancellation has been requested for a job.
        
        Args:
            job_id: The job identifier
        
        Returns:
            True if cancellation was requested
        """
        r = self._get_redis()
        if r:
            cancel_key = self.JOB_CANCEL_KEY.format(job_id)
            return r.exists(cancel_key) == 1
        else:
            with self._fallback_lock:
                job = self._fallback_store.get(job_id)
                return job.cancelled if job else False
    
    def list_jobs(
        self,
        status: Optional[JobStatus] = None,
        limit: int = 50,
    ) -> list[dict]:
        """
        List jobs with optional status filter.
        
        Args:
            status: Optional status filter
            limit: Maximum number of jobs to return
        
        Returns:
            List of job dictionaries
        """
        r = self._get_redis()
        if r:
            # Get all job IDs
            job_ids = r.smembers(self.ALL_JOBS_SET)
            jobs = []
            
            for job_id in list(job_ids)[:limit]:
                job = self.get_job(job_id)
                if job:
                    if status is None or job.status == status:
                        jobs.append(job.to_dict())
            
            # Sort by created_at descending
            jobs.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            return jobs[:limit]
        else:
            with self._fallback_lock:
                jobs = list(self._fallback_store.values())
                if status:
                    jobs = [j for j in jobs if j.status == status]
                jobs.sort(key=lambda x: x.created_at or "", reverse=True)
                return [j.to_dict() for j in jobs[:limit]]
    
    def get_queue_position(self, job_id: str) -> int:
        """
        Get the position of a job in the pending queue.
        
        Args:
            job_id: The job identifier
        
        Returns:
            Position (0-indexed) or -1 if not in queue
        """
        r = self._get_redis()
        if r:
            pending = r.lrange(self.PENDING_QUEUE, 0, -1)
            try:
                return pending.index(job_id)
            except ValueError:
                return -1
        else:
            with self._fallback_lock:
                try:
                    return self._fallback_queue.index(job_id)
                except ValueError:
                    return -1
    
    def get_active_count(self) -> int:
        """Get the number of currently running jobs."""
        r = self._get_redis()
        if r:
            return r.scard(self.ACTIVE_SET)
        else:
            with self._fallback_lock:
                return sum(1 for j in self._fallback_store.values() if j.status == JobStatus.RUNNING)
    
    def get_job_count(self) -> int:
        """Get the total number of jobs in the queue."""
        r = self._get_redis()
        if r:
            return r.scard(self.ALL_JOBS_SET)
        else:
            with self._fallback_lock:
                return len(self._fallback_store)
    
    def cleanup_old_jobs(self, max_age_days: int = 7) -> int:
        """
        Remove jobs older than max_age_days.
        
        Args:
            max_age_days: Maximum age in days
        
        Returns:
            Number of jobs removed
        """
        # Redis handles TTL automatically
        # This is mainly for the in-memory fallback
        if not self._get_redis():
            with self._fallback_lock:
                cutoff = datetime.utcnow().timestamp() - (max_age_days * 86400)
                to_remove = []
                for job_id, job in self._fallback_store.items():
                    if job.created_at:
                        created = datetime.fromisoformat(job.created_at).timestamp()
                        if created < cutoff:
                            to_remove.append(job_id)
                
                for job_id in to_remove:
                    del self._fallback_store[job_id]
                    if job_id in self._fallback_queue:
                        self._fallback_queue.remove(job_id)
                
                return len(to_remove)
        return 0
    
    # =========================================================================
    # Hash-Based Caching (for constraint-aware result reuse)
    # =========================================================================
    
    HASH_RESULT_KEY = "result_by_hash:{}"
    HASH_TTL_SECONDS = 86400 * 7  # 7 days
    
    def store_result_by_hash(self, input_hash: str, job_id: str, result: dict) -> bool:
        """
        Store solver result indexed by input hash for cache lookup.
        
        This allows reusing results when the same input is submitted again.
        The hash includes school data + constraints + solver version, so different 
        constraints or solver versions produce different hashes.
        
        Also persists to disk for retrieval after server restart.
        
        Args:
            input_hash: SHA-256 hash of the solver input (including solver version)
            job_id: The job ID that produced this result
            result: The solver result dictionary
            
        Returns:
            True if stored successfully
        """
        from ..config import RESULTS_DIR
        
        cache_data = {
            "job_id": job_id,
            "input_hash": input_hash,
            "cached_at": datetime.utcnow().isoformat(),
            "result": result,
        }
        
        # Persist to file system for retrieval after restart
        try:
            RESULTS_DIR.mkdir(parents=True, exist_ok=True)
            
            # Save by hash
            hash_file = RESULTS_DIR / f"hash_{input_hash}.json"
            with open(hash_file, "w") as f:
                json.dump(cache_data, f, indent=2)
            
            # Also save by job_id for direct lookup
            job_file = RESULTS_DIR / f"job_{job_id}.json"
            with open(job_file, "w") as f:
                json.dump(cache_data, f, indent=2)
                
            logger.info(f"Persisted result to {hash_file}")
        except Exception as e:
            logger.error(f"Failed to persist result to file: {e}")
        
        r = self._get_redis()
        if r:
            hash_key = self.HASH_RESULT_KEY.format(input_hash)
            r.set(hash_key, json.dumps(cache_data))
            r.expire(hash_key, self.HASH_TTL_SECONDS)
            logger.info(f"Cached result by hash: {input_hash[:16]}... -> job {job_id}")
            return True
        else:
            # For in-memory, store in a separate dict
            with self._fallback_lock:
                if not hasattr(self, '_hash_cache'):
                    self._hash_cache = {}
                self._hash_cache[input_hash] = cache_data
                return True
    
    def get_result_by_hash(self, input_hash: str) -> Optional[dict]:
        """
        Retrieve cached result by input hash.
        
        Checks Redis first, then falls back to file system.
        
        Args:
            input_hash: SHA-256 hash of the solver input
            
        Returns:
            Cached result with metadata, or None if not found
        """
        from ..config import RESULTS_DIR
        
        r = self._get_redis()
        if r:
            hash_key = self.HASH_RESULT_KEY.format(input_hash)
            cached_json = r.get(hash_key)
            if cached_json:
                cached = json.loads(cached_json)
                logger.info(f"Cache HIT (Redis) for hash: {input_hash[:16]}... (job {cached.get('job_id')})")
                return cached
        
        # Try in-memory fallback
        with self._fallback_lock:
            if hasattr(self, '_hash_cache'):
                cached = self._hash_cache.get(input_hash)
                if cached:
                    logger.info(f"Cache HIT (memory) for hash: {input_hash[:16]}...")
                    return cached
        
        # Try file system fallback
        try:
            hash_file = RESULTS_DIR / f"hash_{input_hash}.json"
            if hash_file.exists():
                with open(hash_file, "r") as f:
                    cached = json.load(f)
                logger.info(f"Cache HIT (file) for hash: {input_hash[:16]}... (job {cached.get('job_id')})")
                
                # Re-populate Redis cache if available
                if r:
                    hash_key = self.HASH_RESULT_KEY.format(input_hash)
                    r.set(hash_key, json.dumps(cached))
                    r.expire(hash_key, self.HASH_TTL_SECONDS)
                    
                return cached
        except Exception as e:
            logger.warning(f"Failed to read cache file: {e}")
        
        logger.info(f"Cache MISS for hash: {input_hash[:16]}...")
        return None
    
    def get_result_by_job_id(self, job_id: str) -> Optional[dict]:
        """
        Retrieve cached result by job ID.
        
        Useful for retrieving results after server restart.
        
        Args:
            job_id: The job identifier
            
        Returns:
            Cached result with metadata, or None if not found
        """
        from ..config import RESULTS_DIR
        
        # Try file system
        try:
            job_file = RESULTS_DIR / f"job_{job_id}.json"
            if job_file.exists():
                with open(job_file, "r") as f:
                    cached = json.load(f)
                logger.info(f"Retrieved result for job: {job_id} from file")
                return cached
        except Exception as e:
            logger.warning(f"Failed to read job result file: {e}")
        
        return None
    
    def invalidate_hash_cache(self, input_hash: str) -> bool:
        """
        Invalidate a cached result by hash.
        
        Use this when force_fresh=True is requested or when constraints change.
        Removes from Redis, memory cache, and file system.
        
        Args:
            input_hash: SHA-256 hash to invalidate
            
        Returns:
            True if cache was invalidated (existed and was removed)
        """
        from ..config import RESULTS_DIR
        
        invalidated = False
        
        # Remove from Redis
        r = self._get_redis()
        if r:
            hash_key = self.HASH_RESULT_KEY.format(input_hash)
            deleted = r.delete(hash_key)
            if deleted:
                invalidated = True
                logger.info(f"Invalidated Redis cache for hash: {input_hash[:16]}...")
        
        # Remove from memory
        with self._fallback_lock:
            if hasattr(self, '_hash_cache') and input_hash in self._hash_cache:
                del self._hash_cache[input_hash]
                invalidated = True
                logger.info(f"Invalidated memory cache for hash: {input_hash[:16]}...")
        
        # Remove from file system
        try:
            hash_file = RESULTS_DIR / f"hash_{input_hash}.json"
            if hash_file.exists():
                hash_file.unlink()
                invalidated = True
                logger.info(f"Invalidated file cache for hash: {input_hash[:16]}...")
        except Exception as e:
            logger.warning(f"Failed to remove cache file: {e}")
        
        return invalidated
    
    def invalidate_all_caches_for_constraints(self, constraints_pattern: str = "*") -> int:
        """
        Invalidate all cached results.
        
        Use when solver version changes or for a full cache clear.
        
        Args:
            constraints_pattern: Pattern to match (currently unused, clears all)
            
        Returns:
            Number of cache entries invalidated
        """
        from ..config import RESULTS_DIR
        
        count = 0
        
        # Clear Redis caches
        r = self._get_redis()
        if r:
            cursor = 0
            while True:
                cursor, keys = r.scan(cursor, match="result_by_hash:*", count=100)
                if keys:
                    count += r.delete(*keys)
                if cursor == 0:
                    break
        
        # Clear memory cache
        with self._fallback_lock:
            if hasattr(self, '_hash_cache'):
                count += len(self._hash_cache)
                self._hash_cache.clear()
        
        # Clear file cache
        try:
            if RESULTS_DIR.exists():
                for f in RESULTS_DIR.glob("hash_*.json"):
                    f.unlink()
                    count += 1
        except Exception as e:
            logger.warning(f"Failed to clear file cache: {e}")
        
        logger.info(f"Invalidated {count} cache entries")
        return count


# Global instance (lazy initialization)
_job_queue: Optional[RedisJobQueue] = None
_job_queue_lock = threading.Lock()


def get_queue() -> RedisJobQueue:
    """
    Get the global job queue instance (thread-safe singleton).
    
    This ensures only ONE queue instance exists across all modules,
    preventing jobs from being "lost" due to multiple queue instances.
    """
    global _job_queue
    
    if _job_queue is not None:
        return _job_queue
    
    with _job_queue_lock:
        # Double-check locking pattern
        if _job_queue is None:
            from ..config import REDIS_URL, UPSTASH_REDIS_URL, MAX_CONCURRENT_JOBS
            
            # Prefer UPSTASH_REDIS_URL if set, otherwise use REDIS_URL
            redis_url = UPSTASH_REDIS_URL or REDIS_URL
            
            # Disable Redis if explicitly set to empty
            if not redis_url or redis_url.lower() in ("none", "memory"):
                redis_url = None
            
            _job_queue = RedisJobQueue(redis_url=redis_url, max_jobs=MAX_CONCURRENT_JOBS * 10)
            
            if redis_url:
                logger.info(f"Job queue initialized with Redis: {redis_url[:30]}...")
            else:
                logger.info("Job queue initialized with in-memory storage (no Redis configured)")
        
        return _job_queue


# Backward compatibility alias
def get_job_queue() -> RedisJobQueue:
    """Alias for get_queue() - for backward compatibility."""
    return get_queue()
