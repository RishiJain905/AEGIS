"""S3-compatible object storage adapter for snapshot archives.

Vendor SDK (boto3) stays behind this adapter. Domain/replay code depends on
ObjectStoragePort only.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from aegis_contracts import AegisSettings


class ObjectStorageError(RuntimeError):
    """Raised when object storage operations fail."""


class ObjectStoragePort(Protocol):
    def put_bytes(
        self,
        *,
        object_key: str,
        data: bytes,
        content_type: str,
    ) -> str:
        """Store bytes and return sha256:<hex> checksum of the stored payload."""

    def get_bytes(self, *, object_key: str) -> bytes:
        """Load object bytes by key."""

    def delete(self, *, object_key: str) -> None:
        """Delete object if present."""

    def exists(self, *, object_key: str) -> bool:
        """Return True when the object key exists."""


def sha256_hex(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


@dataclass(frozen=True, slots=True)
class InMemoryObjectStorage:
    """Test/dev storage that never leaves process memory."""

    _objects: dict[str, tuple[bytes, str]]

    @classmethod
    def create(cls) -> InMemoryObjectStorage:
        return cls(_objects={})

    def put_bytes(self, *, object_key: str, data: bytes, content_type: str) -> str:
        checksum = sha256_hex(data)
        self._objects[object_key] = (data, content_type)
        return checksum

    def get_bytes(self, *, object_key: str) -> bytes:
        try:
            data, _content_type = self._objects[object_key]
        except KeyError as exc:
            raise ObjectStorageError(f"Object not found: {object_key}") from exc
        return data

    def delete(self, *, object_key: str) -> None:
        self._objects.pop(object_key, None)

    def exists(self, *, object_key: str) -> bool:
        return object_key in self._objects


class S3ObjectStorageAdapter:
    """boto3-backed S3/MinIO adapter."""

    def __init__(self, settings: AegisSettings) -> None:
        try:
            import boto3
            from botocore.client import Config
        except ImportError as exc:  # pragma: no cover - dependency gate
            raise ObjectStorageError(
                "boto3 is required for S3ObjectStorageAdapter"
            ) from exc

        self._bucket = settings.S3_BUCKET
        self._client = boto3.client(
            "s3",
            endpoint_url=str(settings.S3_ENDPOINT),
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            config=Config(signature_version="s3v4"),
            region_name="us-east-1",
        )
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        try:
            self._client.head_bucket(Bucket=self._bucket)
        except Exception:
            try:
                self._client.create_bucket(Bucket=self._bucket)
            except Exception as exc:
                # Bucket may already exist from a race; verify again.
                try:
                    self._client.head_bucket(Bucket=self._bucket)
                except Exception as head_exc:
                    raise ObjectStorageError(
                        f"Unable to ensure bucket {self._bucket}"
                    ) from head_exc
                _ = exc

    def put_bytes(self, *, object_key: str, data: bytes, content_type: str) -> str:
        checksum = sha256_hex(data)
        try:
            self._client.put_object(
                Bucket=self._bucket,
                Key=object_key,
                Body=data,
                ContentType=content_type,
                Metadata={"checksum": checksum},
            )
        except Exception as exc:
            raise ObjectStorageError(f"Failed to put object {object_key}") from exc
        return checksum

    def get_bytes(self, *, object_key: str) -> bytes:
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=object_key)
            body = response["Body"].read()
        except Exception as exc:
            raise ObjectStorageError(f"Failed to get object {object_key}") from exc
        if not isinstance(body, (bytes, bytearray)):
            raise ObjectStorageError(f"Unexpected body type for {object_key}")
        return bytes(body)

    def delete(self, *, object_key: str) -> None:
        try:
            self._client.delete_object(Bucket=self._bucket, Key=object_key)
        except Exception as exc:
            raise ObjectStorageError(f"Failed to delete object {object_key}") from exc

    def exists(self, *, object_key: str) -> bool:
        try:
            self._client.head_object(Bucket=self._bucket, Key=object_key)
            return True
        except Exception:
            return False


@dataclass(slots=True)
class FilesystemObjectStorage:
    """Durable local filesystem storage for demos/tests without MinIO."""

    root: Path

    def __post_init__(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, object_key: str) -> Path:
        safe = object_key.lstrip("/")
        path = (self.root / safe).resolve()
        if not str(path).startswith(str(self.root.resolve())):
            raise ObjectStorageError(f"Invalid object key path: {object_key}")
        return path

    def put_bytes(self, *, object_key: str, data: bytes, content_type: str) -> str:
        path = self._path(object_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        meta = path.with_suffix(path.suffix + ".meta")
        meta.write_text(content_type, encoding="utf-8")
        return sha256_hex(data)

    def get_bytes(self, *, object_key: str) -> bytes:
        path = self._path(object_key)
        if not path.exists():
            raise ObjectStorageError(f"Object not found: {object_key}")
        return path.read_bytes()

    def delete(self, *, object_key: str) -> None:
        path = self._path(object_key)
        meta = path.with_suffix(path.suffix + ".meta")
        if path.exists():
            path.unlink()
        if meta.exists():
            meta.unlink()

    def exists(self, *, object_key: str) -> bool:
        return self._path(object_key).exists()


def build_object_storage(
    settings: AegisSettings,
    *,
    in_memory: bool = False,
    filesystem_root: str | None = None,
) -> ObjectStoragePort:
    if in_memory and not filesystem_root:
        return InMemoryObjectStorage.create()
    if filesystem_root:
        return FilesystemObjectStorage(root=Path(filesystem_root))
    return S3ObjectStorageAdapter(settings)
