"""Private, read-through cache for small authorised media derivatives.

The cache has no public URL and never decides authorisation.  Callers resolve a
server-side object only after their normal ACL checks, then ask this module to
materialise that object locally.
"""
from __future__ import annotations

import errno
import fcntl
import hashlib
import logging
import os
import stat
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Callable

from flask import current_app, make_response, send_file

from app.storage.exceptions import StorageNotFoundError


LOG = logging.getLogger(__name__)
_CHUNK_SIZE = 64 * 1024
_ALLOWED_DELIVERY_MODES = {"send_file", "x_accel"}
_SAFE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif", "svg"}


class MediaCacheError(RuntimeError):
    """A cache failure that must not be represented as a successful response."""


class MediaCacheSourceMissing(MediaCacheError):
    """The authorised S3 object disappeared before it could be cached."""


@dataclass(frozen=True)
class CacheSource:
    category: str
    object_id: int
    derivative_type: str
    immutable_key: str
    version_id: int
    extension: str
    mime_type: str
    file_size: int
    bucket: str


@dataclass(frozen=True)
class CachedMedia:
    path: Path
    relative_path: str
    size: int


def validate_cache_config(config) -> list[str]:
    errors = []
    root = str(config.get("MEDIA_CACHE_ROOT") or "")
    if not root or not os.path.isabs(root):
        errors.append("MEDIA_CACHE_ROOT must be an absolute path")
    mode = str(config.get("MEDIA_CACHE_DELIVERY_MODE") or "")
    if mode not in _ALLOWED_DELIVERY_MODES:
        errors.append("MEDIA_CACHE_DELIVERY_MODE must be send_file or x_accel")
    prefix = str(config.get("MEDIA_CACHE_X_ACCEL_PREFIX") or "")
    if not prefix.startswith("/") or not prefix.endswith("/") or "//" in prefix:
        errors.append("MEDIA_CACHE_X_ACCEL_PREFIX must start and end with one slash")
    try:
        if int(config.get("MEDIA_CACHE_MAX_BYTES", 0)) < 1:
            errors.append("MEDIA_CACHE_MAX_BYTES must be greater than zero")
    except (TypeError, ValueError):
        errors.append("MEDIA_CACHE_MAX_BYTES must be greater than zero")
    try:
        if int(config.get("MEDIA_CACHE_MAX_AGE_DAYS", 0)) < 1:
            errors.append("MEDIA_CACHE_MAX_AGE_DAYS must be greater than zero")
    except (TypeError, ValueError):
        errors.append("MEDIA_CACHE_MAX_AGE_DAYS must be greater than zero")
    return errors


class MediaCache:
    def __init__(self, config=None):
        config = config or current_app.config
        errors = validate_cache_config(config)
        if errors:
            raise MediaCacheError("Invalid media cache configuration")
        self.root = Path(str(config["MEDIA_CACHE_ROOT"]))
        self.max_bytes = int(config["MEDIA_CACHE_MAX_BYTES"])
        self._ensure_root()

    def cache_path(self, source: CacheSource) -> tuple[Path, str]:
        extension = source.extension.lower().lstrip(".")
        if extension not in _SAFE_EXTENSIONS:
            extension = "bin"
        identity = "\x1f".join((
            source.category,
            str(int(source.object_id)),
            source.derivative_type,
            source.immutable_key,
            str(int(source.version_id)),
        ))
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
        relative = Path(source.category) / digest[:2] / digest[2:4] / f"{digest}.{extension}"
        self._ensure_safe_directory(relative.parent)
        path = self._safe_path(relative)
        return path, relative.as_posix()

    def get_or_fill(self, source: CacheSource, open_source: Callable[[], BinaryIO]) -> CachedMedia:
        path, relative = self.cache_path(source)
        cached = self._valid_file(path)
        if cached is not None:
            LOG.info("media_cache_hit object_id=%s type=%s", source.object_id, source.derivative_type)
            return CachedMedia(path, relative, cached)

        LOG.info("media_cache_miss object_id=%s type=%s", source.object_id, source.derivative_type)
        started = time.monotonic()
        with self._key_lock(path):
            cached = self._valid_file(path)
            if cached is not None:
                LOG.info("media_cache_hit object_id=%s type=%s", source.object_id, source.derivative_type)
                return CachedMedia(path, relative, cached)
            try:
                size = self._fill(path, source, open_source)
            except StorageNotFoundError as exc:
                LOG.info("media_cache_fill_failed object_id=%s type=%s error_code=NoSuchKey", source.object_id, source.derivative_type)
                raise MediaCacheSourceMissing("Media object no longer exists") from exc
            except Exception as exc:
                LOG.info("media_cache_fill_failed object_id=%s type=%s error_code=%s", source.object_id, source.derivative_type, type(exc).__name__)
                if isinstance(exc, MediaCacheError):
                    raise
                raise MediaCacheError("Unable to fill private media cache") from exc
        elapsed = time.monotonic() - started
        LOG.info("media_cache_fill_seconds=%.3f object_id=%s type=%s", elapsed, source.object_id, source.derivative_type)
        LOG.info("media_cache_bytes=%s object_id=%s type=%s", size, source.object_id, source.derivative_type)
        return CachedMedia(path, relative, size)

    def _fill(self, path: Path, source: CacheSource, open_source: Callable[[], BinaryIO]) -> int:
        expected_size = int(source.file_size)
        if expected_size < 1 or expected_size > self.max_bytes:
            raise MediaCacheError("Media object is not cacheable")
        self._ensure_safe_directory(path.relative_to(self.root).parent)
        temporary = self._temporary_path(path)
        total = 0
        try:
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, "wb") as output:
                source_stream = open_source()
                try:
                    while True:
                        chunk = source_stream.read(_CHUNK_SIZE)
                        if not chunk:
                            break
                        total += len(chunk)
                        if total > self.max_bytes or total > expected_size:
                            raise MediaCacheError("Media object exceeds cache limit")
                        output.write(chunk)
                finally:
                    close = getattr(source_stream, "close", None)
                    if close:
                        close()
                output.flush()
                os.fsync(output.fileno())
            if total < 1 or total != expected_size:
                raise MediaCacheError("Media object is empty or incomplete")
            self._assert_regular_file(temporary)
            os.replace(temporary, path)
            self._fsync_directory(path.parent)
            final_size = self._valid_file(path)
            if final_size != total:
                raise MediaCacheError("Media cache validation failed")
            return total
        finally:
            try:
                if os.path.lexists(temporary):
                    os.unlink(temporary)
            except OSError:
                pass

    def _ensure_root(self) -> None:
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._assert_directory(self.root)
        self.root = self.root.resolve(strict=True)

    def _ensure_safe_directory(self, relative: Path) -> Path:
        current = self.root
        for part in relative.parts:
            if part in {"", ".", ".."}:
                raise MediaCacheError("Unsafe cache directory")
            current = current / part
            if current.exists() or os.path.lexists(current):
                self._assert_directory(current)
            else:
                try:
                    current.mkdir(mode=0o700)
                except FileExistsError:
                    pass
                self._assert_directory(current)
        return current

    def _safe_path(self, relative: Path) -> Path:
        if relative.is_absolute() or ".." in relative.parts:
            raise MediaCacheError("Unsafe cache path")
        path = self.root / relative
        resolved_parent = path.parent.resolve(strict=True)
        if os.path.commonpath((str(self.root), str(resolved_parent))) != str(self.root):
            raise MediaCacheError("Cache path escaped root")
        return path

    def _valid_file(self, path: Path) -> int | None:
        try:
            self._assert_regular_file(path)
            size = path.stat().st_size
        except FileNotFoundError:
            return None
        if size < 1 or size > self.max_bytes:
            return None
        return size

    @staticmethod
    def _assert_regular_file(path: Path) -> None:
        info = os.lstat(path)
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
            raise MediaCacheError("Unsafe cache file")

    @staticmethod
    def _assert_directory(path: Path) -> None:
        info = os.lstat(path)
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
            raise MediaCacheError("Unsafe cache directory")

    @staticmethod
    def _fsync_directory(directory: Path) -> None:
        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    @staticmethod
    def _temporary_path(path: Path) -> Path:
        return path.with_name(f".{path.name}.tmp-{os.getpid()}-{time.time_ns()}")

    def _key_lock(self, path: Path):
        return _CacheKeyLock(path.with_name(f".{path.name}.lock"), self)


class _CacheKeyLock:
    def __init__(self, path: Path, cache: MediaCache, *, nonblocking=False):
        self.path = path
        self.cache = cache
        self.nonblocking = nonblocking
        self.fd = None

    def __enter__(self):
        self.cache._ensure_safe_directory(self.path.relative_to(self.cache.root).parent)
        try:
            self.fd = os.open(self.path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        except OSError as exc:
            raise MediaCacheError("Unsafe media cache lock") from exc
        try:
            info = os.fstat(self.fd)
            if not stat.S_ISREG(info.st_mode):
                raise MediaCacheError("Unsafe media cache lock")
            fcntl.flock(self.fd, fcntl.LOCK_EX | (fcntl.LOCK_NB if self.nonblocking else 0))
        except Exception:
            os.close(self.fd)
            self.fd = None
            raise
        return self

    def __exit__(self, *_exc):
        if self.fd is not None:
            fcntl.flock(self.fd, fcntl.LOCK_UN)
            os.close(self.fd)
            self.fd = None


def deliver_cached_media(cached: CachedMedia, source: CacheSource, *, cache_control: str, etag: str):
    """Return an authorised private-media response without exposing a disk path."""
    config = current_app.config
    mode = config["MEDIA_CACHE_DELIVERY_MODE"]
    if mode == "send_file":
        response = send_file(cached.path, mimetype=source.mime_type, conditional=True, etag=etag, max_age=0)
    else:
        prefix = config["MEDIA_CACHE_X_ACCEL_PREFIX"]
        response = make_response("")
        response.headers["X-Accel-Redirect"] = prefix + cached.relative_path
        response.headers["Content-Length"] = str(cached.size)
        response.headers["Content-Type"] = source.mime_type
        response.set_etag(etag)
    response.headers["Content-Disposition"] = "inline"
    response.headers["Cache-Control"] = cache_control
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


def serve_cached_source(source: CacheSource, *, cache_control: str):
    """Fill and deliver a server-resolved source; callers must authorise first."""
    from app.storage.providers import get_storage_provider

    cache = MediaCache()
    provider = get_storage_provider()
    cached = cache.get_or_fill(source, lambda: provider.open_object(source.bucket, source.immutable_key))
    return deliver_cached_media(cached, source, cache_control=cache_control,
                                etag=f"media-{source.version_id}")


def cleanup_media_cache(config=None, *, dry_run=True) -> dict[str, int]:
    """Remove old cache payloads safely; lock and temporary files are never hits."""
    config = config or current_app.config
    cache = MediaCache(config)
    cutoff = time.time() - int(config["MEDIA_CACHE_MAX_AGE_DAYS"]) * 86400
    result = {"scanned": 0, "deleted": 0, "reclaimed_bytes": 0, "errors": 0}
    candidates = []
    for base, dirs, names in os.walk(cache.root, followlinks=False):
        dirs[:] = [name for name in dirs if not os.path.islink(os.path.join(base, name))]
        for name in names:
            path = Path(base) / name
            if name.endswith(".lock"):
                continue
            try:
                info = os.lstat(path)
                if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
                    continue
                result["scanned"] += 1
                candidates.append((path, info.st_size, info.st_mtime, name.startswith(".") and ".tmp-" in name))
            except OSError:
                result["errors"] += 1
    candidates.sort(key=lambda row: row[2])
    total = sum(size for _, size, _, is_temp in candidates if not is_temp)
    for path, size, mtime, is_temp in candidates:
        expired = mtime < cutoff
        over_limit = not is_temp and total > cache.max_bytes
        if not expired and not over_limit:
            continue
        try:
            lock = _CacheKeyLock(path.with_name(f".{path.name}.lock"), cache, nonblocking=True)
            lock.__enter__()
        except (BlockingIOError, OSError, MediaCacheError):
            continue
        try:
            info = os.lstat(path)
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
                continue
            if not dry_run:
                os.unlink(path)
            result["deleted"] += 1
            result["reclaimed_bytes"] += size
            if not is_temp:
                total -= size
        except OSError:
            result["errors"] += 1
        finally:
            lock.__exit__()
    LOG.info("media_cache_cleanup scanned=%s deleted=%s reclaimed_bytes=%s errors=%s", result["scanned"], result["deleted"], result["reclaimed_bytes"], result["errors"])
    return result
