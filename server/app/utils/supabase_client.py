"""
Supabase client for database operations.
Manages job lifecycle, tenant isolation, and audit trail.
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from supabase import create_client, Client
from app.config import SUPABASE_URL, SUPABASE_KEY

logger = logging.getLogger(__name__)


class SupabaseClient:
    """Thread-safe Supabase client wrapper."""
    
    def __init__(self):
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set")
        
        self.client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("Supabase client initialized")
    
    def create_job(
        self,
        job_id: str,
        tenant_id: str,
        payload_hash: str,
        payload_pointer: str,
        schema_version: str = "1.0",
        solver_version: str = "1.0",
        time_limit_sec: int = 25,
        requested_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new job record."""
        job_data = {
            "job_id": job_id,
            "tenant_id": tenant_id,
            "payload_hash": payload_hash,
            "payload_pointer": payload_pointer,
            "status": "QUEUED",
            "schema_version": schema_version,
            "solver_version": solver_version,
            "time_limit_sec": time_limit_sec,
            "requested_by": requested_by,
            "progress": 0.0
        }
        
        try:
            response = self.client.table("jobs").insert(job_data).execute()
            logger.info(f"Created job {job_id} for tenant {tenant_id}")
            return response.data[0] if response.data else job_data
        except Exception as e:
            logger.error(f"Failed to create job {job_id}: {e}")
            raise
    
    def find_job_by_payload_hash(
        self,
        tenant_id: str,
        payload_hash: str
    ) -> Optional[Dict[str, Any]]:
        """Find existing job with same payload hash (idempotency check)."""
        try:
            response = (
                self.client.table("jobs")
                .select("*")
                .eq("tenant_id", tenant_id)
                .eq("payload_hash", payload_hash)
                .in_("status", ["QUEUED", "RUNNING", "COMPLETED", "COMPLETED_PARTIAL"])
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            
            if response.data:
                logger.info(f"Found existing job for payload_hash {payload_hash[:8]}...")
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error finding job by payload hash: {e}")
            return None
    
    def get_job(self, job_id: str, tenant_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get job by ID with optional tenant check."""
        try:
            query = self.client.table("jobs").select("*").eq("job_id", job_id)
            
            if tenant_id:
                query = query.eq("tenant_id", tenant_id)
            
            response = query.execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error fetching job {job_id}: {e}")
            return None
    
    def update_job_status(
        self,
        job_id: str,
        status: str,
        worker_id: Optional[str] = None,
        progress: Optional[float] = None,
        error_message: Optional[str] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None
    ) -> bool:
        """Update job status and metadata."""
        update_data = {"status": status}
        
        if worker_id is not None:
            update_data["worker_id"] = worker_id
        if progress is not None:
            update_data["progress"] = progress
        if error_message is not None:
            update_data["error_message"] = error_message
        if started_at is not None:
            update_data["started_at"] = started_at.isoformat()
        if completed_at is not None:
            update_data["completed_at"] = completed_at.isoformat()
        
        try:
            self.client.table("jobs").update(update_data).eq("job_id", job_id).execute()
            logger.info(f"Updated job {job_id} status to {status}")
            return True
        except Exception as e:
            logger.error(f"Failed to update job {job_id}: {e}")
            return False
    
    def store_result(
        self,
        job_id: str,
        r2_url: str,
        solve_metrics: Dict[str, Any],
        diagnostics: Optional[Dict[str, Any]] = None,
        status: str = "COMPLETED"
    ) -> bool:
        """Store job result and metrics."""
        update_data = {
            "status": status,
            "r2_url": r2_url,
            "solve_metrics": solve_metrics,
            "progress": 1.0,
            "completed_at": datetime.utcnow().isoformat()
        }
        
        if diagnostics:
            update_data["diagnostics"] = diagnostics
        
        try:
            self.client.table("jobs").update(update_data).eq("job_id", job_id).execute()
            logger.info(f"Stored result for job {job_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to store result for job {job_id}: {e}")
            return False
    
    def get_active_jobs_count(self, tenant_id: Optional[str] = None) -> int:
        """Get count of active jobs (QUEUED or RUNNING)."""
        try:
            query = (
                self.client.table("jobs")
                .select("job_id", count="exact")
                .in_("status", ["QUEUED", "RUNNING"])
            )
            
            if tenant_id:
                query = query.eq("tenant_id", tenant_id)
            
            response = query.execute()
            return response.count or 0
        except Exception as e:
            logger.error(f"Error counting active jobs: {e}")
            return 0
    
    def get_queue_position(self, job_id: str) -> int:
        """Get position of job in queue (1-indexed)."""
        try:
            job = self.get_job(job_id)
            if not job or job["status"] != "QUEUED":
                return 0
            
            # Count QUEUED jobs created before this one
            response = (
                self.client.table("jobs")
                .select("job_id", count="exact")
                .eq("status", "QUEUED")
                .lt("created_at", job["created_at"])
                .execute()
            )
            
            return (response.count or 0) + 1
        except Exception as e:
            logger.error(f"Error calculating queue position for {job_id}: {e}")
            return 0
    
    def get_job_history(self, job_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get job status history."""
        try:
            response = (
                self.client.table("job_history")
                .select("*")
                .eq("job_id", job_id)
                .order("changed_at", desc=True)
                .limit(limit)
                .execute()
            )
            return response.data or []
        except Exception as e:
            logger.error(f"Error fetching job history for {job_id}: {e}")
            return []


# Global singleton instance
_supabase_client: Optional[SupabaseClient] = None


def get_supabase_client() -> SupabaseClient:
    """Get or create Supabase client singleton."""
    global _supabase_client
    if _supabase_client is None:
        _supabase_client = SupabaseClient()
    return _supabase_client
