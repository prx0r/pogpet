"""Presigned R2 delivery — suppliers fetch expiring URLs, nothing stays public.

Card PDFs carry real faces and names, so fulfilment assets go to R2 with a
~24h presigned URL instead of a public mirror. boto3 only; no new deps.
"""
from __future__ import annotations

import os
from pathlib import Path

from . import config


class R2Error(Exception):
    pass


def _client():
    import boto3
    endpoint = os.environ.get("R2_S3_ENDPOINT", "").strip()
    key = os.environ.get("R2_ACCESS_KEY_ID", "").strip()
    secret = os.environ.get("R2_SECRET_ACCESS_KEY", "").strip()
    if not (endpoint and key and secret):
        raise R2Error("R2 S3 credentials missing (R2_S3_ENDPOINT/KEY/SECRET)")
    return boto3.client("s3", endpoint_url=endpoint,
                        aws_access_key_id=key, aws_secret_access_key=secret,
                        region_name="auto")


def put_temp(local: Path | str, key: str | None = None) -> str:
    """Upload a fulfilment asset under a random key. Returns the R2 key."""
    import secrets as _secrets
    local = Path(local)
    key = key or f"tmp/{_secrets.token_hex(16)}/{local.name}"
    try:
        _client().upload_file(str(local), config.R2_BUCKET, key,
                              ExtraArgs={"ContentType": "application/pdf"})
    except Exception as e:
        raise R2Error(f"R2 upload failed: {e}") from None
    return key


def presigned_url(key: str, expires_s: int = 86400) -> str:
    """Time-boxed fetch URL for a supplier. Nothing public, nothing indexed."""
    try:
        return _client().generate_presigned_url(
            "get_object",
            Params={"Bucket": config.R2_BUCKET, "Key": key},
            ExpiresIn=int(expires_s))
    except Exception as e:
        raise R2Error(f"presign failed: {e}") from None


def delete(key: str) -> None:
    try:
        _client().delete_object(Bucket=config.R2_BUCKET, Key=key)
    except Exception:
        pass
