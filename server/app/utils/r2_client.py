"""
Cloudflare R2 client for storing timetable results and large payloads.
Uses S3-compatible API via boto3.
"""

import logging
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from typing import Optional
from pathlib import Path
from app.config import R2_BUCKET, R2_ENDPOINT_URL, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY

logger = logging.getLogger(__name__)


class R2Client:
    """Cloudflare R2 storage client using S3 API."""
    
    def __init__(self):
        if not all([R2_BUCKET, R2_ENDPOINT_URL, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY]):
            raise ValueError("R2 configuration incomplete: R2_BUCKET, R2_ENDPOINT_URL, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY required")
        
        self.bucket = R2_BUCKET
        self.s3_client = boto3.client(
            's3',
            endpoint_url=R2_ENDPOINT_URL,
            aws_access_key_id=R2_ACCESS_KEY_ID,
            aws_secret_access_key=R2_SECRET_ACCESS_KEY,
            config=Config(signature_version='s3v4'),
            region_name='auto'  # R2 uses auto region
        )
        logger.info(f"R2 client initialized for bucket {self.bucket}")
    
    def upload_file(self, file_path: str, object_key: str) -> str:
        """
        Upload a file to R2.
        
        Args:
            file_path: Local file path
            object_key: R2 object key (path in bucket)
        
        Returns:
            R2 URL (r2://bucket/key format)
        """
        try:
            with open(file_path, 'rb') as f:
                self.s3_client.upload_fileobj(
                    f,
                    self.bucket,
                    object_key,
                    ExtraArgs={'ContentType': self._guess_content_type(file_path)}
                )
            
            r2_url = f"r2://{self.bucket}/{object_key}"
            logger.info(f"Uploaded {file_path} to {r2_url}")
            return r2_url
        except ClientError as e:
            logger.error(f"Failed to upload {file_path} to R2: {e}")
            raise
    
    def upload_bytes(self, data: bytes, object_key: str, content_type: str = 'application/json') -> str:
        """
        Upload bytes to R2.
        
        Args:
            data: Bytes to upload
            object_key: R2 object key
            content_type: MIME type
        
        Returns:
            R2 URL
        """
        try:
            self.s3_client.put_object(
                Bucket=self.bucket,
                Key=object_key,
                Body=data,
                ContentType=content_type
            )
            
            r2_url = f"r2://{self.bucket}/{object_key}"
            logger.info(f"Uploaded {len(data)} bytes to {r2_url}")
            return r2_url
        except ClientError as e:
            logger.error(f"Failed to upload bytes to R2: {e}")
            raise
    
    def download_file(self, object_key: str, local_path: str) -> None:
        """
        Download a file from R2.
        
        Args:
            object_key: R2 object key
            local_path: Local destination path
        """
        try:
            # Ensure directory exists
            Path(local_path).parent.mkdir(parents=True, exist_ok=True)
            
            self.s3_client.download_file(self.bucket, object_key, local_path)
            logger.info(f"Downloaded r2://{self.bucket}/{object_key} to {local_path}")
        except ClientError as e:
            logger.error(f"Failed to download from R2: {e}")
            raise
    
    def download_bytes(self, object_key: str) -> bytes:
        """
        Download object as bytes.
        
        Args:
            object_key: R2 object key
        
        Returns:
            Object data as bytes
        """
        try:
            response = self.s3_client.get_object(Bucket=self.bucket, Key=object_key)
            data = response['Body'].read()
            logger.info(f"Downloaded {len(data)} bytes from r2://{self.bucket}/{object_key}")
            return data
        except ClientError as e:
            logger.error(f"Failed to download bytes from R2: {e}")
            raise
    
    def generate_presigned_url(
        self,
        object_key: str,
        expiration: int = 3600,
        http_method: str = 'get_object'
    ) -> str:
        """
        Generate a presigned URL for temporary access.
        
        Args:
            object_key: R2 object key
            expiration: URL validity in seconds (default 1 hour)
            http_method: 'get_object' or 'put_object'
        
        Returns:
            Presigned HTTPS URL
        """
        try:
            url = self.s3_client.generate_presigned_url(
                http_method,
                Params={'Bucket': self.bucket, 'Key': object_key},
                ExpiresIn=expiration
            )
            logger.info(f"Generated presigned URL for {object_key} (expires in {expiration}s)")
            return url
        except ClientError as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            raise
    
    def delete_object(self, object_key: str) -> None:
        """Delete an object from R2."""
        try:
            self.s3_client.delete_object(Bucket=self.bucket, Key=object_key)
            logger.info(f"Deleted r2://{self.bucket}/{object_key}")
        except ClientError as e:
            logger.error(f"Failed to delete from R2: {e}")
            raise
    
    def object_exists(self, object_key: str) -> bool:
        """Check if object exists in R2."""
        try:
            self.s3_client.head_object(Bucket=self.bucket, Key=object_key)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            logger.error(f"Error checking object existence: {e}")
            raise
    
    @staticmethod
    def _guess_content_type(file_path: str) -> str:
        """Guess content type from file extension."""
        suffix = Path(file_path).suffix.lower()
        content_types = {
            '.json': 'application/json',
            '.xml': 'application/xml',
            '.csv': 'text/csv',
            '.txt': 'text/plain',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.xls': 'application/vnd.ms-excel',
            '.pdf': 'application/pdf'
        }
        return content_types.get(suffix, 'application/octet-stream')
    
    @staticmethod
    def parse_r2_url(r2_url: str) -> tuple[str, str]:
        """
        Parse R2 URL into bucket and key.
        
        Args:
            r2_url: URL in format r2://bucket/key
        
        Returns:
            Tuple of (bucket, key)
        """
        if not r2_url.startswith('r2://'):
            raise ValueError(f"Invalid R2 URL: {r2_url}")
        
        path = r2_url[5:]  # Remove 'r2://'
        parts = path.split('/', 1)
        
        if len(parts) != 2:
            raise ValueError(f"Invalid R2 URL format: {r2_url}")
        
        return parts[0], parts[1]


# Global singleton instance
_r2_client: Optional[R2Client] = None


def get_r2_client() -> R2Client:
    """Get or create R2 client singleton."""
    global _r2_client
    if _r2_client is None:
        _r2_client = R2Client()
    return _r2_client
