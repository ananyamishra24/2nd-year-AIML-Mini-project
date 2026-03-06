"""
Cloud Storage Abstraction Layer
────────────────────────────────
Supports AWS S3, Azure Blob, and local filesystem.
Automatically selects backend based on environment configuration.
"""

import os
import time
import logging
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger('brave_story.storage')

# ── Determine storage backend ────────────────────────────────────────
AWS_BUCKET = os.environ.get('AWS_S3_BUCKET', '')
AWS_REGION = os.environ.get('AWS_S3_REGION', 'us-east-1')
AZURE_CONN_STR = os.environ.get('AZURE_STORAGE_CONNECTION_STRING', '')
AZURE_CONTAINER = os.environ.get('AZURE_STORAGE_CONTAINER', 'story-images')


def get_storage_backend():
    # Respect explicit STORAGE_BACKEND env var first
    explicit = os.environ.get('STORAGE_BACKEND', '').strip().lower()
    if explicit in ('local', 's3', 'azure'):
        return explicit
    # Auto-detect from credentials
    if AWS_BUCKET:
        return 's3'
    elif AZURE_CONN_STR:
        return 'azure'
    return 'local'


STORAGE_BACKEND = get_storage_backend()
logger.info(f'Storage backend: {STORAGE_BACKEND}')


# ── Local storage ────────────────────────────────────────────────────

class LocalStorage:
    """Store images on local filesystem."""

    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_image(self, image_bytes: bytes, filename: str) -> str:
        """Save image and return URL path."""
        filepath = self.base_dir / filename
        filepath.write_bytes(image_bytes)
        logger.info(f'Saved image locally: {filename}')
        return f'/generated_images/{filename}'

    def delete_image(self, filename: str) -> bool:
        filepath = self.base_dir / filename
        if filepath.exists():
            filepath.unlink()
            return True
        return False

    def get_url(self, filename: str) -> str:
        return f'/generated_images/{filename}'


# ── AWS S3 Storage ───────────────────────────────────────────────────

# How long presigned URLs remain valid (seconds). Default: 7 days.
PRESIGNED_URL_EXPIRY = int(os.environ.get('S3_PRESIGNED_EXPIRY', 604800))


class S3Storage:
    """Store images in AWS S3 using presigned URLs for private buckets."""

    def __init__(self):
        try:
            import boto3
            self.s3 = boto3.client('s3', region_name=AWS_REGION)
            self.bucket = AWS_BUCKET
            logger.info(f'S3 storage initialized: {self.bucket} (presigned URLs, expiry={PRESIGNED_URL_EXPIRY}s)')
        except ImportError:
            logger.error('boto3 not installed — run: pip install boto3')
            raise

    def _presigned_url(self, key: str) -> str:
        """Generate a presigned GET URL for the given S3 key."""
        return self.s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': self.bucket, 'Key': key},
            ExpiresIn=PRESIGNED_URL_EXPIRY,
        )

    def save_image(self, image_bytes: bytes, filename: str) -> str:
        """Upload image to S3 and return a presigned URL."""
        key = f'generated_images/{filename}'
        self.s3.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=image_bytes,
            ContentType='image/png',
        )
        url = self._presigned_url(key)
        logger.info(f'Uploaded to S3: {key} (presigned URL generated)')
        return url

    def delete_image(self, filename: str) -> bool:
        try:
            self.s3.delete_object(Bucket=self.bucket, Key=f'generated_images/{filename}')
            return True
        except Exception as e:
            logger.error(f'S3 delete failed: {e}')
            return False

    def get_url(self, filename: str) -> str:
        return self._presigned_url(f'generated_images/{filename}')


# ── Azure Blob Storage ───────────────────────────────────────────────

class AzureBlobStorage:
    """Store images in Azure Blob Storage."""

    def __init__(self):
        try:
            from azure.storage.blob import BlobServiceClient
            self.blob_service = BlobServiceClient.from_connection_string(AZURE_CONN_STR)
            self.container_client = self.blob_service.get_container_client(AZURE_CONTAINER)
            # Create container if doesn't exist
            try:
                self.container_client.create_container()
            except Exception:
                pass
            logger.info(f'Azure Blob storage initialized: {AZURE_CONTAINER}')
        except ImportError:
            logger.error('azure-storage-blob not installed — run: pip install azure-storage-blob')
            raise

    def save_image(self, image_bytes: bytes, filename: str) -> str:
        """Upload image to Azure Blob and return URL."""
        blob_client = self.container_client.get_blob_client(filename)
        blob_client.upload_blob(image_bytes, content_type='image/png', overwrite=True)
        url = blob_client.url
        logger.info(f'Uploaded to Azure Blob: {url}')
        return url

    def delete_image(self, filename: str) -> bool:
        try:
            blob_client = self.container_client.get_blob_client(filename)
            blob_client.delete_blob()
            return True
        except Exception as e:
            logger.error(f'Azure delete failed: {e}')
            return False

    def get_url(self, filename: str) -> str:
        blob_client = self.container_client.get_blob_client(filename)
        return blob_client.url


# ── Factory ──────────────────────────────────────────────────────────

def create_storage(local_images_dir: Optional[str] = None):
    """Create the appropriate storage backend.

    Falls back to local storage if the required cloud SDK is not installed.
    """
    base = local_images_dir or str(Path(__file__).parent.parent / 'client' / 'generated_images')

    if STORAGE_BACKEND == 's3':
        try:
            return S3Storage()
        except (ImportError, Exception) as e:
            logger.warning(f'S3 storage unavailable ({e}), falling back to local storage')
            return LocalStorage(base)
    elif STORAGE_BACKEND == 'azure':
        try:
            return AzureBlobStorage()
        except (ImportError, Exception) as e:
            logger.warning(f'Azure storage unavailable ({e}), falling back to local storage')
            return LocalStorage(base)
    else:
        return LocalStorage(base)


# ── Image download helper ────────────────────────────────────────────

def download_and_store(url: str, storage, prefix: str = 'story') -> Optional[str]:
    """Download an image from URL and store it using the configured backend."""
    try:
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        filename = f'{prefix}_{int(time.time())}_{os.urandom(4).hex()}.png'
        return storage.save_image(resp.content, filename)
    except Exception as e:
        logger.error(f'Failed to download and store image: {e}')
        return None
