"""S3-compatible object storage client (MinIO locally, AWS S3 in production)."""
import json
import logging
from functools import lru_cache

import boto3
from botocore.exceptions import ClientError

from clients.config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_s3_client():
    kwargs = dict(
        aws_access_key_id=settings.s3_access_key or None,
        aws_secret_access_key=settings.s3_secret_key or None,
    )
    if settings.s3_endpoint_url:
        kwargs["endpoint_url"] = settings.s3_endpoint_url
    return boto3.client("s3", **kwargs)


def ensure_bucket() -> None:
    s3 = get_s3_client()
    bucket = settings.s3_bucket
    try:
        s3.head_bucket(Bucket=bucket)
    except ClientError:
        s3.create_bucket(Bucket=bucket)
        logger.info("storage: created bucket %s", bucket)


def upload_filing(ticker: str, doc_name: str, content: str) -> str:
    """Upload markdown content, return the S3 key."""
    key = f"filings/{ticker}/{doc_name}"
    get_s3_client().put_object(
        Bucket=settings.s3_bucket,
        Key=key,
        Body=content.encode("utf-8"),
        ContentType="text/markdown",
    )
    logger.info("storage: uploaded %s (%d chars)", key, len(content))
    return key


def download_filing(s3_key: str) -> str:
    """Download markdown content from S3."""
    response = get_s3_client().get_object(Bucket=settings.s3_bucket, Key=s3_key)
    return response["Body"].read().decode("utf-8")


def upload_structure(doc_id: str, structure: list) -> str:
    """Upload PageIndex structure JSON, return the S3 key."""
    key = f"indexes/{doc_id}.json"
    get_s3_client().put_object(
        Bucket=settings.s3_bucket,
        Key=key,
        Body=json.dumps(structure).encode("utf-8"),
        ContentType="application/json",
    )
    logger.info("storage: uploaded structure %s (%d nodes)", key, len(structure))
    return key


def download_structure(s3_key: str) -> list:
    """Download PageIndex structure JSON from S3."""
    response = get_s3_client().get_object(Bucket=settings.s3_bucket, Key=s3_key)
    return json.loads(response["Body"].read().decode("utf-8"))
