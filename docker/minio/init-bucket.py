"""Create the local analytics bucket using MinIO's S3-compatible API."""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import os
import time
import urllib.error
import urllib.parse
import urllib.request


def signature_key(secret: str, date: str, region: str, service: str = "s3") -> bytes:
    key = ("AWS4" + secret).encode()
    date_key = hmac.new(key, date.encode(), hashlib.sha256).digest()
    region_key = hmac.new(date_key, region.encode(), hashlib.sha256).digest()
    service_key = hmac.new(region_key, service.encode(), hashlib.sha256).digest()
    return hmac.new(service_key, b"aws4_request", hashlib.sha256).digest()


def create_bucket(endpoint: str, bucket: str, access_key: str, secret_key: str) -> None:
    parsed = urllib.parse.urlsplit(endpoint)
    host = parsed.netloc
    canonical_uri = f"/{bucket}"
    payload_hash = hashlib.sha256(b"").hexdigest()
    now = dt.datetime.now(dt.timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date = now.strftime("%Y%m%d")
    region = "us-east-1"
    signed_headers = "host;x-amz-content-sha256;x-amz-date"
    canonical_headers = (
        f"host:{host}\n"
        f"x-amz-content-sha256:{payload_hash}\n"
        f"x-amz-date:{amz_date}\n"
    )
    canonical_request = "\n".join(
        ("PUT", canonical_uri, "", canonical_headers, signed_headers, payload_hash)
    )
    scope = f"{date}/{region}/s3/aws4_request"
    string_to_sign = "\n".join(
        (
            "AWS4-HMAC-SHA256",
            amz_date,
            scope,
            hashlib.sha256(canonical_request.encode()).hexdigest(),
        )
    )
    signature = hmac.new(
        signature_key(secret_key, date, region), string_to_sign.encode(), hashlib.sha256
    ).hexdigest()
    authorization = (
        f"AWS4-HMAC-SHA256 Credential={access_key}/{scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )
    request = urllib.request.Request(
        f"{endpoint.rstrip('/')}{canonical_uri}",
        data=b"",
        method="PUT",
        headers={
            "Authorization": authorization,
            "Host": host,
            "x-amz-content-sha256": payload_hash,
            "x-amz-date": amz_date,
        },
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        if response.status not in (200, 204):
            raise RuntimeError(f"MinIO respondió HTTP {response.status} al crear el bucket")


def main() -> None:
    endpoint = os.environ.get("MINIO_ENDPOINT", "http://minio:9000")
    bucket = os.environ.get("ANALYTICS_BUCKET", "firms-analytics")
    access_key = os.environ["MINIO_ROOT_USER"]
    secret_key = os.environ["MINIO_ROOT_PASSWORD"]

    for attempt in range(60):
        try:
            create_bucket(endpoint, bucket, access_key, secret_key)
            print(f"MinIO bucket {bucket} is ready.")
            return
        except urllib.error.HTTPError as error:
            if error.code == 409:
                print(f"MinIO bucket {bucket} already exists.")
                return
            detail = error.read().decode("utf-8", errors="replace")
            message = f"MinIO HTTP {error.code}: {detail}"
        except (OSError, urllib.error.URLError) as error:
            message = str(error)

        if attempt == 59:
            raise RuntimeError(f"No se pudo inicializar el bucket: {message}")
        time.sleep(2)


if __name__ == "__main__":
    main()
