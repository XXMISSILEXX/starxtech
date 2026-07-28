from datetime import datetime, timedelta, timezone
from io import BytesIO

from flask import current_app

from app.storage.exceptions import StorageConfigurationError, StorageNotFoundError


class StorageProvider:
    def create_presigned_upload(self, bucket, object_key, mime_type, file_size, expires_in, metadata=None):
        raise NotImplementedError

    def create_presigned_put(self, bucket, object_key, mime_type, file_size, expires_in, metadata=None):
        raise NotImplementedError

    def create_presigned_download(self, bucket, object_key, expires_in, disposition="inline", filename=None):
        raise NotImplementedError

    def head_object(self, bucket, object_key):
        raise NotImplementedError

    def delete_object(self, bucket, object_key):
        raise NotImplementedError
    def open_object(self, bucket, object_key):
        """Return a readable, bounded-by-caller stream for controlled delivery."""
        raise NotImplementedError
    def download_object(self, bucket, object_key, destination_path): raise NotImplementedError
    def upload_object(self, bucket, object_key, source_path, content_type, metadata=None): raise NotImplementedError


class FakeStorageProvider(StorageProvider):
    """In-memory provider: tests explicitly seed objects before completion."""
    def __init__(self):
        self.objects = {}
        self.deleted = []

    def create_presigned_upload(self, bucket, object_key, mime_type, file_size, expires_in, metadata=None):
        return {"method": "POST", "url": f"https://fake-storage.invalid/{bucket}", "fields": {"key": object_key, "Content-Type": mime_type}, "expires_at": _expires_at(expires_in)}

    def create_presigned_put(self, bucket, object_key, mime_type, file_size, expires_in, metadata=None):
        return {"method": "PUT", "url": f"https://fake-storage.invalid/{bucket}/{object_key}?signature=fake", "headers": {"Content-Type": mime_type, **({"x-amz-meta-sha256": metadata["sha256"]} if metadata and metadata.get("sha256") else {})}, "expires_at": _expires_at(expires_in)}

    def create_presigned_download(self, bucket, object_key, expires_in, disposition="inline", filename=None):
        return {"url": f"https://fake-storage.invalid/{bucket}/{object_key}?signature=fake", "expires_at": _expires_at(expires_in)}

    def head_object(self, bucket, object_key):
        try:
            return self.objects[(bucket, object_key)]
        except KeyError as exc:
            raise StorageNotFoundError("Object không tồn tại.") from exc

    def delete_object(self, bucket, object_key):
        self.objects.pop((bucket, object_key), None)
        self.deleted.append((bucket, object_key))

    def open_object(self, bucket, object_key):
        try:
            return BytesIO(self.objects[(bucket, object_key)].get("bytes", b""))
        except KeyError as exc:
            raise StorageNotFoundError("Object không tồn tại.") from exc

    def register_object(self, bucket, object_key, size, content_type, checksum_sha256=None):
        self.objects[(bucket, object_key)] = {"size": int(size), "content_type": content_type, "checksum_sha256": checksum_sha256, "bytes": b""}
    def put_bytes(self, bucket, object_key, data, content_type):
        self.objects[(bucket, object_key)] = {"size": len(data), "content_type": content_type, "bytes": bytes(data)}
    def download_object(self, bucket, object_key, destination_path):
        from pathlib import Path
        Path(destination_path).write_bytes(self.objects[(bucket, object_key)].get("bytes", b""))
    def upload_object(self, bucket, object_key, source_path, content_type, metadata=None):
        from pathlib import Path
        self.put_bytes(bucket, object_key, Path(source_path).read_bytes(), content_type)


class DisabledStorageProvider(StorageProvider):
    def _disabled(self):
        raise StorageConfigurationError("Storage provider đang bị tắt.")
    create_presigned_upload = create_presigned_put = create_presigned_download = head_object = delete_object = lambda self, *args, **kwargs: self._disabled()


class S3StorageProvider(StorageProvider):
    def __init__(self, config):
        if not config.get("STORAGE_BUCKET") or not config.get("STORAGE_ACCESS_KEY_ID") or not config.get("STORAGE_SECRET_ACCESS_KEY"):
            raise StorageConfigurationError("S3 storage thiếu bucket hoặc credentials.")
        try:
            import boto3
        except ImportError as exc:
            raise StorageConfigurationError("S3 storage cần dependency boto3 đã pin.") from exc
        self.client = boto3.client("s3", endpoint_url=config.get("STORAGE_ENDPOINT_URL"), region_name=config.get("STORAGE_REGION"), aws_access_key_id=config.get("STORAGE_ACCESS_KEY_ID"), aws_secret_access_key=config.get("STORAGE_SECRET_ACCESS_KEY"))

    def create_presigned_upload(self, bucket, object_key, mime_type, file_size, expires_in, metadata=None):
        result = self.client.generate_presigned_post(bucket, object_key, Fields={"Content-Type": mime_type}, Conditions=[["content-length-range", file_size, file_size], {"Content-Type": mime_type}], ExpiresIn=expires_in)
        return {"method": "POST", "url": result["url"], "fields": result["fields"], "expires_at": _expires_at(expires_in)}

    def create_presigned_put(self, bucket, object_key, mime_type, file_size, expires_in, metadata=None):
        params = {"Bucket": bucket, "Key": object_key, "ContentType": mime_type}
        if metadata and metadata.get("sha256"):
            params["Metadata"] = {"sha256": metadata["sha256"]}
        return {"method": "PUT", "url": self.client.generate_presigned_url("put_object", Params=params, ExpiresIn=expires_in, HttpMethod="PUT"), "headers": {"Content-Type": mime_type, **({"x-amz-meta-sha256": metadata["sha256"]} if metadata and metadata.get("sha256") else {})}, "expires_at": _expires_at(expires_in)}

    def create_presigned_download(self, bucket, object_key, expires_in, disposition="inline", filename=None):
        params = {"Bucket": bucket, "Key": object_key, "ResponseContentDisposition": f'{disposition}; filename="{filename or "download"}"'}
        return {"url": self.client.generate_presigned_url("get_object", Params=params, ExpiresIn=expires_in), "expires_at": _expires_at(expires_in)}

    def head_object(self, bucket, object_key):
        result = self.client.head_object(Bucket=bucket, Key=object_key)
        return {"size": result["ContentLength"], "content_type": result.get("ContentType"), "checksum_sha256": result.get("Metadata", {}).get("sha256")}

    def delete_object(self, bucket, object_key):
        self.client.delete_object(Bucket=bucket, Key=object_key)

    def open_object(self, bucket, object_key):
        return self.client.get_object(Bucket=bucket, Key=object_key)["Body"]

    def download_object(self, bucket, object_key, destination_path):
        self.client.download_file(bucket, object_key, str(destination_path))

    def upload_object(self, bucket, object_key, source_path, content_type, metadata=None):
        extra = {"ContentType": content_type}
        if metadata:
            extra["Metadata"] = metadata
        self.client.upload_file(str(source_path), bucket, object_key, ExtraArgs=extra)


def get_storage_provider():
    provider = current_app.extensions.get("storage_provider")
    if provider is not None:
        return provider
    name = str(current_app.config.get("STORAGE_PROVIDER", "disabled")).lower()
    provider = FakeStorageProvider() if name == "fake" else DisabledStorageProvider() if name == "disabled" else S3StorageProvider(current_app.config) if name == "s3" else DisabledStorageProvider()
    current_app.extensions["storage_provider"] = provider
    return provider


def _expires_at(seconds):
    return (datetime.now(timezone.utc) + timedelta(seconds=int(seconds))).isoformat()
